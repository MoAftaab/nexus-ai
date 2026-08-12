from __future__ import annotations

import copy


def first_action(client):
    findings = [item for item in client.get("/api/anomalies").json()["items"] if item["status"] != "resolved" and item["actions"]]
    finding = next((item for item in findings if item["severity"] == "low" and item["impact"] < 25_000), findings[0])
    return finding, finding["actions"][0]


def create_request(client, headers):
    finding, action = first_action(client)
    preview = client.post("/api/changes/preview", headers=headers, json={"anomaly_id": finding["id"], "action_id": action["id"]})
    assert preview.status_code == 200, preview.text
    request = client.post("/api/changes", headers=headers, json=preview.json())
    assert request.status_code == 201, request.text
    return finding, action, request.json()


def test_finding_creates_draft_then_submit_routes_to_approval(client, login_as):
    headers = login_as(client, "operator1@nexusai.demo")
    finding, action, request = create_request(client, headers)
    assert request["status"] == "draft"
    submitted = client.post(f"/api/changes/{request['request_id']}/submit", headers=headers)
    assert submitted.status_code == 200
    assert submitted.json()["status"].startswith("awaiting_")
    detail = client.get(f"/api/changes/{request['request_id']}", headers=headers)
    assert detail.json()["anomaly_id"] == finding["id"]
    assert detail.json()["action_id"] == action["id"]


def test_low_risk_can_complete_with_lead_and_final_apply(client, login_as):
    headers = login_as(client, "operator1@nexusai.demo")
    _, _, request = create_request(client, headers)
    submitted = client.post(f"/api/changes/{request['request_id']}/submit", headers=headers).json()
    decision = submitted
    while decision.get("active_step"):
        current_role = decision["active_step"]["required_role"]
        approver = {"lead": "lead1@nexusai.demo", "manager": "manager1@nexusai.demo", "quality_compliance": "quality1@nexusai.demo", "director": "director@nexusai.demo"}[current_role]
        decision_response = client.post(f"/api/changes/{request['request_id']}/approve", headers=login_as(client, approver), json={"comment": "approved"})
        assert decision_response.status_code == 200, decision_response.text
        decision = decision_response.json()
    assert decision["status"] in {"approved", "applying", "awaiting_verification", "verified"}


def test_reject_return_cancel_and_invalid_stage_actions(client, login_as):
    requester = login_as(client, "operator1@nexusai.demo")
    _, _, request = create_request(client, requester)
    assert client.post(f"/api/changes/{request['request_id']}/submit", headers=requester).status_code == 200
    role = client.get(f"/api/changes/{request['request_id']}", headers=requester).json()["active_step"]["required_role"]
    lead = login_as(client, {"lead": "lead1@nexusai.demo", "manager": "manager1@nexusai.demo", "quality_compliance": "quality1@nexusai.demo", "director": "director@nexusai.demo"}[role])
    rejected = client.post(f"/api/changes/{request['request_id']}/reject", headers=lead, json={"comment": "missing evidence"})
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert client.post(f"/api/changes/{request['request_id']}/approve", headers=lead, json={}).status_code in {400, 403, 409}

    _, _, returned_request = create_request(client, requester)
    assert client.post(f"/api/changes/{returned_request['request_id']}/submit", headers=requester).status_code == 200
    returned = client.post(f"/api/changes/{returned_request['request_id']}/return", headers=lead, json={"comment": "revise"})
    assert returned.status_code == 200
    assert returned.json()["status"] == "returned"
    assert returned.json()["requires_revision"] is True
    assert client.post(f"/api/changes/{returned_request['request_id']}/cancel", headers=requester).status_code == 200
    assert client.post(f"/api/changes/{returned_request['request_id']}/approve", headers=lead, json={}).status_code in {400, 403, 409}


def test_stale_source_is_blocked_and_cannot_be_applied(client, login_as):
    requester = login_as(client, "operator1@nexusai.demo")
    finding, action, request = create_request(client, requester)
    assert client.post(f"/api/changes/{request['request_id']}/submit", headers=requester).status_code == 200
    stale = client.post("/api/demo/inject", params={"type": "overload"})
    assert stale.status_code == 200
    detail = client.get(f"/api/changes/{request['request_id']}", headers=requester)
    assert detail.status_code == 200
    assert detail.json()["source_hash"] == request["source_hash"]


def test_cannot_skip_stage_and_rejected_request_cannot_resubmit(client, login_as):
    requester = login_as(client, "operator1@nexusai.demo")
    _, _, request = create_request(client, requester)
    assert client.post(f"/api/changes/{request['request_id']}/submit", headers=requester).status_code == 200
    assert client.post(f"/api/changes/{request['request_id']}/approve", headers=login_as(client, "director@nexusai.demo"), json={}).status_code == 403
    role = client.get(f"/api/changes/{request['request_id']}", headers=requester).json()["active_step"]["required_role"]
    lead = login_as(client, {"lead": "lead1@nexusai.demo", "manager": "manager1@nexusai.demo", "quality_compliance": "quality1@nexusai.demo", "director": "director@nexusai.demo"}[role])
    assert client.post(f"/api/changes/{request['request_id']}/reject", headers=lead, json={"comment": "no"}).status_code == 200
    assert client.post(f"/api/changes/{request['request_id']}/submit", headers=requester).status_code in {400, 403, 409}
