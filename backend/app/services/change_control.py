"""Canonical change-request workflow, snapshots, approvals, and execution."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import select

from app.db import (
    ApprovalPolicyModel, ApprovalStepModel, AuditLogModel, ChangeRequestModel,
    ContainerModel, DispatchScheduleModel, DocumentModel, InboundOrderModel,
    InventoryPositionModel, MasterSkuModel, OutboundOrderModel, Repository,
    SupplierModel, WorkforceLogModel,
)
from app.services.auth import can_access_site, can_approve_role
from app.services.notifications import notify_request, users_for_role


MODEL_BY_TABLE = {
    "master_skus": MasterSkuModel, "inventory_positions": InventoryPositionModel,
    "inbound_orders": InboundOrderModel, "outbound_orders": OutboundOrderModel,
    "dispatch_schedule": DispatchScheduleModel, "workforce_logs": WorkforceLogModel,
    "containers": ContainerModel, "documents": DocumentModel, "suppliers": SupplierModel,
}


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def compute_snapshot_hash(snapshot: dict[str, Any]) -> str:
    canonical = json.dumps(_jsonable(snapshot), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            result.update(_flatten(item, f"{prefix}.{key}" if prefix else key))
        return result
    return {prefix: value}


def diff_snapshots(before: dict[str, Any], proposed: dict[str, Any], after: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    before_flat, proposed_flat, after_flat = _flatten(before), _flatten(proposed), _flatten(after or {})
    fields = sorted(set(before_flat) | set(proposed_flat) | set(after_flat))
    return [{"field": field, "before": before_flat.get(field), "proposed": proposed_flat.get(field), "after": after_flat.get(field)} for field in fields if before_flat.get(field) != proposed_flat.get(field)]


def snapshot_data_preview(before: dict[str, Any], proposed: dict[str, Any], after: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return a saved, row-level before/proposed/after preview for the user interface."""
    before_rows = {(row.get("table"), row.get("key")): row.get("payload", {}) for row in before.get("records", [])}
    proposed_rows = {(row.get("table"), row.get("key")): row.get("payload", {}) for row in proposed.get("records", [])}
    after_rows = {(row.get("table"), row.get("key")): row.get("payload", {}) for row in (after or {}).get("records", [])}
    result: list[dict[str, Any]] = []
    for record_key in sorted(set(before_rows) | set(proposed_rows) | set(after_rows), key=lambda value: (str(value[0]), str(value[1]))):
        before_row = before_rows.get(record_key, {})
        proposed_row = proposed_rows.get(record_key, {})
        after_row = after_rows.get(record_key, {})
        # The proposed snapshot intentionally stores only fields that will
        # change. Including every field from the full before/after payload would
        # make unchanged columns look like proposed null values.
        fields = sorted(set(proposed_row))
        for field in fields:
            if field == "id" or before_row.get(field) == proposed_row.get(field):
                continue
            result.append({"table": record_key[0], "record_key": record_key[1], "field": field, "before": before_row.get(field), "proposed": proposed_row.get(field), "after": after_row.get(field) if after else None})
    return result


def _record_table(record: dict[str, Any]) -> str:
    if "ppap_attached" in record:
        return "documents"
    if "configured_lead" in record:
        return "suppliers"
    if "total_load_kg" in record:
        return "dispatch_schedule"
    if "picked_qty" in record:
        return "outbound_orders"
    if "overdue_hours" in record:
        return "containers"
    if "fitment_wms" in record:
        return "master_skus"
    if "pick_rate" in record:
        return "workforce_logs"
    if "expected_qty" in record:
        return "inbound_orders"
    return "inventory_positions"


def _target_records(anomaly, store) -> list[tuple[str, str, dict[str, Any]]]:
    data = store._dataset
    records: list[tuple[str, str, dict[str, Any]]] = []
    if anomaly.type in {"Master data conflict", "Compliance", "Warehouse execution"}:
        records = [("master_skus", row["id"], row) for row in data.skus if row["id"] == anomaly.sku]
    elif anomaly.type == "Inventory reconciliation":
        records = [("inventory_positions", row["id"], row) for row in data.inventory if row["sku"] == anomaly.sku and max(row["wms"], row["erp"], row["physical"]) - min(row["wms"], row["erp"], row["physical"]) >= 25]
    elif anomaly.type == "Document intelligence":
        records = [("documents", row["id"], row) for row in data.documents if row["sku"] == anomaly.sku and not row["ppap_attached"]]
    elif anomaly.type == "Supplier reliability":
        records = [("suppliers", row["id"], row) for row in data.suppliers if row["name"] in anomaly.title]
    elif anomaly.type == "Dispatch readiness":
        records = [("dispatch_schedule", row["id"], row) for row in data.dispatches if row["id"] in anomaly.title or row["dock"] == anomaly.zone]
    elif anomaly.type == "Workforce performance":
        records = [("workforce_logs", row["id"], row) for row in data.workforce if row["zone"] == anomaly.zone and row["pick_rate"] < 70]
    elif anomaly.type == "SLA escalation":
        records = [("outbound_orders", row["id"], row) for row in data.outbound_orders if row["id"] in anomaly.title]
    elif anomaly.type == "Replenishment risk":
        records = [("inventory_positions", row["id"], row) for row in data.inventory if row["sku"] == anomaly.sku]
    elif anomaly.type == "Container tracking":
        records = [("containers", row["id"], row) for row in data.containers if row["overdue_hours"] > 24]
    elif anomaly.type.startswith("SAP"):
        records = [("inventory_positions", row["id"], row) for row in data.inventory if row.get("material") == anomaly.sku or (anomaly.type != "SAP storage fragmentation" and row.get("sap_anchor"))]
    return records[:100]


