from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db import ApprovalStepModel, WorkflowActionModel
from main import store


def _create_submitted(client, login_as, *, high=False):
    requester = login_as(client, "operator1@nexusai.demo")
    findings = [item for item in client.get("/api/anomalies").json()["items"] if item["actions"]]
    if high:
        finding = next(item for item in findings if item["severity"] in {"high", "critical"} and not any(term in item["title"].lower() for term in ("ppap", "hazmat", "vda", "sds", "compliance", "document release")))
    else:
        finding = next(item for item in findings if item["severity"] == "low" and item["impact"] < 25_000)
    preview = client.post("/api/changes/preview", headers=requester, json={"anomaly_id": finding["id"], "action_id": finding["actions"][0]["id"]})
    assert preview.status_code == 200, preview.text
    created = client.post("/api/changes", headers=requester, json=preview.json())
    assert created.status_code == 201, created.text
    submitted = client.post(f"/api/changes/{created.json()['request_id']}/submit", headers=requester)
    assert submitted.status_code == 200, submitted.text
    return requester, submitted.json()


def test_detail_request_pauses_and_resumes_same_assignee_without_resetting_completed_stages(client, login_as):
    requester, request = _create_submitted(client, login_as, high=True)
    manager = login_as(client, "manager1@nexusai.demo")
    progressed = client.post(f"/api/changes/{request['request_id']}/approve", headers=manager, json={"comment": "Business evidence accepted"})
    assert progressed.status_code == 200, progressed.text
    assert progressed.json()["active_step"]["required_role"] == "director"

    director = login_as(client, "director@nexusai.demo")
    details = client.post(f"/api/changes/{request['request_id']}/details", headers=director, json={
        "requested_fields": ["rollback_plan", "source_owner"], "question": "Attach the controlled rollback plan", "due_hours": 12,
    })
    assert details.status_code == 201, details.text
    paused = client.get(f"/api/changes/{request['request_id']}", headers=requester).json()
    assert paused["status"] == "waiting_for_details"
    assert paused["active_step"]["status"] == "paused"
    assert "respond_details" in paused["allowed_actions"]
    assert next(step for step in paused["steps"] if step["required_role"] == "manager")["status"] == "completed"
    assert client.post(f"/api/changes/{request['request_id']}/approve", headers=director, json={}).status_code == 403

    wrong_requester = login_as(client, "operator2@nexusai.demo")
    assert client.post(f"/api/changes/{request['request_id']}/details/{details.json()['detail_request_id']}/respond", headers=wrong_requester, json={"response": "attempt"}).status_code == 403
    response = client.post(f"/api/changes/{request['request_id']}/details/{details.json()['detail_request_id']}/respond", headers=requester, json={"response": "Rollback plan attached and source owner confirmed", "evidence_attachments": ["DOC-ROLLBACK-1"]})
    assert response.status_code == 200, response.text
    resumed = client.get(f"/api/changes/{request['request_id']}", headers=director).json()
    assert resumed["status"] == "awaiting_director"
    assert resumed["active_step"]["status"] == "active"
    assert resumed["current_owner"]["user_ids"] == ["director"]
    assert next(step for step in resumed["steps"] if step["required_role"] == "manager")["status"] == "completed"


def test_delegation_is_horizontal_site_scoped_and_changes_the_only_decision_owner(client, login_as):
    admin = login_as(client, "admin@nexusai.demo")
    backup = client.post("/api/admin/users", headers=admin, json={
        "email": "delegatelead@nexusai.demo", "display_name": "Delegation Lead", "role": "lead", "site_scopes": ["wolfsburg"],
    })
    assert backup.status_code == 200, backup.text
    _, request = _create_submitted(client, login_as)
    lead = login_as(client, "lead1@nexusai.demo")
    candidates = client.get(f"/api/changes/{request['request_id']}/eligible-recipients?kind=delegation", headers=lead)
    assert candidates.status_code == 200, candidates.text
    ids = {item["user_id"] for item in candidates.json()["items"]}
    assert "delegatelead" in ids
    assert "lead2" not in ids

    assert client.post(f"/api/changes/{request['request_id']}/delegate", headers=lead, json={"assignee_user_id": "lead2", "reason": "wrong site"}).status_code == 403
    delegated = client.post(f"/api/changes/{request['request_id']}/delegate", headers=lead, json={"assignee_user_id": "delegatelead", "reason": "Shift handover coverage"})
    assert delegated.status_code == 200, delegated.text
    assert delegated.json()["previous_assignee"] == "lead1"
    assert client.post(f"/api/changes/{request['request_id']}/approve", headers=lead, json={}).status_code == 403
    accepted = client.post(f"/api/changes/{request['request_id']}/approve", headers=login_as(client, "delegatelead@nexusai.demo"), json={"comment": "Reviewed after handover"})
    assert accepted.status_code == 200, accepted.text


