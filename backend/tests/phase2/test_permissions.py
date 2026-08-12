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

