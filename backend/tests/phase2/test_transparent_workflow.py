from __future__ import annotations


def _create_high_request(client, login_as):
    requester = login_as(client, "operator1@nexusai.demo")
    finding = next(item for item in client.get("/api/anomalies", headers=requester).json()["items"] if item["actions"] and item["severity"] in {"high", "critical"})
    preview = client.post("/api/changes/preview", headers=requester, json={"anomaly_id": finding["id"], "action_id": finding["actions"][0]["id"]})
    assert preview.status_code == 200, preview.text
    created = client.post("/api/changes", headers=requester, json=preview.json())
    assert created.status_code == 201, created.text
    return requester, created.json()


def test_request_detail_exposes_owner_decision_and_saved_data_preview(client, login_as):
    requester, request = _create_high_request(client, login_as)
    detail = client.get(f"/api/changes/{request['request_id']}", headers=requester)
    assert detail.status_code == 200
    body = detail.json()
    assert body["current_owner"]["role"] == "requester"
    assert body["can_decide"] is False
    assert body["data_preview"]
    assert body["effect"]["status"] == "planned"

    assert client.post(f"/api/changes/{request['request_id']}/submit", headers=requester).status_code == 200
    manager = login_as(client, "manager1@nexusai.demo")
    waiting = client.get(f"/api/changes/{request['request_id']}", headers=manager).json()
    assert waiting["current_owner"]["role"] == "manager"
    assert waiting["current_owner"]["user_ids"]
    assert waiting["can_decide"] is True
    assert waiting["data_preview"][0]["before"] != waiting["data_preview"][0]["proposed"]


def test_notifications_follow_request_routing_and_rollback_is_director_only(client, login_as):
    requester, request = _create_high_request(client, login_as)
    assert client.post(f"/api/changes/{request['request_id']}/submit", headers=requester).status_code == 200
    manager = login_as(client, "manager1@nexusai.demo")
    manager_notifications = client.get("/api/notifications", headers=manager)
    assert manager_notifications.status_code == 200
    assert any(item["request_id"] == request["request_id"] for item in manager_notifications.json()["items"])
    assert client.post(f"/api/changes/{request['request_id']}/rollback", headers=manager, json={"comment": "not allowed"}).status_code == 403

    approved = client.post(f"/api/changes/{request['request_id']}/approve", headers=manager, json={"comment": "manager approved"})
    assert approved.status_code == 200, approved.text
    director = login_as(client, "director@nexusai.demo")
    final = client.post(f"/api/changes/{request['request_id']}/approve", headers=director, json={"comment": "director approved"})
    assert final.status_code == 200, final.text
    assert final.json()["status"] == "verified"
    assert final.json()["rollback_available"] is True

    rolled_back = client.post(f"/api/changes/{request['request_id']}/rollback", headers=director, json={"comment": "Restore the approved source state"})
    assert rolled_back.status_code == 200, rolled_back.text
    assert rolled_back.json()["status"] == "rolled_back"
    assert rolled_back.json()["rollback_available"] is False
    assert rolled_back.json()["effect"]["status"] == "rolled_back"
