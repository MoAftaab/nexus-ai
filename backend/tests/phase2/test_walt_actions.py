def _create_submitted(client, login_as, requester_email="operator1@nexusai.demo"):
    requester = login_as(client, requester_email)
    finding = next(item for item in client.get("/api/anomalies").json()["items"] if item["severity"] == "low" and item["impact"] < 25_000 and item["actions"])
    preview = client.post("/api/changes/preview", headers=requester, json={"anomaly_id": finding["id"], "action_id": finding["actions"][0]["id"]})
    assert preview.status_code == 200, preview.text
    created = client.post("/api/changes", headers=requester, json=preview.json())
    assert created.status_code == 201, created.text
    submitted = client.post(f"/api/changes/{created.json()['request_id']}/submit", headers=requester)
    assert submitted.status_code == 200, submitted.text
    return requester, submitted.json()


def test_walt_answers_reporting_manager_and_role_site_scope_from_live_identity(client, login_as):
    operator = login_as(client, "operator1@nexusai.demo")
    manager = client.post("/api/walt/resolve", headers=operator, json={"message": "Who is my manager name?"})
    assert manager.status_code == 200, manager.text
    assert manager.json()["handled"] is True
    assert manager.json()["type"] == "identity"
    assert "Lead Wolfsburg" in manager.json()["answer"]

    scope = client.post("/api/walt/resolve", headers=operator, json={"message": "What is my role and site scope?"})
    assert scope.status_code == 200, scope.text
    assert scope.json()["identity"]["user"]["role"] == "operator"
    assert scope.json()["identity"]["site_scopes"] == ["wolfsburg"]
    assert "cannot" in scope.json()["answer"].lower()


def test_walt_previews_then_confirms_audited_notification_to_exact_approver(client, login_as):
    requester, request = _create_submitted(client, login_as)
    resolved = client.post("/api/walt/resolve", headers=requester, json={
        "message": "Ping the next approver now because the impact window is closing",
        "request_id": request["request_id"],
    })
    assert resolved.status_code == 200, resolved.text
    payload = resolved.json()
    assert payload["type"] == "action_preview"
    assert payload["action"]["kind"] == "reminder"
    assert payload["action"]["recipient_user_id"] == "lead1"
    assert payload["action"]["requires_confirmation"] is True

    before = client.get("/api/notifications", headers=login_as(client, "lead1@nexusai.demo")).json()["items"]
    confirmed = client.post(
        f"/api/changes/{request['request_id']}/reminder/confirm",
        headers=requester,
        json={"action_id": payload["action"]["action_id"]},
    )
    assert confirmed.status_code == 200, confirmed.text
    after = client.get("/api/notifications", headers=login_as(client, "lead1@nexusai.demo")).json()["items"]
    assert len(after) == len(before) + 1
    assert any(item["request_id"] == request["request_id"] and item["type"] == "approval_reminder_sent" for item in after)


def test_walt_never_bypasses_assignment_scope_or_human_decision(client, login_as):
    _, request = _create_submitted(client, login_as)
    other_operator = login_as(client, "operator2@nexusai.demo")
    denied = client.post("/api/walt/resolve", headers=other_operator, json={
        "message": "Notify the approver immediately",
        "request_id": request["request_id"],
    })
    assert denied.status_code == 200
    assert denied.json()["type"] == "denied"

    lead = login_as(client, "lead1@nexusai.demo")
    guarded = client.post("/api/walt/resolve", headers=lead, json={
        "message": "Approve this immediately",
        "request_id": request["request_id"],
    })
    assert guarded.status_code == 200
    assert guarded.json()["type"] == "guardrail"
    assert "will not approve" in guarded.json()["answer"]

    auditor = login_as(client, "auditor@nexusai.demo")
    auditor_action = client.post("/api/walt/resolve", headers=auditor, json={
        "message": "Escalate this approval",
        "request_id": request["request_id"],
    })
    assert auditor_action.status_code == 200
    assert auditor_action.json()["type"] == "denied"


def test_walt_routes_assigned_approver_escalation_to_configured_manager(client, login_as):
    _, request = _create_submitted(client, login_as)
    lead = login_as(client, "lead1@nexusai.demo")
    preview = client.post("/api/walt/resolve", headers=lead, json={
        "message": "Escalate this approval because the operational window is closing",
        "request_id": request["request_id"],
    })
    assert preview.status_code == 200, preview.text
    action = preview.json()["action"]
    assert preview.json()["type"] == "action_preview"
    assert action["kind"] == "escalation"
    assert action["recipient_user_id"] == "manager1"

    confirmed = client.post(
        f"/api/changes/{request['request_id']}/escalation/confirm",
        headers=lead,
        json={"action_id": action["action_id"]},
    )
    assert confirmed.status_code == 200, confirmed.text
    manager_notifications = client.get("/api/notifications", headers=login_as(client, "manager1@nexusai.demo")).json()["items"]
    assert any(item["request_id"] == request["request_id"] and item["type"] == "escalation_confirmed" for item in manager_notifications)


def test_walt_requires_request_disambiguation_before_notification(client, login_as):
    requester, first = _create_submitted(client, login_as)
    _, second = _create_submitted(client, login_as)
    result = client.post("/api/walt/resolve", headers=requester, json={"message": "Remind the approver"})
    assert result.status_code == 200, result.text
    assert result.json()["type"] == "clarification"
    ids = {choice["request_id"] for choice in result.json()["choices"]}
    assert {first["request_id"], second["request_id"]}.issubset(ids)