def test_reminder_escalation_and_sla_actions_are_confirmed_and_idempotent(client, login_as):
    requester, request = _create_submitted(client, login_as)
    request_id = request["request_id"]
    preview = client.post(f"/api/changes/{request_id}/reminder/preview", headers=requester, json={"reason": "Approval SLA is approaching"})
    assert preview.status_code == 201, preview.text
    duplicate_preview = client.post(f"/api/changes/{request_id}/reminder/preview", headers=requester, json={"reason": "Approval SLA is approaching"})
    assert duplicate_preview.status_code == 201
    assert duplicate_preview.json()["action_id"] == preview.json()["action_id"]
    confirmed = client.post(f"/api/changes/{request_id}/reminder/confirm", headers=requester, json={"action_id": preview.json()["action_id"]})
    assert confirmed.status_code == 200, confirmed.text
    repeated = client.post(f"/api/changes/{request_id}/reminder/confirm", headers=requester, json={"action_id": preview.json()["action_id"]})
    assert repeated.status_code == 200
    assert repeated.json()["confirmed_at"] == confirmed.json()["confirmed_at"]

    recipients = client.get(f"/api/changes/{request_id}/eligible-recipients?kind=escalation", headers=requester)
    assert recipients.status_code == 200
    assert recipients.json()["items"][0]["user_id"] == "manager1"
    escalation = client.post(f"/api/changes/{request_id}/escalation/preview", headers=requester, json={"reason": "Operational impact window is closing"})
    assert escalation.status_code == 201, escalation.text
    assert escalation.json()["recipient_user_id"] == "manager1"
    assert client.post(f"/api/changes/{request_id}/escalation/confirm", headers=requester, json={"action_id": escalation.json()["action_id"]}).status_code == 200

    with store.repository.session() as session:
        step = session.scalar(select(ApprovalStepModel).where(ApprovalStepModel.request_id == request_id, ApprovalStepModel.status == "active"))
        step.assigned_at = datetime.now(timezone.utc) - timedelta(hours=25)
        step.sla_deadline = datetime.now(timezone.utc) - timedelta(hours=1)
    admin = login_as(client, "admin@nexusai.demo")
    first = client.post("/api/workflow/sla/evaluate", headers=admin)
    second = client.post("/api/workflow/sla/evaluate", headers=admin)
    assert first.status_code == 200 and first.json()["actions_created"] == 1
    assert second.status_code == 200 and second.json()["actions_created"] == 0
    with store.repository.session() as session:
        automatic = session.scalars(select(WorkflowActionModel).where(WorkflowActionModel.request_id == request_id, WorkflowActionModel.action_type == "sla")).all()
        assert len(automatic) == 1


def test_unconfirmed_preview_expires_when_owner_changes(client, login_as):
    admin = login_as(client, "admin@nexusai.demo")
    client.post("/api/admin/users", headers=admin, json={"email": "handoverlead@nexusai.demo", "display_name": "Handover Lead", "role": "lead", "site_scopes": ["wolfsburg"]})
    requester, request = _create_submitted(client, login_as)
    request_id = request["request_id"]
    preview = client.post(f"/api/changes/{request_id}/reminder/preview", headers=requester, json={"reason": "Please review"})
    lead = login_as(client, "lead1@nexusai.demo")
    delegated = client.post(f"/api/changes/{request_id}/delegate", headers=lead, json={"assignee_user_id": "handoverlead", "reason": "Scheduled handover"})
    assert delegated.status_code == 200, delegated.text
    stale = client.post(f"/api/changes/{request_id}/reminder/confirm", headers=requester, json={"action_id": preview.json()["action_id"]})
    assert stale.status_code == 409