def _changed_values(anomaly, record: dict[str, Any]) -> dict[str, Any]:
    if anomaly.type == "Master data conflict":
        result = {}
        if record.get("fitment_wms") != record.get("fitment_erp"):
            result["fitment_wms"] = record.get("fitment_erp")
        if record.get("wms_weight_kg") is not None and record.get("wms_weight_kg") != record.get("weight_kg"):
            result["wms_weight_kg"] = record.get("weight_kg")
        if record.get("tms_weight_kg") is not None and record.get("tms_weight_kg") != record.get("weight_kg"):
            result["tms_weight_kg"] = record.get("weight_kg")
        return result
    if anomaly.type == "Inventory reconciliation":
        return {key: record.get("physical") for key in ("wms", "erp", "tms")}
    if anomaly.type == "Document intelligence":
        return {"ppap_attached": True}
    if anomaly.type == "Supplier reliability":
        return {"configured_lead": record.get("actual_lead")}
    if anomaly.type == "Dispatch readiness":
        return {"label_success": record.get("total_labels"), "total_load_kg": int(record.get("vehicle_capacity_kg", 0) * .88)}
    if anomaly.type == "Workforce performance":
        return {"pick_rate": 70, "overtime_hours": .5, "exceptions": 1}
    if anomaly.type == "SLA escalation":
        return {"picked_qty": record.get("ordered_qty"), "pick_status": "completed"}
    if anomaly.type == "Replenishment risk":
        return {"expected_qty": max(1, int(record.get("wms", 0))), "expected_date": "expedited"}
    if anomaly.type == "Container tracking":
        return {"overdue_hours": 0}
    if anomaly.type == "Compliance":
        return {"hazmat": True}
    if anomaly.type == "Warehouse execution":
        return {"bin_active": True}
    if anomaly.type == "SAP fiscal year desync":
        return {"fiscalyearofcurrentperiod": 2026, "currentperiod": "12"}
    if anomaly.type == "SAP physical inventory audit":
        return {"dateoflastpostedcount": "20260720", "physicalinventoryblockingind": ""}
    if anomaly.type == "SAP blocked stock":
        return {"blockedstock": 0, "stockinqualityinspection": 0, "freeavailablestock": max(1, record.get("freeavailablestock", 1))}
    if anomaly.type == "SAP master data deletion":
        return {"deletionflag": "", "maintenancestatus": "DL"}
    if anomaly.type == "SAP storage fragmentation":
        return {"storagelocation": "CONSOLIDATED"}
    return {}


