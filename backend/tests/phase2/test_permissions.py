def test_operator_cannot_approve_own_request(client, login_as):
    requester = login_as(client, "operator1@nexusai.demo")
    finding = next(item for item in client.get("/api/anomalies").json()["items"] if item["status"] != "resolved")
    action = finding["actions"][0]
    preview = client.post("/api/changes/preview", headers=requester, json={"anomaly_id": finding["id"], "action_id": action["id"]}).json()
    request = client.post("/api/changes", headers=requester, json=preview).json()
    client.post(f"/api/changes/{request['request_id']}/submit", headers=requester)
    assert client.post(f"/api/changes/{request['request_id']}/approve", headers=requester, json={}).status_code == 403


def test_site_scoped_approvers_cannot_cross_sites_but_director_can(client, login_as):
    requester = login_as(client, "operator1@nexusai.demo")
    finding = next(item for item in client.get("/api/anomalies").json()["items"] if item["status"] != "resolved")
    preview = client.post("/api/changes/preview", headers=requester, json={"anomaly_id": finding["id"], "action_id": finding["actions"][0]["id"]}).json()
    request = client.post("/api/changes", headers=requester, json=preview).json()
    client.post(f"/api/changes/{request['request_id']}/submit", headers=requester)
    assert client.get("/api/changes", headers=login_as(client, "operator2@nexusai.demo")).json()["total"] == 0
    assert client.post(f"/api/changes/{request['request_id']}/approve", headers=login_as(client, "lead2@nexusai.demo"), json={}).status_code == 403


def test_auditor_is_read_only_and_admin_can_manage_users_and_policies(client, login_as):
    auditor = login_as(client, "auditor@nexusai.demo")
    assert client.get("/api/changes", headers=auditor).status_code == 200
    assert client.post("/api/changes", headers=auditor, json={}).status_code == 403
    assert client.get("/api/admin/users", headers=auditor).status_code == 403
    admin = login_as(client, "admin@nexusai.demo")
    assert client.get("/api/admin/users", headers=admin).status_code == 200
    created = client.post("/api/admin/users", headers=admin, json={"email": "new@nexusai.demo", "display_name": "New", "role": "operator", "site_scopes": ["pune"]})
    assert created.status_code in {200, 201}


def test_unauthenticated_wrong_role_empty_scope_and_role_change_are_blocked(client, login_as):
    assert client.get("/api/changes").status_code == 401
    assert client.get("/api/inbox", headers=login_as(client, "operator1@nexusai.demo")).status_code == 200
    assert client.post("/api/admin/policy", headers=login_as(client, "operator1@nexusai.demo"), json={}).status_code == 403


def test_only_the_exact_assigned_role_and_user_can_decide(client, login_as):
    admin = login_as(client, "admin@nexusai.demo")
    backup = client.post("/api/admin/users", headers=admin, json={
        "email": "leadbackup@nexusai.demo",
        "display_name": "Backup Lead Wolfsburg",
        "role": "lead",
        "site_scopes": ["wolfsburg"],
    })
    assert backup.status_code in {200, 201}

    requester = login_as(client, "operator1@nexusai.demo")
    finding = next(item for item in client.get("/api/anomalies").json()["items"] if item["actions"] and item["severity"] == "low" and item["impact"] < 25_000)
    preview = client.post("/api/changes/preview", headers=requester, json={"anomaly_id": finding["id"], "action_id": finding["actions"][0]["id"]}).json()
    request = client.post("/api/changes", headers=requester, json=preview).json()
    submitted = client.post(f"/api/changes/{request['request_id']}/submit", headers=requester)
    assert submitted.status_code == 200

    auditor_detail = client.get(f"/api/changes/{request['request_id']}", headers=login_as(client, "auditor@nexusai.demo")).json()
    assert auditor_detail["active_step"]["required_role"] == "lead"
    assert auditor_detail["active_step"]["assigned_to"] == "lead1"
    assert "approve" not in submitted.json()["allowed_actions"]

    assert client.post(f"/api/changes/{request['request_id']}/approve", headers=login_as(client, "manager1@nexusai.demo"), json={}).status_code == 403
    backup_lead = login_as(client, "leadbackup@nexusai.demo")
    assert client.post(f"/api/changes/{request['request_id']}/approve", headers=backup_lead, json={}).status_code == 403
    walt = client.post("/api/chat", headers=backup_lead, json={"message": "Who is assigned and can I approve this request?", "request_id": request["request_id"]})
    assert walt.status_code == 200
    assert "Assigned account: lead1" in walt.json()["answer"]
    assert "view evidence, view audit" in walt.json()["answer"]
    assigned = client.post(f"/api/changes/{request['request_id']}/approve", headers=login_as(client, "lead1@nexusai.demo"), json={})
    assert assigned.status_code == 200


def test_admin_cannot_impersonate_director_or_roll_back(client, login_as):
    admin = login_as(client, "admin@nexusai.demo")
    backup_manager = client.post("/api/admin/users", headers=admin, json={
        "email": "aaa-manager@nexusai.demo", "display_name": "Unassigned Backup Manager", "role": "manager", "site_scopes": ["wolfsburg"],
    })
    assert backup_manager.status_code in {200, 201}
    requester = login_as(client, "operator1@nexusai.demo")
    finding = next(item for item in client.get("/api/anomalies").json()["items"] if item["actions"] and item["severity"] in {"high", "critical"} and not any(term in item["title"].lower() for term in ("ppap", "hazmat", "vda", "sds", "compliance", "document release")))
    preview = client.post("/api/changes/preview", headers=requester, json={"anomaly_id": finding["id"], "action_id": finding["actions"][0]["id"]}).json()
    request = client.post("/api/changes", headers=requester, json=preview).json()
    submitted = client.post(f"/api/changes/{request['request_id']}/submit", headers=requester)
    assert submitted.status_code == 200
    detail = client.get(f"/api/changes/{request['request_id']}", headers=login_as(client, "auditor@nexusai.demo")).json()
    assert detail["active_step"]["assigned_to"] == "manager1"
    assert client.post(f"/api/changes/{request['request_id']}/approve", headers=login_as(client, "aaa-manager@nexusai.demo"), json={}).status_code == 403
    manager = client.post(f"/api/changes/{request['request_id']}/approve", headers=login_as(client, "manager1@nexusai.demo"), json={})
    assert manager.status_code == 200
    assert manager.json()["active_step"]["required_role"] == "director"

    assert client.post(f"/api/changes/{request['request_id']}/approve", headers=admin, json={}).status_code == 403
    final = client.post(f"/api/changes/{request['request_id']}/approve", headers=login_as(client, "director@nexusai.demo"), json={})
    assert final.status_code == 200
    assert final.json()["status"] == "verified"
    assert client.post(f"/api/changes/{request['request_id']}/rollback", headers=admin, json={"comment": "admin bypass"}).status_code == 403
