"""Central, deterministic workflow authorization.

The UI and WALT consume this result, but every mutation is re-evaluated here on
the backend against the live request and active approval step.
"""
from __future__ import annotations

from typing import Any

from app.services.auth import can_access_site, can_approve_role


def _value(record: Any, key: str, default=None):
    if isinstance(record, dict):
        return record.get(key, default)
    return getattr(record, key, default)


def evaluate_workflow_permissions(
    principal: dict[str, Any],
    request: Any,
    active_step: Any | None = None,
    requested_action: str | None = None,
) -> dict[str, Any]:
    role = str(principal.get("role") or "")
    user_id = str(principal.get("user_id") or "")
    site_id = str(_value(request, "site_id", ""))
    status = str(_value(request, "status", ""))
    requester = str(_value(request, "requested_by", ""))
    in_scope = can_access_site(principal, site_id)
    owns_request = user_id == requester
    assigned_to = _value(active_step, "assigned_to") if active_step else None
    required_role = _value(active_step, "required_role") if active_step else None
    exact_role = bool(active_step and can_approve_role(principal, str(required_role)))
    exact_assignment = bool(active_step and assigned_to and assigned_to == user_id)
    separation_ok = not owns_request
    denial_reasons: list[str] = []
    actions: set[str] = set()

    if not in_scope:
        denial_reasons.append(f"The request belongs to {site_id}, which is outside the signed-in user's site scope")
    elif role == "operator" and not owns_request:
        denial_reasons.append("Operations operators can view only their own governed requests")
    else:
        actions.update({"view_evidence", "view_audit"})

    if actions and role not in {"auditor", "admin"}:
        if owns_request:
            if status == "draft":
                actions.update({"submit", "cancel"})
            elif status == "returned":
                actions.update({"revise", "cancel"})
            elif status == "waiting_for_details":
                actions.update({"respond_details", "cancel"})
            elif status.startswith("awaiting_"):
                actions.update({"cancel", "prepare_escalation"})
                if assigned_to:
                    actions.add("send_reminder")

        if active_step and status.startswith("awaiting_"):
            if not exact_role:
                denial_reasons.append(f"The active stage requires the {required_role} role")
            elif not exact_assignment:
                denial_reasons.append(f"The active stage is assigned to {assigned_to}, not {user_id}")
            elif not separation_ok:
                denial_reasons.append("The requester cannot decide their own request")
            else:
                actions.update({"approve", "reject", "return", "request_details", "delegate", "prepare_escalation"})

        if role == "director" and status == "verified":
            actions.add("rollback")

    # Auditor and administrator are deliberately read-only for operations.
    if role in {"auditor", "admin"}:
        actions.intersection_update({"view_evidence", "view_audit"})

    ordered = [
        "submit", "revise", "cancel", "approve", "reject", "return",
        "request_details", "respond_details", "delegate", "send_reminder",
        "prepare_escalation", "view_evidence",
        "view_audit", "rollback",
    ]
    allowed_actions = [action for action in ordered if action in actions]
    allowed = bool(actions) if requested_action is None else requested_action in actions
    if requested_action and not allowed and not denial_reasons:
        denial_reasons.append(f"Action '{requested_action}' is not valid while the request is {status}")
    return {
        "allowed": allowed,
        "allowed_actions": allowed_actions,
        "denial_reasons": denial_reasons,
        "scope": {"site_id": site_id, "in_scope": in_scope, "site_scopes": list(principal.get("site_scopes") or [])},
        "active_assignment": {"assigned_to": assigned_to, "required_role": required_role} if active_step else None,
        "separation_of_duties": {"requester": requester, "actor": user_id, "satisfied": separation_ok},
        "policy_version": _value(request, "policy_version"),
    }
