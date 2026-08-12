from __future__ import annotations

from app.services.change_control import compute_approval_stages


def _create_request(client, headers, severity=None):
    findings = [item for item in client.get("/api/anomalies").json()["items"] if item["status"] != "resolved" and item["actions"]]
    if severity:
        findings = [item for item in findings if item["severity"] == severity]
    finding = findings[0]
    preview = client.post("/api/changes/preview", headers=headers, json={"anomaly_id": finding["id"], "action_id": finding["actions"][0]["id"]})
    assert preview.status_code == 200, preview.text
    response = client.post("/api/changes", headers=headers, json=preview.json())
    assert response.status_code == 201, response.text
    return response.json()


def test_custom_policy_rules_are_used_for_new_routes():
    custom_policy = {"rules": [{"name": "all-risk-manager", "severity": ["low"], "max_impact": 999_999, "roles": ["manager", "director"]}]}
    stages = compute_approval_stages("low", 1_000, False, custom_policy)
    assert [stage["required_role"] for stage in stages] == ["manager", "director"]


def test_returned_request_cannot_reuse_old_proposal(client, login_as):
    requester = login_as(client, "operator1@nexusai.demo")
    request = _create_request(client, requester, "low")
    submitted = client.post(f"/api/changes/{request['request_id']}/submit", headers=requester)
    assert submitted.status_code == 200
    role = submitted.json()["active_step"]["required_role"]
    approver_email = {"lead": "lead1@nexusai.demo", "manager": "manager1@nexusai.demo"}[role]
    returned = client.post(f"/api/changes/{request['request_id']}/return", headers=login_as(client, approver_email), json={"comment": "Please revise the source correction"})
    assert returned.status_code == 200
    blocked = client.post(f"/api/changes/{request['request_id']}/submit", headers=requester)
    assert blocked.status_code == 409
    assert "revised" in blocked.json()["detail"].lower()
    revised = client.post(f"/api/changes/{request['request_id']}/revise", headers=requester)
    assert revised.status_code == 200
    assert revised.json()["status"] == "draft"
    assert revised.json()["revision_count"] == 1
    assert revised.json()["data_preview"]
    resubmitted = client.post(f"/api/changes/{request['request_id']}/submit", headers=requester)
    assert resubmitted.status_code == 200
    assert resubmitted.json()["status"].startswith("awaiting_")


def test_requester_role_cannot_create_a_deadlocked_request(client, login_as):
    director = login_as(client, "director@nexusai.demo")
    findings = [item for item in client.get("/api/anomalies").json()["items"] if item["status"] != "resolved" and item["actions"] and item["severity"] in {"high", "critical"}]
    finding = findings[0]
    preview = client.post("/api/changes/preview", headers=director, json={"anomaly_id": finding["id"], "action_id": finding["actions"][0]["id"]})
    assert preview.status_code == 200
    response = client.post("/api/changes", headers=director, json=preview.json())
    assert response.status_code == 403
    assert "requester" in response.json()["detail"].lower()


def test_invalid_change_payload_returns_validation_error(client, login_as):
    operator = login_as(client, "operator1@nexusai.demo")
    response = client.post("/api/changes", headers=operator, json={})
    assert response.status_code == 422
    finding = next(item for item in client.get("/api/anomalies", headers=operator).json()["items"] if item["actions"] and item["status"] != "resolved")
    preview = client.post("/api/changes/preview", headers=operator, json={"anomaly_id": finding["id"], "action_id": finding["actions"][0]["id"]}).json()
    preview["impact_euros"] = int(preview["impact_euros"]) + 1
    tampered = client.post("/api/changes", headers=operator, json=preview)
    assert tampered.status_code == 422
    assert "modified" in tampered.json()["detail"].lower()