def _snapshot_for(anomaly, store, site_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    targets = _target_records(anomaly, store)
    before_records = [{"table": table, "key": key, "payload": _jsonable(deepcopy(record))} for table, key, record in targets]
    proposed_records = []
    fields: set[str] = set()
    for table, key, record in targets:
        changes = _changed_values(anomaly, record)
        fields.update(changes)
        proposed_records.append({"table": table, "key": key, "payload": _jsonable(changes)})
    base = {"records": before_records, "fields": sorted(fields), "site_id": site_id}
    proposed = {"records": proposed_records, "fields": sorted(fields), "site_id": site_id}
    return base, proposed


def _after_snapshot_for(before_snapshot: dict[str, Any], store, site_id: str) -> dict[str, Any]:
    """Capture the complete live records that were in the approved before snapshot.

    Target selection is based on the saved keys instead of the anomaly detector's
    current predicate, because a successful correction may make the anomaly no
    longer match that predicate.
    """
    records: list[dict[str, Any]] = []
    for saved in before_snapshot.get("records", []):
        table, key = saved.get("table"), saved.get("key")
        current = next((row for row in _dataset_records(store, table) if str(row.get("id")) == str(key)), None)
        if current is not None:
            records.append({"table": table, "key": key, "payload": _jsonable(deepcopy(current))})
    return {"records": records, "fields": list(before_snapshot.get("fields", [])), "site_id": site_id}


def build_change_preview(anomaly_id: str, action_id: str, user: dict[str, Any], repo: Repository, store=None) -> dict[str, Any]:
    if store is None:
        raise ValueError("An OperationsStore is required to build a source-twin preview")
    anomaly = store.anomaly(anomaly_id)
    if not anomaly or not any(action.id == action_id for action in anomaly.actions):
        raise LookupError("Anomaly or action not found")
    site_id = (user.get("permitted_sites") or user.get("site_scopes") or ["wolfsburg"])[0]
    if site_id == "*":
        site_id = "wolfsburg"
    before, proposed = _snapshot_for(anomaly, store, site_id)
    regulated = any(keyword in f"{anomaly.title} {anomaly.type}".lower() for keyword in ("ppap", "hazmat", "vda", "sds", "compliance", "document release"))
    policy = _active_policy(repo)
    approval_route = compute_approval_stages(anomaly.severity, anomaly.impact, regulated, {"rules": policy.rules or [], "title": anomaly.title})
    return {
        "anomaly_id": anomaly_id, "action_id": action_id, "site_id": site_id,
        "title": anomaly.title, "severity": anomaly.severity, "impact_euros": anomaly.impact,
        "is_regulated": regulated, "before_snapshot": before, "proposed_snapshot": proposed,
        "source_hash": compute_snapshot_hash(before), "target_record_ids": [record["key"] for record in before["records"]],
        "policy_version": policy.version,
        "approval_route": approval_route,
        "expected": {"impact_euros": anomaly.impact, "value_protected": next((action.impact_saved for action in anomaly.actions if action.id == action_id), anomaly.impact), "cascade_probability": 0, "p90_exposure": anomaly.impact, "readiness_effect": "improves after verification"},
    }


def compute_approval_stages(severity: str, impact_euros: int, is_regulated: bool, policy: dict[str, Any] | ApprovalPolicyModel) -> list[dict[str, Any]]:
    severity = str(severity).lower()
    impact = int(impact_euros)
    policy_rules = policy.get("rules", []) if isinstance(policy, dict) else (policy.rules or [])
    title = str(policy.get("title", "") if isinstance(policy, dict) else "").lower()

    def matches(rule: dict[str, Any]) -> bool:
        if not isinstance(rule, dict):
            return False
        severities = rule.get("severity")
        if severities and severity not in {str(item).lower() for item in severities}:
            return False
        if rule.get("min_impact") is not None and impact < int(rule["min_impact"]):
            return False
        if rule.get("max_impact") is not None and impact > int(rule["max_impact"]):
            return False
        keywords = rule.get("keywords") or []
        if keywords and not (is_regulated or any(str(keyword).lower() in title for keyword in keywords)):
            return False
        return True

    risk_rule = next((rule for rule in policy_rules if isinstance(rule, dict) and rule.get("roles") and not rule.get("keywords") and matches(rule)), None)
    if risk_rule:
        roles = [str(role) for role in risk_rule.get("roles", []) if role]
    elif severity == "low" and impact < 25_000:
        roles = ["lead"]
    elif severity in {"high", "critical"} or impact >= 100_000:
        roles = ["manager", "director"]
    else:
        roles = ["manager"]

    regulated_rule = next((rule for rule in policy_rules if isinstance(rule, dict) and rule.get("keywords") and rule.get("roles") and matches(rule)), None)
    if regulated_rule:
        quality_roles = [str(role) for role in regulated_rule.get("roles", []) if role]
        insertion = len(roles) if roles == ["lead"] else max(0, len(roles) - 1)
        for role in reversed(quality_roles):
            if role not in roles:
                roles.insert(insertion, role)
    elif is_regulated or any(keyword in title for keyword in ("ppap", "hazmat", "vda", "sds", "compliance", "document release")):
        insertion = len(roles) if roles == ["lead"] else max(0, len(roles) - 1)
        if "quality_compliance" not in roles:
            roles.insert(insertion, "quality_compliance")

    # A malformed policy must never create duplicate approval owners.
    roles = list(dict.fromkeys(roles))
    return [{"stage": f"awaiting_{role}", "required_role": role, "order_index": index} for index, role in enumerate(roles)]


def _active_policy(repo: Repository) -> ApprovalPolicyModel:
    with repo.session() as session:
        policy = session.scalar(select(ApprovalPolicyModel).where(ApprovalPolicyModel.is_active.is_(True)).order_by(ApprovalPolicyModel.version.desc()))
        if not policy:
            raise RuntimeError("No active approval policy")
        return deepcopy(policy)


def _audit(repo: Repository, event_type: str, user: dict[str, Any], request: ChangeRequestModel | None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {"request_id": request.request_id if request else None, "anomaly_id": request.anomaly_id if request else None, "site_id": request.site_id if request else (user.get("permitted_sites") or ["*"])[0], "role": user.get("role"), "at": datetime.now(timezone.utc).isoformat(), "event": event_type, "policy_version": request.policy_version if request else None}
    if request:
        payload.update({"snapshot_hash": compute_snapshot_hash(request.before_snapshot), "before_snapshot_hash": compute_snapshot_hash(request.before_snapshot), "proposed_snapshot_hash": compute_snapshot_hash(request.proposed_snapshot)})
    if extra:
        payload.update(extra)
    with repo.session() as session:
        previous = session.scalar(select(AuditLogModel).order_by(AuditLogModel.id.desc()))
        prior_hash = (previous.payload or {}).get("current_hash", "") if previous else "GENESIS"
        payload["prior_hash"] = prior_hash
        payload["current_hash"] = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
        session.add(AuditLogModel(event_id=str(uuid.uuid4()), event_type=event_type, actor=user.get("email", "system"), payload=payload))
    return payload


def create_change_request(preview: dict[str, Any], user: dict[str, Any], repo: Repository, store=None) -> ChangeRequestModel:
    required_fields = {"anomaly_id", "action_id", "severity", "impact_euros", "before_snapshot", "proposed_snapshot", "source_hash"}
    missing = sorted(field for field in required_fields if preview.get(field) in (None, ""))
    if missing:
        raise ValueError(f"Change preview is missing required fields: {', '.join(missing)}")
    if not isinstance(preview.get("before_snapshot"), dict) or not isinstance(preview.get("proposed_snapshot"), dict):
        raise ValueError("Change snapshots must be objects")
    if compute_snapshot_hash(preview["before_snapshot"]) != preview["source_hash"]:
        raise ValueError("The source preview hash is invalid; generate a fresh preview")
    if store is not None:
        canonical = build_change_preview(str(preview["anomaly_id"]), str(preview["action_id"]), user, repo, store)
        immutable_fields = ("site_id", "severity", "impact_euros", "is_regulated", "before_snapshot", "proposed_snapshot", "source_hash")
        if any(preview.get(field) != canonical.get(field) for field in immutable_fields):
            raise ValueError("The change preview was modified; generate a fresh preview")
        preview = canonical
    site_id = preview.get("site_id", "wolfsburg")
    if not can_access_site(user, site_id):
        raise PermissionError("User cannot access this site")
    policy = _active_policy(repo)
    policy_for_route = {"rules": policy.rules or [], "title": preview.get("title", "")}
    stages = compute_approval_stages(preview["severity"], preview["impact_euros"], bool(preview.get("is_regulated")), policy_for_route)
    if user.get("role") != "admin" and user.get("role") in {stage["required_role"] for stage in stages}:
        raise PermissionError("The requester cannot also be an approval owner for this request")
    request = ChangeRequestModel(request_id=f"CR-{uuid.uuid4().hex[:12].upper()}", anomaly_id=preview["anomaly_id"], action_id=preview["action_id"], site_id=site_id, status="draft", severity=preview["severity"], impact_euros=int(preview["impact_euros"]), is_regulated=bool(preview.get("is_regulated")), requested_by=user["user_id"], policy_version=policy.version, before_snapshot=deepcopy(preview["before_snapshot"]), proposed_snapshot=deepcopy(preview["proposed_snapshot"]), source_hash=preview["source_hash"], payload={"title": preview.get("title", ""), "target_record_ids": preview.get("target_record_ids", []), "expected": preview.get("expected", {}), "requires_revision": False, "effect": {"status": "planned", "value_protected": int(preview.get("expected", {}).get("value_protected", preview.get("impact_euros", 0))), "fields": snapshot_data_preview(preview["before_snapshot"], preview["proposed_snapshot"])}})
    with repo.session() as session:
        session.add(request)
        session.flush()
        for stage in stages:
            session.add(ApprovalStepModel(request_id=request.request_id, stage=stage["stage"], required_role=stage["required_role"], site_id=site_id, status="waiting", order_index=stage["order_index"], sla_deadline=datetime.now(timezone.utc) + timedelta(hours=24)))
    _audit(repo, "change_requested", user, request)
    return request


def _request(repo: Repository, request_id: str) -> ChangeRequestModel | None:
    with repo.session() as session:
        row = session.scalar(select(ChangeRequestModel).where(ChangeRequestModel.request_id == request_id))
        return deepcopy(row) if row else None


def _steps(repo: Repository, request_id: str) -> list[ApprovalStepModel]:
    with repo.session() as session:
        return [deepcopy(item) for item in session.scalars(select(ApprovalStepModel).where(ApprovalStepModel.request_id == request_id).order_by(ApprovalStepModel.order_index)).all()]


def submit_change_request(request_id: str, user: dict[str, Any], repo: Repository) -> ChangeRequestModel:
    with repo.session() as session:
        request = session.scalar(select(ChangeRequestModel).where(ChangeRequestModel.request_id == request_id))
        if not request:
            raise LookupError("Change request not found")
        if request.requested_by != user.get("user_id"):
            raise PermissionError("Only the requester can submit this change request")
        if request.status == "returned":
            raise ValueError("This request was returned and needs a revised preview before submission")
        if request.status != "draft":
            raise PermissionError("Only a draft change request can be submitted")
        resume_order = int((request.payload or {}).get("return_to_order", 0))
        step = session.scalar(select(ApprovalStepModel).where(ApprovalStepModel.request_id == request_id, ApprovalStepModel.order_index == resume_order))
        if not step:
            raise ValueError("No approval steps configured")
        session.query(ApprovalStepModel).filter(ApprovalStepModel.request_id == request_id, ApprovalStepModel.status == "active").update({"status": "waiting"})
        step.status = "active"
        request.status = step.stage
        request.payload = {**request.payload, "requires_revision": False, "return_to_order": None}
        request.updated_at = datetime.now(timezone.utc)
        result = deepcopy(request)
    _audit(repo, "change_submitted", user, result)
    notify_request(repo, result, "submitted", actor=user.get("user_id"), detail=f"{result.request_id} is waiting for {step.required_role.replace('_', ' ')} approval.")
    return result


def revise_change_request(request_id: str, user: dict[str, Any], repo: Repository, store) -> ChangeRequestModel:
    """Create a new source-twin proposal after an approver returns a request."""
    request = _request(repo, request_id)
    if not request:
        raise LookupError("Change request not found")
    if request.requested_by != user.get("user_id"):
        raise PermissionError("Only the requester can revise this change request")
    if request.status != "returned":
        raise ValueError("Only a returned request can be revised")
    anomaly = store.anomaly(request.anomaly_id)
    if not anomaly:
        raise LookupError("Linked anomaly not found")
    before, proposed = _snapshot_for(anomaly, store, request.site_id)
    revision_number = int((request.payload or {}).get("revision_count", 0)) + 1
    resume_order = int((request.payload or {}).get("return_to_order", 0))
    with repo.session() as session:
        row = session.scalar(select(ChangeRequestModel).where(ChangeRequestModel.request_id == request_id))
        if not row or row.status != "returned":
            raise ValueError("The request changed while it was being revised")
        row.before_snapshot = deepcopy(before)
        row.proposed_snapshot = deepcopy(proposed)
        row.after_snapshot = None
        row.source_hash = compute_snapshot_hash(before)
        row.status = "draft"
        row.payload = {
            **(row.payload or {}),
            "requires_revision": False,
            "revision_count": revision_number,
            "revision_at": datetime.now(timezone.utc).isoformat(),
            "return_to_order": resume_order,
            "effect": {
                **((row.payload or {}).get("effect") or {}),
                "status": "planned",
                "fields": snapshot_data_preview(before, proposed),
                "corrections": "A new proposal is ready for approval.",
            },
        }
        step = session.scalar(select(ApprovalStepModel).where(ApprovalStepModel.request_id == request_id, ApprovalStepModel.order_index == resume_order))
        if not step:
            raise ValueError("The returned approval stage no longer exists")
        step.status = "waiting"
        step.assigned_to = None
        step.decided_at = None
        step.decided_by = None
        step.decision = None
        step.comment = None
        row.updated_at = datetime.now(timezone.utc)
        result = deepcopy(row)
    _audit(repo, "change_revised", user, result, {"revision_count": revision_number, "resume_order": resume_order})
    notify_request(repo, result, "revised", actor=user.get("user_id"), detail=f"{result.request_id} has a refreshed before-and-proposed preview and is ready to resubmit.")
    return result


def decide_approval(request_id: str, decision: str, comment: str | None, user: dict[str, Any], repo: Repository) -> ChangeRequestModel:
    decision = decision.lower()
    if decision not in {"approved", "rejected", "returned"}:
        raise ValueError("Unknown approval decision")
    if decision in {"rejected", "returned"} and not (comment or "").strip():
        raise ValueError("A comment is required")
    with repo.session() as session:
        request = session.scalar(select(ChangeRequestModel).where(ChangeRequestModel.request_id == request_id))
        if not request:
            raise LookupError("Change request not found")
        if not can_access_site(user, request.site_id):
            raise PermissionError("User cannot access this site")
        if request.requested_by == user.get("user_id"):
            raise PermissionError("Requester cannot approve their own request")
        step = session.scalar(select(ApprovalStepModel).where(ApprovalStepModel.request_id == request_id, ApprovalStepModel.status == "active"))
        if not step or not can_approve_role(user, step.required_role):
            raise PermissionError("This approval stage is not assigned to the current user")
        step.decided_at = datetime.now(timezone.utc); step.decided_by = user.get("user_id"); step.decision = decision; step.comment = comment
        if decision == "rejected":
            step.status = "rejected"; request.status = "rejected"
        elif decision == "returned":
            step.status = "waiting"; request.status = "returned"; request.payload = {**request.payload, "requires_revision": True}
            request.payload["return_to_order"] = step.order_index
        else:
            step.status = "completed"
            next_step = session.scalar(select(ApprovalStepModel).where(ApprovalStepModel.request_id == request_id, ApprovalStepModel.order_index > step.order_index).order_by(ApprovalStepModel.order_index))
            if next_step:
                next_step.status = "active"; request.status = next_step.stage
            else:
                request.status = "approved"
        request.updated_at = datetime.now(timezone.utc)
        result = deepcopy(request)
    event = "approval_decided" if decision == "approved" else f"change_{'rejected' if decision == 'rejected' else 'returned'}"
    _audit(repo, event, user, result, {"decision": decision, "comment": comment or ""})
    notify_request(repo, result, event.replace("change_", ""), actor=user.get("user_id"), detail=f"{result.request_id} was {decision} by {user.get('user_id')} and is now {result.status.replace('_', ' ')}.")
    return result


def execute_approved_change(request_id: str, user: dict[str, Any], repo: Repository, store) -> ChangeRequestModel:
    request = _request(repo, request_id)
    if not request:
        raise LookupError("Change request not found")
    if request.status != "approved":
        raise ValueError("Change request is not fully approved")
    anomaly = store.anomaly(request.anomaly_id)
    if not anomaly:
        raise LookupError("Linked anomaly not found")
    current_before, _ = _snapshot_for(anomaly, store, request.site_id)
    if compute_snapshot_hash(current_before) != request.source_hash:
        with repo.session() as session:
            row = session.scalar(select(ChangeRequestModel).where(ChangeRequestModel.request_id == request_id))
            row.status = "stale"; row.payload = {**row.payload, "failure": "Source data changed after approval"}
            result = deepcopy(row)
        _audit(repo, "change_stale", user, result, {"failure": "Source hash mismatch"})
        raise ValueError("Source data changed since preview; request is stale")
    with repo.session() as session:
        row = session.scalar(select(ChangeRequestModel).where(ChangeRequestModel.request_id == request_id))
        row.status = "applying"
    try:
        corrections = store._remediate(anomaly)
        with store._lock:
            live = next((item for item in store._anomalies if item.id == anomaly.id), None)
            if live:
                action = next((item for item in live.actions if item.id == request.action_id), None)
                if action:
                    action.status = "applied"
                live.status = "resolved"
                for node in live.cascade_nodes:
                    node.health = "healthy"
            store.repository.persist_anomalies(store._run_id, store._anomalies)
        after = _after_snapshot_for(request.before_snapshot, store, request.site_id)
        after_rows = {(row.get("table"), row.get("key")): row.get("payload", {}) for row in after.get("records", [])}
        verification_errors = []
        for saved in request.proposed_snapshot.get("records", []):
            key = (saved.get("table"), saved.get("key"))
            for field, proposed_value in (saved.get("payload") or {}).items():
                if after_rows.get(key, {}).get(field) != proposed_value:
                    verification_errors.append({"table": key[0], "field": field, "proposed": proposed_value, "after": after_rows.get(key, {}).get(field)})
        if verification_errors:
            raise ValueError("Applied source data does not match the approved proposal")
    except Exception as error:
        with repo.session() as session:
            row = session.scalar(select(ChangeRequestModel).where(ChangeRequestModel.request_id == request_id))
            row.status = "failed_verification"
            row.payload = {**(row.payload or {}), "failure": str(error), "failed_at": datetime.now(timezone.utc).isoformat(), "effect": {**((row.payload or {}).get("effect") or {}), "status": "failed_verification"}}
            failed = deepcopy(row)
        _audit(repo, "change_failed_verification", user, failed, {"failure": str(error)})
        notify_request(repo, failed, "failed_verification", actor=user.get("user_id"), detail=f"{failed.request_id} could not be verified and was stopped for investigation.")
        raise ValueError(str(error)) from error
    with repo.session() as session:
        row = session.scalar(select(ChangeRequestModel).where(ChangeRequestModel.request_id == request_id))
        row.after_snapshot = after
        row.status = "verified"
        verification_time = datetime.now(timezone.utc).isoformat()
        effect = {**(row.payload or {}).get("effect", {}), "status": "verified", "value_protected": row.impact_euros, "corrections": corrections, "after_snapshot_hash": compute_snapshot_hash(after), "verified_at": verification_time}
        row.payload = {**row.payload, "corrections": corrections, "verification": {"status": "verified", "verified_at": verification_time}, "effect": effect}
        result = deepcopy(row)
    repo.add_outcome("fix", f"Verified: {anomaly.title}", corrections or "Approved source correction applied", anomaly.impact, {"request_id": request_id, "anomaly_id": anomaly.id, "change_request": True})
    _audit(repo, "change_applied", user, result, {"corrections": corrections, "after_snapshot_hash": compute_snapshot_hash(after)})
    _audit(repo, "change_verified", user, result, {"verification": "verified", "after_snapshot_hash": compute_snapshot_hash(after)})
    notify_request(repo, result, "verified", actor=user.get("user_id"), detail=f"{result.request_id} was applied and verified. The saved after preview is now available.")
    return result


def verify_change(request_id: str, repo: Repository) -> ChangeRequestModel:
    request = _request(repo, request_id)
    if not request:
        raise LookupError("Change request not found")
    return request


def _dataset_records(store, table: str) -> list[dict[str, Any]]:
    collections = {
        "master_skus": store._dataset.skus,
        "inventory_positions": store._dataset.inventory,
        "inbound_orders": store._dataset.inbound_orders,
        "outbound_orders": store._dataset.outbound_orders,
        "suppliers": store._dataset.suppliers,
        "dispatch_schedule": store._dataset.dispatches,
        "workforce_logs": store._dataset.workforce,
        "documents": store._dataset.documents,
        "containers": store._dataset.containers,
    }
    return collections.get(table, [])


def rollback_change(request_id: str, comment: str, user: dict[str, Any], repo: Repository, store) -> ChangeRequestModel:
    """Restore the exact saved before snapshot after a verified change."""
    if user.get("role") not in {"director", "admin"}:
        raise PermissionError("Only the Supply Chain Director or administrator can roll back a verified change")
    if not (comment or "").strip():
        raise ValueError("A rollback reason is required")
    request = _request(repo, request_id)
    if not request:
        raise LookupError("Change request not found")
    if not can_access_site(user, request.site_id):
        raise PermissionError("User cannot access this site")
    if request.status != "verified":
        raise ValueError("Only a verified change can be rolled back")
    if not request.after_snapshot:
        raise ValueError("The verified after snapshot is missing")
    anomaly = store.anomaly(request.anomaly_id)
    if not anomaly:
        raise LookupError("Linked anomaly not found")
    current_after = _after_snapshot_for(request.before_snapshot, store, request.site_id)
    if compute_snapshot_hash(current_after) != compute_snapshot_hash(request.after_snapshot):
        raise ValueError("Rollback blocked because live source data changed after verification")

    restored_by_table: dict[str, dict[str, dict[str, Any]]] = {}
    for record in request.before_snapshot.get("records", []):
        restored_by_table.setdefault(record["table"], {})[record["key"]] = deepcopy(record.get("payload", {}))
    for table, records in restored_by_table.items():
        model = MODEL_BY_TABLE.get(table)
        if not model:
            continue
        updates = {key: payload for key, payload in records.items()}
        if table == "documents":
            for key, payload in updates.items():
                store.repository.update_source_document(key, payload)
        else:
            store.repository.update_source_records(store._run_id, model, updates)
        for live_record in _dataset_records(store, table):
            key = live_record.get("id")
            if key in records:
                live_record.clear()
                live_record.update(deepcopy(records[key]))

    with store._lock:
        live_anomaly = next((item for item in store._anomalies if item.id == anomaly.id), None)
        if live_anomaly:
            live_anomaly.status = "open"
            for action in live_anomaly.actions:
                if action.id == request.action_id:
                    action.status = "recommended"
            for node in live_anomaly.cascade_nodes:
                node.health = "risk"
        store.repository.persist_anomalies(store._run_id, store._anomalies)

    rollback_time = datetime.now(timezone.utc).isoformat()
    with repo.session() as session:
        row = session.scalar(select(ChangeRequestModel).where(ChangeRequestModel.request_id == request_id))
        row.status = "rolled_back"
        row.payload = {**row.payload, "rollback": {"status": "rolled_back", "reason": comment.strip(), "rolled_back_by": user.get("user_id"), "rolled_back_at": rollback_time, "snapshot_hash": compute_snapshot_hash(row.before_snapshot)}, "effect": {**(row.payload or {}).get("effect", {}), "status": "rolled_back", "rollback_reason": comment.strip(), "rolled_back_at": rollback_time}}
        result = deepcopy(row)
    repo.add_outcome("rollback", f"Rolled back: {anomaly.title}", comment.strip(), 0, {"request_id": request_id, "anomaly_id": anomaly.id, "change_request": True})
    _audit(repo, "change_rollback", user, result, {"reason": comment.strip(), "restored_snapshot_hash": compute_snapshot_hash(result.before_snapshot)})
    notify_request(repo, result, "rolled_back", actor=user.get("user_id"), detail=f"{result.request_id} was rolled back by {user.get('user_id')}. The original source data was restored.")
    return result


def cancel_change_request(request_id: str, user: dict[str, Any], repo: Repository) -> ChangeRequestModel:
    with repo.session() as session:
        request = session.scalar(select(ChangeRequestModel).where(ChangeRequestModel.request_id == request_id))
        if not request:
            raise LookupError("Change request not found")
        if request.requested_by != user.get("user_id") and user.get("role") not in {"admin", "director"}:
            raise PermissionError("Only requester or administrator can cancel")
        if request.status in {"rejected", "cancelled", "verified", "stale"}:
            raise ValueError("Request is immutable")
        request.status = "cancelled"; request.updated_at = datetime.now(timezone.utc)
        result = deepcopy(request)
    _audit(repo, "change_cancelled", user, result)
    return result


def serialize_request(repo: Repository, request_id: str, user: dict[str, Any]) -> dict[str, Any] | None:
    request = _request(repo, request_id)
    if not request or not can_access_site(user, request.site_id):
        return None
    if user.get("role") == "operator" and request.requested_by != user.get("user_id"):
        return None
    steps = _steps(repo, request_id)
    payload = {"request_id": request.request_id, "anomaly_id": request.anomaly_id, "action_id": request.action_id, "site_id": request.site_id, "status": request.status, "severity": request.severity, "impact_euros": request.impact_euros, "is_regulated": request.is_regulated, "requested_by": request.requested_by, "policy_version": request.policy_version, "before_snapshot": request.before_snapshot, "proposed_snapshot": request.proposed_snapshot, "after_snapshot": request.after_snapshot, "source_hash": request.source_hash, "created_at": request.created_at.isoformat(), "updated_at": request.updated_at.isoformat(), **request.payload}
    payload["steps"] = [{"id": step.id, "stage": step.stage, "required_role": step.required_role, "assigned_to": step.assigned_to, "site_id": step.site_id, "status": step.status, "sla_deadline": step.sla_deadline.isoformat() if step.sla_deadline else None, "decided_at": step.decided_at.isoformat() if step.decided_at else None, "decided_by": step.decided_by, "decision": step.decision, "comment": step.comment, "order_index": step.order_index} for step in steps]
    payload["active_step"] = next((item for item in payload["steps"] if item["status"] == "active"), None)
    active = payload["active_step"]
    owner_labels = {"requester": "Requester", "operator": "Operations Operator", "lead": "Operations Lead", "manager": "Operations Manager", "quality_compliance": "Quality and Compliance", "director": "Supply Chain Director", "system": "System"}
    if request.status in {"draft", "returned"}:
        owner_role = "requester"
        owner_ids = [request.requested_by]
    elif active:
        owner_role = active["required_role"]
        owner_ids = [item.user_id for item in users_for_role(repo, owner_role, request.site_id)]
    else:
        owner_role = "system"
        owner_ids = []
    payload["current_owner"] = {"role": owner_role, "user_ids": owner_ids, "label": owner_labels.get(owner_role, owner_role.replace("_", " ").title())}
    payload["can_decide"] = bool(active and active["required_role"] == user.get("role") and request.requested_by != user.get("user_id") and can_approve_role(user, active["required_role"]))
    payload["data_preview"] = snapshot_data_preview(request.before_snapshot, request.proposed_snapshot, request.after_snapshot)
    payload["effect"] = {"status": "planned", **(request.payload or {}).get("effect", {})}
    payload["rollback_available"] = request.status == "verified" and user.get("role") in {"director", "admin"}
    return payload


def list_requests(repo: Repository, user: dict[str, Any]) -> list[dict[str, Any]]:
    with repo.session() as session:
        rows = session.scalars(select(ChangeRequestModel).order_by(ChangeRequestModel.created_at.desc())).all()
        ids = [row.request_id for row in rows if can_access_site(user, row.site_id) and (user.get("role") != "operator" or row.requested_by == user.get("user_id"))]
    return [serialize_request(repo, request_id, user) for request_id in ids]


def inbox(repo: Repository, user: dict[str, Any]) -> list[dict[str, Any]]:
    with repo.session() as session:
        approver_roles = [user.get("role")]
        if user.get("role") == "admin":
            approver_roles.append("director")
        steps = session.scalars(select(ApprovalStepModel).where(ApprovalStepModel.required_role.in_(approver_roles), ApprovalStepModel.status == "active")).all()
        ids = [step.request_id for step in steps]
    return [serialize_request(repo, request_id, user) for request_id in ids if serialize_request(repo, request_id, user)]


def workflow_summary(repo: Repository, user: dict[str, Any]) -> dict[str, Any]:
    requests = list_requests(repo, user)
    awaiting = [item for item in requests if str(item["status"]).startswith("awaiting_")]
    return {"total": len(requests), "stage_counts": {stage: sum(item["status"] == stage for item in requests) for stage in ("draft", "submitted", "awaiting_lead", "awaiting_manager", "awaiting_quality_compliance", "awaiting_director", "approved", "applying", "awaiting_verification", "verified", "rolled_back", "rejected", "returned", "cancelled", "stale", "failed_verification")}, "awaiting_my_decision": len(inbox(repo, user)), "value_awaiting_approval": sum(item["impact_euros"] for item in awaiting), "sla_risk": sum(1 for item in awaiting if item.get("active_step") and item["active_step"].get("sla_deadline")), "verified_value_protected": sum(item["impact_euros"] for item in requests if item["status"] == "verified")}
