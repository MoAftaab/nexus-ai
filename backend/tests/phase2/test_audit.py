from __future__ import annotations

from app.db import AuditLogModel, Repository
from app.config import get_settings


def test_approval_decision_creates_hash_linked_append_only_audit(client, login_as):
    requester = login_as(client, "operator1@nexusai.demo")
    findings = [item for item in client.get("/api/anomalies").json()["items"] if item["actions"]]
    finding = next((item for item in findings if item["severity"] == "low" and item["impact"] < 25_000), findings[0])
    preview = client.post("/api/changes/preview", headers=requester, json={"anomaly_id": finding["id"], "action_id": finding["actions"][0]["id"]}).json()
    request = client.post("/api/changes", headers=requester, json=preview).json()
    client.post(f"/api/changes/{request['request_id']}/submit", headers=requester)
    role = client.get(f"/api/changes/{request['request_id']}", headers=requester).json()["active_step"]["required_role"]
    approver = login_as(client, {"lead": "lead1@nexusai.demo", "manager": "manager1@nexusai.demo", "quality_compliance": "quality1@nexusai.demo", "director": "director@nexusai.demo"}[role])
    decision = client.post(f"/api/changes/{request['request_id']}/return", headers=approver, json={"comment": "needs evidence"})
    assert decision.status_code == 200
    audit = client.get("/api/audit", headers=requester).json()["items"]
    change_events = [row for row in audit if row.get("request_id") == request["request_id"]]
    assert change_events
    assert all(row.get("role") and row.get("site_id") and row.get("at") for row in change_events)
    assert all("prior_hash" in row and "current_hash" in row for row in change_events)
    assert all("snapshot_hash" in row for row in change_events)


def test_demo_reset_preserves_audit_history(client, login_as):
    headers = login_as(client, "admin@nexusai.demo")
    before = client.get("/api/audit", headers=headers).json()["items"]
    assert client.post("/api/demo/reset").status_code == 200
    after = client.get("/api/audit", headers=headers).json()["items"]
    assert len(after) >= len(before)


def test_audit_chain_has_no_duplicate_event_ids():
    repository = Repository(get_settings())
    with repository.session() as session:
        rows = session.query(AuditLogModel).all()
        assert len({row.event_id for row in rows}) == len(rows)
