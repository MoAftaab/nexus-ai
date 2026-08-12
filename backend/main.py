from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, Header, HTTPException, Query, UploadFile, WebSocket
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import get_settings
from app.models import ChatRequest
from app.services.operations import OperationsStore
from app.services.document_parser import inspect_and_index
from app.services.reasoner import answer_chat, stream_chat
from app.services.event_bus import EventBus
from app.services.auth import can_access_site, principal_from_token, sign_in, sign_out
from app.services.change_control import (
    build_change_preview, cancel_change_request, create_change_request, decide_approval,
    diff_snapshots, execute_approved_change, inbox as approval_inbox, list_requests,
    revise_change_request, rollback_change, serialize_request, submit_change_request, workflow_summary,
)
from app.services.notifications import list_notifications, mark_notification_read
from app.db import ContainerModel, DispatchScheduleModel, InboundOrderModel, InventoryPositionModel, MasterSkuModel, OutboundOrderModel, SupplierModel, WorkforceLogModel


settings = get_settings()
store = OperationsStore(settings)
event_bus = EventBus(settings.redis_url)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await event_bus.start()
    yield
    await event_bus.close()


app = FastAPI(
    title="NexusAI Operations API",
    version="1.0.0",
    description="Synthetic-data automotive supply-chain cascade intelligence.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:5173", "http://localhost:4173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "time": datetime.now(timezone.utc).isoformat(), "mode": "openai" if settings.openai_api_key else "demo"}


def current_user(authorization: str | None) -> dict[str, object]:
    token = authorization.removeprefix("Bearer ").strip() if authorization else None
    user = principal_from_token(store.repository, token)
    if not user:
        raise HTTPException(status_code=401, detail="A valid NexusAI session is required")
    return user


def admin_user(authorization: str | None) -> dict[str, object]:
    user = current_user(authorization)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Administrator role required")
    return user


@app.post("/api/auth/signin")
async def auth_signin(payload: dict[str, str]) -> dict[str, object]:
    if not payload.get("email") or not payload.get("password"):
        raise HTTPException(status_code=422, detail="Email and password are required")
    result = sign_in(store.repository, payload["email"], payload["password"])
    if not result:
        raise HTTPException(status_code=401, detail="Invalid demo credentials")
    return result


@app.post("/api/auth/signout")
async def auth_signout(authorization: str | None = Header(default=None)) -> dict[str, bool]:
    current_user(authorization)
    token = authorization.removeprefix("Bearer ").strip() if authorization else ""
    return {"signed_out": sign_out(store.repository, token)}


@app.get("/api/auth/me")
async def auth_me(authorization: str | None = Header(default=None)) -> dict[str, object]:
    return current_user(authorization)


@app.get("/api/sites")
async def sites(authorization: str | None = Header(default=None)) -> dict[str, object]:
    user = current_user(authorization)
    from app.db import SiteModel
    with store.repository.session() as session:
        rows = session.scalars(select(SiteModel).order_by(SiteModel.id)).all()
        result = [{"site_id": row.site_id, "name": row.name, "plant_code": row.plant_code, "timezone": row.timezone} for row in rows if can_access_site(user, row.site_id)]
    return {"items": result}


@app.post("/api/changes/preview")
async def change_preview(payload: dict[str, str], authorization: str | None = Header(default=None)) -> dict[str, object]:
    user = current_user(authorization)
    missing = [field for field in ("anomaly_id", "action_id") if not payload.get(field)]
    if missing:
        raise HTTPException(status_code=422, detail=f"Preview requires: {', '.join(missing)}")
    try:
        return build_change_preview(payload.get("anomaly_id", ""), payload.get("action_id", ""), user, store.repository, store)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (PermissionError, ValueError) as error:
        raise HTTPException(status_code=403, detail=str(error)) from error


@app.post("/api/changes", status_code=201)
async def change_create(payload: dict[str, object], authorization: str | None = Header(default=None)) -> dict[str, object]:
    user = current_user(authorization)
    if user.get("role") not in {"operator", "lead", "manager", "quality_compliance", "director", "admin"}:
        raise HTTPException(status_code=403, detail="Read-only users cannot create change requests")
    try:
        request = create_change_request(payload, user, store.repository, store)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except (KeyError, TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return serialize_request(store.repository, request.request_id, user) or {}


@app.get("/api/changes")
async def changes(status: str | None = None, site_id: str | None = None, severity: str | None = None, authorization: str | None = Header(default=None)) -> dict[str, object]:
    user = current_user(authorization)
    items = list_requests(store.repository, user)
    if status:
        items = [item for item in items if item["status"] == status]
    if site_id:
        items = [item for item in items if item["site_id"] == site_id]
    if severity:
        items = [item for item in items if item["severity"] == severity]
    return {"items": items, "total": len(items)}


@app.get("/api/changes/{request_id}")
async def change_detail(request_id: str, authorization: str | None = Header(default=None)) -> dict[str, object]:
    result = serialize_request(store.repository, request_id, current_user(authorization))
    if not result:
        raise HTTPException(status_code=404, detail="Change request not found")
    return result


@app.post("/api/changes/{request_id}/submit")
async def change_submit(request_id: str, authorization: str | None = Header(default=None)) -> dict[str, object]:
    user = current_user(authorization)
    try:
        submit_change_request(request_id, user, store.repository)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    result = serialize_request(store.repository, request_id, user) or {}
    await event_bus.publish("approval_stage_activated", {"request_id": request_id, "site_id": result.get("site_id"), "status": result.get("status")})
    return result


@app.post("/api/changes/{request_id}/revise")
async def change_revise(request_id: str, authorization: str | None = Header(default=None)) -> dict[str, object]:
    user = current_user(authorization)
    try:
        revise_change_request(request_id, user, store.repository, store)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    result = serialize_request(store.repository, request_id, user) or {}
    await event_bus.publish("change_revised", {"request_id": request_id, "site_id": result.get("site_id"), "status": result.get("status"), "revision_count": result.get("revision_count", 0)})
    return result


async def _decide(request_id: str, decision: str, payload: dict[str, object], authorization: str | None):
    user = current_user(authorization)
    try:
        request = decide_approval(request_id, decision, str(payload.get("comment") or ""), user, store.repository)
        if decision == "approved" and request.status == "approved":
            request = execute_approved_change(request_id, user, store.repository, store)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    result = serialize_request(store.repository, request_id, user) or {}
    event_type = "approval_decided" if decision == "approved" else f"change_{'rejected' if decision == 'rejected' else 'returned'}"
    await event_bus.publish(event_type, {"request_id": request_id, "site_id": result.get("site_id"), "status": result.get("status"), "decision": decision})
    if result.get("status") == "verified":
        await event_bus.publish("change_verified", {"request_id": request_id, "site_id": result.get("site_id"), "status": "verified"})
    return result


@app.post("/api/changes/{request_id}/approve")
async def change_approve(request_id: str, payload: dict[str, object] | None = None, authorization: str | None = Header(default=None)):
    return await _decide(request_id, "approved", payload or {}, authorization)


@app.post("/api/changes/{request_id}/reject")
async def change_reject(request_id: str, payload: dict[str, object] | None = None, authorization: str | None = Header(default=None)):
    return await _decide(request_id, "rejected", payload or {}, authorization)


@app.post("/api/changes/{request_id}/return")
async def change_return(request_id: str, payload: dict[str, object] | None = None, authorization: str | None = Header(default=None)):
    return await _decide(request_id, "returned", payload or {}, authorization)


@app.post("/api/changes/{request_id}/cancel")
async def change_cancel(request_id: str, authorization: str | None = Header(default=None)) -> dict[str, object]:
    user = current_user(authorization)
    try:
        cancel_change_request(request_id, user, store.repository)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (PermissionError, ValueError) as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    result = serialize_request(store.repository, request_id, user) or {}
    await event_bus.publish("change_cancelled", {"request_id": request_id, "site_id": result.get("site_id"), "status": result.get("status")})
    return result


@app.post("/api/changes/{request_id}/rollback")
async def change_rollback(request_id: str, payload: dict[str, object] | None = None, authorization: str | None = Header(default=None)) -> dict[str, object]:
    user = current_user(authorization)
    try:
        rollback_change(request_id, str((payload or {}).get("comment") or ""), user, store.repository, store)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    result = serialize_request(store.repository, request_id, user) or {}
    await event_bus.publish("change_rollback", {"request_id": request_id, "site_id": result.get("site_id"), "status": result.get("status")})
    return result


@app.get("/api/changes/{request_id}/diff")
async def change_diff(request_id: str, authorization: str | None = Header(default=None)) -> dict[str, object]:
    result = serialize_request(store.repository, request_id, current_user(authorization))
    if not result:
        raise HTTPException(status_code=404, detail="Change request not found")
    return {"request_id": request_id, "fields": diff_snapshots(result["before_snapshot"], result["proposed_snapshot"], result.get("after_snapshot")), "data_preview": result.get("data_preview", []), "effect": result.get("effect", {})}


@app.get("/api/notifications")
async def notifications(unread_only: bool = False, authorization: str | None = Header(default=None)) -> dict[str, object]:
    user = current_user(authorization)
    items = list_notifications(store.repository, user, unread_only)
    return {"items": items, "unread": sum(1 for item in items if not item["read"]), "total": len(items)}


@app.post("/api/notifications/{notification_id}/read")
async def notification_read(notification_id: str, authorization: str | None = Header(default=None)) -> dict[str, bool]:
    user = current_user(authorization)
    if not mark_notification_read(store.repository, notification_id, user):
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"ok": True}


@app.get("/api/inbox")
async def inbox(authorization: str | None = Header(default=None)) -> dict[str, object]:
    return {"items": approval_inbox(store.repository, current_user(authorization))}


@app.get("/api/workflow/summary")
async def workflow(authorization: str | None = Header(default=None)) -> dict[str, object]:
    return workflow_summary(store.repository, current_user(authorization))


@app.get("/api/admin/users")
async def admin_users(authorization: str | None = Header(default=None)) -> dict[str, object]:
    admin_user(authorization)
    from app.db import UserModel
    with store.repository.session() as session:
        rows = session.scalars(select(UserModel).order_by(UserModel.id)).all()
        return {"items": [{"user_id": row.user_id, "email": row.email, "display_name": row.display_name, "role": row.role, "site_scopes": row.site_scopes, "is_active": row.is_active} for row in rows]}


@app.post("/api/admin/users")
async def admin_user_upsert(payload: dict[str, object], authorization: str | None = Header(default=None)) -> dict[str, object]:
    admin = admin_user(authorization)
    from app.db import UserModel
    from app.services.auth import ROLES, _hash_password
    if payload.get("role") not in ROLES or not payload.get("email"):
        raise HTTPException(status_code=422, detail="Valid email and role are required")
    with store.repository.session() as session:
        email = str(payload["email"]).lower()
        row = session.scalar(select(UserModel).where(UserModel.email == email))
        if row:
            row.display_name = str(payload.get("display_name") or row.display_name)
            row.role = str(payload["role"])
            row.site_scopes = list(payload.get("site_scopes") or [])
            row.is_active = bool(payload.get("is_active", row.is_active))
        else:
            row = UserModel(user_id=email.split("@", 1)[0], email=email, display_name=str(payload.get("display_name") or email), role=str(payload["role"]), site_scopes=list(payload.get("site_scopes") or []), password_hash=_hash_password(str(payload.get("password") or "nexusai2026")))
            session.add(row)
        session.flush()
        return {"user_id": row.user_id, "email": row.email, "display_name": row.display_name, "role": row.role, "site_scopes": row.site_scopes, "updated_by": admin["user_id"]}


@app.get("/api/admin/policy")
async def admin_policy(authorization: str | None = Header(default=None)) -> dict[str, object]:
    admin_user(authorization)
    from app.db import ApprovalPolicyModel
    with store.repository.session() as session:
        row = session.scalar(select(ApprovalPolicyModel).where(ApprovalPolicyModel.is_active.is_(True)).order_by(ApprovalPolicyModel.version.desc()))
        return {"version": row.version, "rules": row.rules, "created_by": row.created_by, "created_at": row.created_at.isoformat()}


@app.put("/api/admin/policy")
async def admin_policy_update(payload: dict[str, object], authorization: str | None = Header(default=None)) -> dict[str, object]:
    admin = admin_user(authorization)
    from app.db import ApprovalPolicyModel
    rules = payload.get("rules")
    if not isinstance(rules, list) or not rules:
        raise HTTPException(status_code=422, detail="Policy rules must be a non-empty list")
    with store.repository.session() as session:
        current = session.scalar(select(ApprovalPolicyModel).where(ApprovalPolicyModel.is_active.is_(True)).order_by(ApprovalPolicyModel.version.desc()))
        version = current.version + 1 if current else 1
        if current:
            current.is_active = False
        row = ApprovalPolicyModel(version=version, rules=rules, is_active=True, created_by=str(admin["user_id"]))
        session.add(row)
        session.flush()
        result = {"version": row.version, "rules": row.rules, "created_by": row.created_by}
    store.repository.add_audit(f"POLICY-{result['version']}-{admin['user_id']}", "policy_updated", str(admin["email"]), {"role": admin["role"], "site_id": "*", "policy_version": result["version"], "rules": rules})
    return result


@app.post("/api/admin/policy")
async def admin_policy_post(payload: dict[str, object], authorization: str | None = Header(default=None)) -> dict[str, object]:
    # Keep an explicit method response so role failures are authorization errors,
    # while policy writes remain versioned through the documented PUT endpoint.
    admin_user(authorization)
    raise HTTPException(status_code=405, detail="Use PUT /api/admin/policy")


@app.get("/api/dashboard")
async def dashboard() -> dict[str, object]:
    return store.dashboard()


@app.get("/api/agents")
async def agents() -> dict[str, object]:
    findings = store.anomalies()
    lead = findings[0] if findings else None
    return {"agents": store.dashboard()["agents"], "communication": [
        {"from": "Sentinel", "to": "Correlator", "message": f"{lead.id if lead else 'No finding'} crossed its detection threshold", "time": (datetime.now(timezone.utc).replace(microsecond=0)).strftime("%H:%M")},
        {"from": "Correlator", "to": "Cascade", "message": f"{len(lead.cascade_edges) if lead else 0} downstream dependencies confirmed", "time": (datetime.now(timezone.utc).replace(microsecond=0)).strftime("%H:%M")},
        {"from": "Cascade", "to": "Impact", "message": f"{lead.time_to_impact if lead else 'No'} runway modeled to first consequence", "time": (datetime.now(timezone.utc).replace(microsecond=0)).strftime("%H:%M")},
        {"from": "Impact", "to": "Fix", "message": f"{('€' + format(lead.impact, ',')) if lead else '€0'} modeled exposure ready for control design", "time": (datetime.now(timezone.utc).replace(microsecond=0)).strftime("%H:%M")},
    ]}


@app.get("/api/agents/architecture")
async def agent_architecture() -> dict[str, object]:
    return store.agent_architecture()


@app.get("/api/anomalies")
async def anomalies(
    severity: str | None = Query(default=None), status: str | None = Query(default=None), search: str | None = Query(default=None)
) -> dict[str, object]:
    results = store.anomalies(severity=severity, status=status, search=search)
    return {"items": results, "total": len(results)}


@app.get("/api/anomalies/{anomaly_id}")
async def anomaly(anomaly_id: str) -> object:
    result = store.anomaly(anomaly_id)
    if not result:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    return result


@app.get("/api/cascades")
async def cascades(anomaly_id: str | None = Query(default=None)) -> dict[str, object]:
    if anomaly_id and not store.anomaly(anomaly_id):
        raise HTTPException(status_code=404, detail="Anomaly not found")
    return store.graph(anomaly_id)


@app.get("/api/cascades/{anomaly_id}/whatif/{action_id}")
async def cascade_whatif(anomaly_id: str, action_id: str) -> dict[str, object]:
    anomaly_result = store.anomaly(anomaly_id)
    if not anomaly_result:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    action = next((item for item in anomaly_result.actions if item.id == action_id), None)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    return store.cascade_engine.simulate_whatif(anomaly_result, action)


@app.post("/api/cascades/{anomaly_id}/explain")
async def cascade_explain(anomaly_id: str):
    anomaly_result = store.anomaly(anomaly_id)
    if not anomaly_result:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    graph_payload = store.graph(anomaly_id)
    from app.services.reasoner import stream_cascade_explanation
    return StreamingResponse(stream_cascade_explanation(anomaly_result, graph_payload, store, settings), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/anomalies/{anomaly_id}/actions/{action_id}/apply")
async def apply_action(anomaly_id: str, action_id: str) -> dict[str, object]:
    anomaly_result, action_title = store.approve_action(anomaly_id, action_id)
    if not anomaly_result or not action_title:
        raise HTTPException(status_code=404, detail="Action not found")
    payload = {
        "message": f"{action_title} is now applied and logged for human review.",
        "anomaly": anomaly_result,
        "audit": {"actor": "Operations controller", "event": "fix_action_applied", "timestamp": datetime.now(timezone.utc).isoformat()},
    }
    await event_bus.publish("action_applied", {"anomaly_id": anomaly_id, "action_id": action_id, "title": action_title})
    return payload


@app.post("/api/scan")
async def scan() -> dict[str, object]:
    result = await asyncio.to_thread(store.run_scan)
    await event_bus.publish("scan_complete", result)
    return result


INCIDENT_ALIASES = {
    "vda": "labels",
    "replenishment": "replenish",
    "po": "replenish",
    "jis": "weight",
    "hazmat": "weight",
    "leadtime": "inventory",
    "workforce": "overload",
    "sla": "overload",
    "klt": "ppap",
}


@app.post("/api/demo/inject")
async def demo_inject(incident_type: str | None = Query(default=None, alias="type")) -> dict[str, object]:
    target_type = INCIDENT_ALIASES.get(incident_type.lower(), incident_type) if incident_type else None
    if target_type and target_type != "random" and target_type not in OperationsStore.INJECTABLE_INCIDENTS:
        valid_types = list(OperationsStore.INJECTABLE_INCIDENTS) + list(INCIDENT_ALIASES.keys())
        raise HTTPException(status_code=422, detail=f"Unknown incident type; use one of {', '.join(valid_types)} or random")
    result = await asyncio.to_thread(store.inject_incident, target_type)
    if result.get("injected"):
        await event_bus.publish("scan_complete", {"scan_id": result["scan_id"], "findings": len(result["new_findings"])})
    return result


@app.post("/api/demo/storm")
async def demo_storm(count: int = Query(default=3, ge=1, le=5)) -> dict[str, object]:
    result = await asyncio.to_thread(store.inject_storm, count)
    if result.get("injected"):
        await event_bus.publish("scan_complete", {"scan_id": result["scan_id"], "findings": result["findings"]})
    return result


@app.post("/api/demo/reset")
async def demo_reset() -> dict[str, object]:
    # Model training runs ~14s; off the event loop so the server stays responsive.
    result = await asyncio.to_thread(store.reset_demo)
    await event_bus.publish("scan_complete", {"scan_id": "RESET", "findings": result["findings"]})
    return result


@app.get("/api/anomalies/{anomaly_id}/report")
async def anomaly_report(anomaly_id: str):
    report = store.incident_report(anomaly_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    from fastapi.responses import Response
    return Response(
        content=report,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="nexusai_incident_{anomaly_id}.md"'},
    )


@app.get("/api/escalations")
async def escalations() -> dict[str, object]:
    """Render the notifications that would go to the shift manager for open critical/high findings."""
    items = []
    for anomaly in store.anomalies():
        if anomaly.status == "resolved" or anomaly.severity not in {"critical", "high"}:
            continue
        owner = anomaly.actions[0].owner if anomaly.actions else "Operations"
        items.append({
            "id": anomaly.id, "severity": anomaly.severity, "channel": "#warehouse-escalations",
            "to": f"{owner} · shift manager on duty",
            "subject": f"[{anomaly.severity.upper()}] {anomaly.title}",
            "body": f"{anomaly.summary} Modeled exposure €{anomaly.impact:,}; {anomaly.time_to_impact} until first consequence. Recommended: {anomaly.actions[0].title if anomaly.actions else 'escalate for manual review'} (confidence {anomaly.actions[0].confidence if anomaly.actions else '—'}%). Open NexusAI → {anomaly.id} to approve.",
            "time_to_impact": anomaly.time_to_impact,
        })
    return {"items": items, "note": "Preview only — wire a Slack/Teams webhook or SMTP relay to deliver these for real."}


@app.get("/api/reconciliation")
async def reconciliation() -> dict[str, object]:
    return store.reconciliation()


@app.get("/api/alerts")
async def alerts() -> dict[str, object]:
    items = store.alerts()
    return {"items": items, "generated_at": datetime.now(timezone.utc).isoformat()}


@app.get("/api/actions")
async def actions(status: str | None = Query(default=None)) -> dict[str, object]:
    items = store.actions(status)
    return {"items": items, "total": len(items)}


@app.get("/api/documents")
async def documents() -> dict[str, object]:
    return store.documents()


@app.get("/api/documents/{document_id}")
async def document(document_id: str) -> dict[str, object]:
    result = store.document(document_id)
    if not result:
        raise HTTPException(status_code=404, detail="Document not found")
    return result


@app.get("/api/documents/{document_id}/preview")
async def document_preview(document_id: str):
    result = store.document(document_id)
    if not result:
        raise HTTPException(status_code=404, detail="Document not found")
    storage = result.get("storage_path")
    if not storage:
        raise HTTPException(status_code=404, detail="No preview is available for generated control records")
    candidate = Path(storage).with_name(f"{document_id}.preview.png")
    if not candidate.exists():
        raise HTTPException(status_code=404, detail="This document type has no visual preview")
    return FileResponse(candidate, media_type="image/png")


@app.get("/api/audit")
async def audit() -> dict[str, object]:
    return {"items": store.audit()}


@app.get("/api/outcomes")
async def outcomes() -> dict[str, object]:
    return store.outcomes()


@app.get("/api/system")
async def system_health() -> dict[str, object]:
    payload = store.system_health()
    # Probe the real handlers in-process so the health page reports actual
    # response times for the endpoints the UI depends on.
    import time
    checks = []
    probes = {
        "/api/dashboard": store.dashboard,
        "/api/anomalies": store.anomalies,
        "/api/cascades": store.graph,
        "/api/reconciliation": store.reconciliation,
        "/api/documents": store.documents,
        "/api/alerts": store.alerts,
        "/api/outcomes": store.outcomes,
        "/api/audit": store.audit,
    }
    for path, probe in probes.items():
        started = time.perf_counter()
        try:
            probe()
            checks.append({"endpoint": path, "status": "healthy", "latency_ms": round((time.perf_counter() - started) * 1000, 1)})
        except Exception as error:
            checks.append({"endpoint": path, "status": "failing", "latency_ms": round((time.perf_counter() - started) * 1000, 1), "error": f"{type(error).__name__}"})
    payload["endpoints"] = checks
    payload["api"] = {"status": "healthy" if all(check["status"] == "healthy" for check in checks) else "degraded", "checked_at": datetime.now(timezone.utc).isoformat(), "websocket": "/ws/operations"}
    return payload


@app.post("/api/chat")
async def chat(request: ChatRequest) -> object:
    return await answer_chat(request, store, settings)


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    return StreamingResponse(stream_chat(request, store, settings), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/documents/inspect")
async def inspect_document(file: UploadFile = File(...)) -> object:
    if not file.filename:
        raise HTTPException(status_code=400, detail="A file name is required")
    raw = await file.read()
    if len(raw) > 5_000_000:
        raise HTTPException(status_code=413, detail="Use a document smaller than 5 MB for the demo inspector")
    try:
        result = await inspect_and_index(store, settings, file.filename, raw)
        await event_bus.publish("document_ingested", {"document_id": result.document_id, "filename": result.filename, "status": result.status})
        return result
    except Exception as error:
        raise HTTPException(status_code=422, detail=f"Nexus could not parse this document: {error}") from error


@app.websocket("/ws/operations")
async def operations_socket(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token")
    principal = principal_from_token(store.repository, token) if token else None
    await event_bus.connect(websocket, principal.get("site_scopes") if principal else None)
    try:
        while True:
            dashboard_data = store.dashboard()
            await websocket.send_json({
                "type": "pulse",
                "at": datetime.now(timezone.utc).isoformat(),
                "active_findings": sum(dashboard_data["severity_counts"].values()),
                "scan_count": dashboard_data["scan_count"],
                "agent": "Sentinel",
            })
            await asyncio.sleep(5)
    except Exception:
        # Any send failure (not only WebSocketDisconnect) means the socket is gone.
        pass
    finally:
        event_bus.disconnect(websocket)


@app.get("/api/data/master-skus")
async def master_skus(page: int = 1, page_size: int = 50) -> dict[str, object]:
    return store.repository.browse(MasterSkuModel, page, page_size)


@app.get("/api/data/inventory")
async def inventory_data(page: int = 1, page_size: int = 50) -> dict[str, object]:
    return store.repository.browse(InventoryPositionModel, page, page_size)


@app.get("/api/dispatch/readiness")
async def dispatch_readiness(page: int = 1, page_size: int = 50) -> dict[str, object]:
    return store.repository.browse(DispatchScheduleModel, page, page_size)


@app.get("/api/data/{entity}")
async def browse_data(entity: str, page: int = 1, page_size: int = 50) -> dict[str, object]:
    entities = {"suppliers": SupplierModel, "inbound-orders": InboundOrderModel, "outbound-orders": OutboundOrderModel, "dispatches": DispatchScheduleModel, "workforce": WorkforceLogModel, "containers": ContainerModel}
    model = entities.get(entity)
    if not model:
        raise HTTPException(status_code=404, detail="Unknown data entity")
    return store.repository.browse(model, page, page_size)
