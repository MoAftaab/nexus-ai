"""Permission-checked coordination actions layered on the canonical workflow."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.db import (
    ApprovalPolicyModel,
    ApprovalStepModel,
    ChangeRequestModel,
    DetailRequestModel,
    Repository,
    UserModel,
    WorkflowActionModel,
)
from app.services.change_control import _audit
from app.services.notifications import create_notification
from app.services.workflow_permissions import evaluate_workflow_permissions


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _in_site(user: UserModel, site_id: str) -> bool:
    scopes = list(user.site_scopes or [])
    return user.is_active and ("*" in scopes or site_id in scopes)


def _active_step(session, request_id: str, include_paused: bool = False) -> ApprovalStepModel | None:
    statuses = ["active", "paused"] if include_paused else ["active"]
    return session.scalar(select(ApprovalStepModel).where(
        ApprovalStepModel.request_id == request_id,
        ApprovalStepModel.status.in_(statuses),
    ))


def _stage_policy(session, request: ChangeRequestModel, step: ApprovalStepModel) -> dict[str, Any]:
    policy = session.scalar(select(ApprovalPolicyModel).where(ApprovalPolicyModel.version == request.policy_version).order_by(ApprovalPolicyModel.id.desc()))
    for rule in (policy.rules or []) if policy else []:
        if not isinstance(rule, dict) or step.required_role not in (rule.get("roles") or []):
            continue
        severities = {str(value).lower() for value in (rule.get("severity") or [])}
        if severities and request.severity.lower() not in severities:
            continue
        if rule.get("min_impact") is not None and request.impact_euros < int(rule["min_impact"]):
            continue
        if rule.get("max_impact") is not None and request.impact_euros > int(rule["max_impact"]):
            continue
        if rule.get("keywords") and not request.is_regulated:
            continue
        return rule
    return {}


def _serialize_detail(row: DetailRequestModel) -> dict[str, Any]:
    return {
        "detail_request_id": row.detail_request_id,
        "request_id": row.request_id,
        "approval_step_id": row.approval_step_id,
        "requested_by": row.requested_by,
        "requested_from": row.requested_from,
        "requested_fields": list(row.requested_fields or []),
        "question": row.question,
        "status": row.status,
        "response": row.response,
        "evidence_attachments": list(row.evidence_attachments or []),
        "created_at": _aware(row.created_at).isoformat(),
        "due_at": _aware(row.due_at).isoformat() if row.due_at else None,
        "responded_at": _aware(row.responded_at).isoformat() if row.responded_at else None,
    }


def _serialize_action(row: WorkflowActionModel) -> dict[str, Any]:
    return {
        "action_id": row.action_id,
        "action_type": row.action_type,
        "request_id": row.request_id,
        "approval_step_id": row.approval_step_id,
        "actor_user_id": row.actor_user_id,
        "recipient_user_id": row.recipient_user_id,
        "status": row.status,
        "reason": row.reason,
        "payload": dict(row.payload or {}),
        "created_at": _aware(row.created_at).isoformat(),
        "confirmed_at": _aware(row.confirmed_at).isoformat() if row.confirmed_at else None,
    }


def request_details(request_id: str, payload: dict[str, Any], user: dict[str, Any], repo: Repository) -> dict[str, Any]:
    fields = list(dict.fromkeys(str(item).strip() for item in payload.get("requested_fields", []) if str(item).strip()))
    question = str(payload.get("question") or "").strip()
    if not fields and not question:
        raise ValueError("Select at least one requested field or enter a question")
    if any(len(item) > 80 for item in fields):
        raise ValueError("Requested field labels must be 80 characters or fewer")
    due_hours = int(payload.get("due_hours", 24))
    with repo.session() as session:
        request = session.scalar(select(ChangeRequestModel).where(ChangeRequestModel.request_id == request_id))
        if not request:
            raise LookupError("Change request not found")
        step = _active_step(session, request_id)
        permissions = evaluate_workflow_permissions(user, request, step, "request_details")
        if not permissions["allowed"]:
            raise PermissionError("; ".join(permissions["denial_reasons"]) or "Only the assigned approver can request details")
        existing = session.scalar(select(DetailRequestModel).where(
            DetailRequestModel.request_id == request_id,
            DetailRequestModel.approval_step_id == step.id,
            DetailRequestModel.status == "open",
        ))
        if existing:
            raise ValueError("This approval stage already has an open detail request")
        detail = DetailRequestModel(
            detail_request_id=f"DR-{uuid.uuid4().hex[:12].upper()}",
            request_id=request_id,
            approval_step_id=step.id,
            requested_by=str(user["user_id"]),
            requested_from=request.requested_by,
            requested_fields=fields,
            question=question,
            due_at=_now() + timedelta(hours=due_hours),
        )
        session.add(detail)
        session.flush()
        resume_status = request.status
        step.status = "paused"
        request.status = "waiting_for_details"
        pause_sla = bool(_stage_policy(session, request, step).get("pause_on_details", True))
        request.payload = {**(request.payload or {}), "active_detail_request_id": detail.detail_request_id, "detail_resume_status": resume_status, "detail_pause_sla": pause_sla}
        request.updated_at = _now()
        result, record = deepcopy(request), _serialize_detail(detail)
    _audit(repo, "details_requested", user, result, {
        "step_id": record["approval_step_id"], "detail_request_id": record["detail_request_id"],
        "requested_from": record["requested_from"], "requested_fields": record["requested_fields"], "due_at": record["due_at"],
    })
    create_notification(repo, result.requested_by, result.site_id, "details_requested", "Approval details required", f"{user.get('display_name') or user.get('user_id')} requested additional information for {request_id}.", request_id, {"detail_request_id": record["detail_request_id"], "requested_fields": fields, "due_at": record["due_at"]})
    return record


def respond_to_details(request_id: str, detail_request_id: str, payload: dict[str, Any], user: dict[str, Any], repo: Repository) -> dict[str, Any]:
    response = str(payload.get("response") or "").strip()
    evidence = list(dict.fromkeys(str(item).strip() for item in payload.get("evidence_attachments", []) if str(item).strip()))
    if not response:
        raise ValueError("A detail response is required")
    with repo.session() as session:
        detail = session.scalar(select(DetailRequestModel).where(DetailRequestModel.detail_request_id == detail_request_id))
        if not detail:
            raise LookupError("Detail request not found")
        if detail.request_id != request_id:
            raise LookupError("Detail request does not belong to this change request")
        request = session.scalar(select(ChangeRequestModel).where(ChangeRequestModel.request_id == detail.request_id))
        step = session.get(ApprovalStepModel, detail.approval_step_id)
        permissions = evaluate_workflow_permissions(user, request, step, "respond_details")
        if not permissions["allowed"] or detail.requested_from != user.get("user_id"):
            raise PermissionError("Only the named requester can respond to this detail request")
        if request.status != "waiting_for_details" or step.status != "paused" or detail.status != "open":
            raise ValueError("This detail request is no longer open")
        detail.status = "responded"
        detail.response = response
        detail.evidence_attachments = evidence
        detail.responded_at = _now()
        step.status = "active"
        if (request.payload or {}).get("detail_pause_sla", True) and step.sla_deadline and detail.created_at:
            step.sla_deadline = _aware(step.sla_deadline) + (detail.responded_at - _aware(detail.created_at))
        request.status = str((request.payload or {}).get("detail_resume_status") or step.stage)
        request.payload = {**(request.payload or {}), "active_detail_request_id": None, "detail_resume_status": None, "detail_pause_sla": None, "last_detail_response_id": detail.detail_request_id}
        request.updated_at = _now()
        result, record, recipient = deepcopy(request), _serialize_detail(detail), step.assigned_to
    _audit(repo, "details_responded", user, result, {
        "step_id": record["approval_step_id"], "detail_request_id": record["detail_request_id"],
        "evidence_references": record["evidence_attachments"],
    })
    if recipient:
        create_notification(repo, recipient, result.site_id, "details_responded", "Requested details received", f"{result.request_id} has new evidence and is ready for your continued review.", result.request_id, {"detail_request_id": detail_request_id})
    return record


def list_detail_requests(request_id: str, user: dict[str, Any], repo: Repository) -> list[dict[str, Any]]:
    with repo.session() as session:
        request = session.scalar(select(ChangeRequestModel).where(ChangeRequestModel.request_id == request_id))
        if not request:
            raise LookupError("Change request not found")
        permissions = evaluate_workflow_permissions(user, request, _active_step(session, request_id, True))
        if "view_evidence" not in permissions["allowed_actions"]:
            raise PermissionError("This request is outside the current user's workflow scope")
        rows = session.scalars(select(DetailRequestModel).where(DetailRequestModel.request_id == request_id).order_by(DetailRequestModel.created_at)).all()
        return [_serialize_detail(row) for row in rows]


def _delegation_candidates(session, request: ChangeRequestModel, step: ApprovalStepModel) -> list[UserModel]:
    users = session.scalars(select(UserModel).where(UserModel.role == step.required_role, UserModel.is_active.is_(True))).all()
    return sorted((candidate for candidate in users if candidate.user_id not in {request.requested_by, step.assigned_to} and _in_site(candidate, request.site_id)), key=lambda item: item.display_name)


def _escalation_candidates(session, request: ChangeRequestModel, step: ApprovalStepModel, actor_id: str) -> list[UserModel]:
    users = session.scalars(select(UserModel).where(UserModel.is_active.is_(True))).all()
    by_id = {candidate.user_id: candidate for candidate in users}
    starting_user = by_id.get(step.assigned_to or "") or by_id.get(actor_id)
    ordered: list[UserModel] = []
    visited: set[str] = set()
    cursor = starting_user
    while cursor and cursor.user_id not in visited:
        visited.add(cursor.user_id)
        next_id = cursor.escalation_owner_user_id or cursor.manager_user_id
        cursor = by_id.get(next_id or "")
        if cursor and cursor.user_id != request.requested_by and _in_site(cursor, request.site_id):
            ordered.append(cursor)
    escalation_level = max(0, int((request.payload or {}).get("escalation_level", 0)))
    if ordered:
        return [ordered[escalation_level]] if escalation_level < len(ordered) else []
    next_roles = _stage_policy(session, request, step).get("escalation_chain") or {"operator": ["lead", "manager", "director"], "lead": ["manager", "director"], "manager": ["director"], "quality_compliance": ["director"], "director": []}.get(step.required_role, [])
    if escalation_level < len(next_roles):
        role = next_roles[escalation_level]
        eligible = sorted((candidate for candidate in users if candidate.role == role and candidate.user_id != request.requested_by and _in_site(candidate, request.site_id)), key=lambda item: item.display_name)
        if eligible:
            return eligible
    return []


def eligible_recipients(request_id: str, kind: str, user: dict[str, Any], repo: Repository) -> dict[str, Any]:
    if kind not in {"delegation", "escalation"}:
        raise ValueError("Recipient kind must be delegation or escalation")
    with repo.session() as session:
        request = session.scalar(select(ChangeRequestModel).where(ChangeRequestModel.request_id == request_id))
        if not request:
            raise LookupError("Change request not found")
        step = _active_step(session, request_id)
        action = "delegate" if kind == "delegation" else "prepare_escalation"
        permissions = evaluate_workflow_permissions(user, request, step, action)
        if not permissions["allowed"]:
            raise PermissionError("; ".join(permissions["denial_reasons"]) or f"This user cannot prepare a {kind}")
        candidates = _delegation_candidates(session, request, step) if kind == "delegation" else _escalation_candidates(session, request, step, str(user["user_id"]))
        items = [{"user_id": candidate.user_id, "display_name": candidate.display_name, "role": candidate.role, "site_scopes": list(candidate.site_scopes or [])} for candidate in candidates]
    return {"kind": kind, "items": items, "selection_required": len(items) > 1}


def delegate_stage(request_id: str, payload: dict[str, Any], user: dict[str, Any], repo: Repository) -> dict[str, Any]:
    new_assignee_id = str(payload.get("assignee_user_id") or "")
    reason = str(payload.get("reason") or "").strip()
    with repo.session() as session:
        request = session.scalar(select(ChangeRequestModel).where(ChangeRequestModel.request_id == request_id))
        if not request:
            raise LookupError("Change request not found")
        step = _active_step(session, request_id)
        permissions = evaluate_workflow_permissions(user, request, step, "delegate")
        if not permissions["allowed"]:
            raise PermissionError("; ".join(permissions["denial_reasons"]) or "Only the current assignee may delegate this stage")
        candidates = {candidate.user_id: candidate for candidate in _delegation_candidates(session, request, step)}
        if new_assignee_id not in candidates:
            raise PermissionError("The selected account is not an active same-role user in this request's site scope")
        previous = step.assigned_to
        step.assigned_to = new_assignee_id
        step.assigned_at = _now()
        step.assignment_reason = f"delegated_by:{user.get('user_id')}"
        request.updated_at = _now()
        result = deepcopy(request)
        receipt = {"request_id": request_id, "step_id": step.id, "previous_assignee": previous, "new_assignee": new_assignee_id, "role": step.required_role, "site_id": request.site_id, "reason": reason, "status": "completed"}
    _audit(repo, "delegation_completed", user, result, receipt)
    if previous:
        create_notification(repo, previous, result.site_id, "delegation_completed", "Approval reassigned", f"{request_id} was delegated from your queue to {new_assignee_id}.", request_id, receipt)
    create_notification(repo, new_assignee_id, result.site_id, "delegation_completed", "Approval assigned to you", f"{request_id} was delegated to your approval queue.", request_id, receipt)
    return receipt


def _sla_snapshot(step: ApprovalStepModel) -> dict[str, Any]:
    assigned_at, deadline, now = _aware(step.assigned_at), _aware(step.sla_deadline), _now()
    if not assigned_at or not deadline or deadline <= assigned_at:
        return {"deadline": deadline.isoformat() if deadline else None, "elapsed_percent": None, "overdue": False}
    elapsed = max(0.0, (now - assigned_at).total_seconds())
    total = (deadline - assigned_at).total_seconds()
    return {"deadline": deadline.isoformat(), "elapsed_percent": round(elapsed / total * 100, 1), "overdue": now >= deadline}


def prepare_workflow_action(request_id: str, kind: str, payload: dict[str, Any], user: dict[str, Any], repo: Repository) -> dict[str, Any]:
    if kind not in {"reminder", "escalation"}:
        raise ValueError("Workflow action must be reminder or escalation")
    reason = str(payload.get("reason") or "").strip()
    selected_recipient = str(payload.get("recipient_user_id") or "") or None
    with repo.session() as session:
        request = session.scalar(select(ChangeRequestModel).where(ChangeRequestModel.request_id == request_id))
        if not request:
            raise LookupError("Change request not found")
        step = _active_step(session, request_id)
        action_name = "send_reminder" if kind == "reminder" else "prepare_escalation"
        permissions = evaluate_workflow_permissions(user, request, step, action_name)
        if not permissions["allowed"]:
            raise PermissionError("; ".join(permissions["denial_reasons"]) or f"This user cannot prepare a {kind}")
        if kind == "reminder":
            recipient = session.scalar(select(UserModel).where(UserModel.user_id == step.assigned_to, UserModel.is_active.is_(True))) if step.assigned_to else None
            candidates = [recipient] if recipient and _in_site(recipient, request.site_id) else []
        else:
            candidates = _escalation_candidates(session, request, step, str(user["user_id"]))
        if selected_recipient and selected_recipient not in {candidate.user_id for candidate in candidates}:
            raise PermissionError("The selected recipient is inactive, out of scope, or not in the configured workflow chain")
        if not selected_recipient and len(candidates) > 1:
            raise ValueError("Multiple eligible recipients exist; select one explicitly")
        recipient = next((candidate for candidate in candidates if candidate.user_id == selected_recipient), candidates[0] if len(candidates) == 1 else None)
        if not recipient:
            raise ValueError(f"No eligible {kind} recipient is configured")
        level = int((request.payload or {}).get("escalation_level", 0)) + (1 if kind == "escalation" else 0)
        day_key = _now().strftime("%Y-%m-%d")
        key = f"{request_id}:{step.id}:{kind}:{user.get('user_id')}:{recipient.user_id}:{level if kind == 'escalation' else day_key}"
        existing = session.scalar(select(WorkflowActionModel).where(WorkflowActionModel.idempotency_key == key))
        if existing:
            return _serialize_action(existing)
        action = WorkflowActionModel(
            action_id=f"WA-{uuid.uuid4().hex[:12].upper()}", action_type=kind, request_id=request_id,
            approval_step_id=step.id, actor_user_id=str(user["user_id"]), recipient_user_id=recipient.user_id,
            reason=reason, idempotency_key=key,
            payload={
                "recipient_name": recipient.display_name, "recipient_role": recipient.role, "site_id": request.site_id,
                "request_title": (request.payload or {}).get("title"), "current_owner": step.assigned_to,
                "current_stage": step.stage, "severity": request.severity, "impact_euros": request.impact_euros,
                "sla": _sla_snapshot(step), "escalation_level": level if kind == "escalation" else int((request.payload or {}).get("escalation_level", 0)),
                "message": f"{kind.title()} requested for {request_id}: {reason}",
            },
        )
        session.add(action)
        try:
            session.flush()
        except IntegrityError:
            session.rollback()
            existing = session.scalar(select(WorkflowActionModel).where(WorkflowActionModel.idempotency_key == key))
            if existing:
                return _serialize_action(existing)
            raise
        result, receipt = deepcopy(request), _serialize_action(action)
    _audit(repo, f"{kind}_previewed", user, result, {"step_id": receipt["approval_step_id"], "workflow_action_id": receipt["action_id"], "recipient": receipt["recipient_user_id"], "sla_state": receipt["payload"].get("sla")})
    return receipt


def confirm_workflow_action(request_id: str, action_id: str, kind: str, user: dict[str, Any], repo: Repository) -> dict[str, Any]:
    with repo.session() as session:
        action = session.scalar(select(WorkflowActionModel).where(WorkflowActionModel.action_id == action_id))
        if not action or action.action_type != kind:
            raise LookupError("Workflow action preview not found")
        if action.request_id != request_id:
            raise LookupError("Workflow preview does not belong to this change request")
        request = session.scalar(select(ChangeRequestModel).where(ChangeRequestModel.request_id == action.request_id))
        step = _active_step(session, action.request_id)
        action_name = "send_reminder" if kind == "reminder" else "prepare_escalation"
        permissions = evaluate_workflow_permissions(user, request, step, action_name)
        if action.actor_user_id != user.get("user_id") or not permissions["allowed"]:
            raise PermissionError("This preview cannot be confirmed by the current user")
        if action.status == "confirmed":
            return _serialize_action(action)
        if action.status != "previewed":
            raise ValueError("This workflow preview has expired; prepare a fresh preview")
        if step.id != action.approval_step_id or step.assigned_to != (action.payload or {}).get("current_owner"):
            raise ValueError("The workflow owner or active stage changed; prepare a fresh preview")
        recipient = session.scalar(select(UserModel).where(UserModel.user_id == action.recipient_user_id, UserModel.is_active.is_(True)))
        if not recipient or not _in_site(recipient, request.site_id):
            raise ValueError("The preview recipient is no longer active and in scope")
        if kind == "escalation" and recipient.user_id not in {candidate.user_id for candidate in _escalation_candidates(session, request, step, str(user["user_id"]))}:
            raise ValueError("The configured escalation chain changed; prepare a fresh preview")
        confirmed_at = _now()
        claimed = session.execute(update(WorkflowActionModel).where(
            WorkflowActionModel.id == action.id,
            WorkflowActionModel.status == "previewed",
        ).values(status="confirmed", confirmed_at=confirmed_at))
        if not claimed.rowcount:
            session.refresh(action)
            return _serialize_action(action)
        action.status = "confirmed"
        action.confirmed_at = confirmed_at
        if kind == "escalation":
            request.payload = {**(request.payload or {}), "escalation_level": int((action.payload or {}).get("escalation_level", 1)), "last_escalated_at": action.confirmed_at.isoformat(), "last_escalated_to": recipient.user_id}
            request.updated_at = _now()
        result, receipt = deepcopy(request), _serialize_action(action)
    notification_type = "approval_reminder_sent" if kind == "reminder" else "escalation_confirmed"
    title = "Approval reminder" if kind == "reminder" else "Workflow escalation"
    create_notification(repo, receipt["recipient_user_id"], result.site_id, notification_type, title, str(receipt["payload"].get("message")), result.request_id, {"workflow_action_id": action_id, **receipt["payload"]})
    _audit(repo, notification_type, user, result, {"step_id": receipt["approval_step_id"], "workflow_action_id": action_id, "recipient": receipt["recipient_user_id"], "idempotency_key": action.idempotency_key, "sla_state": receipt["payload"].get("sla")})
    _audit(repo, "notification_delivered", user, result, {"workflow_action_id": action_id, "recipient": receipt["recipient_user_id"], "notification_type": notification_type})
    return receipt


def evaluate_sla(repo: Repository, user: dict[str, Any]) -> dict[str, Any]:
    if user.get("role") != "admin":
        raise PermissionError("Only a System Administrator can run the SLA evaluator manually")
    due_actions: list[tuple[str, str, int, str, str, dict[str, Any]]] = []
    with repo.session() as session:
        steps = session.scalars(select(ApprovalStepModel).where(ApprovalStepModel.status == "active", ApprovalStepModel.assigned_to.is_not(None))).all()
        for step in steps:
            request = session.scalar(select(ChangeRequestModel).where(ChangeRequestModel.request_id == step.request_id))
            sla = _sla_snapshot(step)
            percent = sla.get("elapsed_percent")
            policy = _stage_policy(session, request, step)
            warning_percent = float(policy.get("warning_percent", 75))
            urgent_percent = float(policy.get("urgent_percent", 90))
            immediate = bool(policy.get("critical_immediate_escalation")) and request.severity == "critical"
            if percent is None or (percent < warning_percent and not immediate):
                continue
            level, event = ("immediate", "automatic_escalation_triggered") if immediate else (("overdue", "automatic_escalation_triggered") if percent >= 100 else (("urgent", "approval_reminder_sent") if percent >= urgent_percent else ("warning", "sla_warning_sent")))
            key = f"{request.request_id}:{step.id}:{event}:{level}"
            if session.scalar(select(WorkflowActionModel).where(WorkflowActionModel.idempotency_key == key)):
                continue
            assignee = session.scalar(select(UserModel).where(UserModel.user_id == step.assigned_to, UserModel.is_active.is_(True)))
            recipients = _escalation_candidates(session, request, step, step.assigned_to) if level in {"overdue", "immediate"} else ([assignee] if assignee else [])
            if not recipients:
                continue
            recipient = recipients[0]
            action = WorkflowActionModel(action_id=f"WA-{uuid.uuid4().hex[:12].upper()}", action_type="sla", request_id=request.request_id, approval_step_id=step.id, actor_user_id=str(user["user_id"]), recipient_user_id=recipient.user_id, status="confirmed", reason=level, idempotency_key=key, payload={"event": event, "level": level, "sla": sla, "current_owner": step.assigned_to}, confirmed_at=_now())
            session.add(action)
            due_actions.append((request.request_id, request.site_id, step.id, recipient.user_id, event, {"idempotency_key": key, "sla": sla, "level": level}))
    for request_id, site_id, step_id, recipient, event, data in due_actions:
        create_notification(repo, recipient, site_id, event, "Approval SLA requires attention", f"{request_id} is at {data['sla']['elapsed_percent']}% of its approval SLA.", request_id, {"step_id": step_id, **data})
        request_copy = None
        with repo.session() as session:
            request_copy = deepcopy(session.scalar(select(ChangeRequestModel).where(ChangeRequestModel.request_id == request_id)))
        _audit(repo, event, user, request_copy, {"step_id": step_id, "recipient": recipient, **data})
    return {"evaluated_at": _now().isoformat(), "actions_created": len(due_actions), "items": [{"request_id": item[0], "event": item[4], "recipient": item[3]} for item in due_actions]}
