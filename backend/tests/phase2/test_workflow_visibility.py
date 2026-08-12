from __future__ import annotations


def _create_low_request(client, headers):
    findings = client.get("/api/anomalies", headers=headers).json()["items"]
    finding = next(item for item in findings if item["status"] != "resolved" and item["actions"] and item["severity"] == "low" and item["impact"] < 25_000)
    preview = client.post("/api/changes/preview", headers=headers, json={"anomaly_id": finding["id"], "action_id": finding["actions"][0]["id"]})
    assert preview.status_code == 200, preview.text
    created = client.post("/api/changes", headers=headers, json=preview.json())
    assert created.status_code == 201, created.text
    return created.json()


def test_workflow_detail_exposes_each_live_status_and_stage(client, login_as):
    requester = login_as(client, "operator1@nexusai.demo")
    request = _create_low_request(client, requester)
    assert request["status"] == "draft"
    assert [step["status"] for step in request["steps"]] == ["waiting"]

    submitted = client.post(f"/api/changes/{request['request_id']}/submit", headers=requester)
    assert submitted.status_code == 200
    waiting = submitted.json()
    assert waiting["status"] == "awaiting_lead"
    assert waiting["active_step"]["required_role"] == "lead"
    assert waiting["active_step"]["status"] == "active"

    approved = client.post(f"/api/changes/{request['request_id']}/approve", headers=login_as(client, "lead1@nexusai.demo"), json={})
    assert approved.status_code == 200, approved.text
    final = approved.json()
    assert final["status"] == "verified"
    assert final["active_step"] is None
    assert [step["status"] for step in final["steps"]] == ["completed"]
    assert final["after_snapshot"]


def test_regulated_high_workflow_includes_quality_before_director(client, login_as):
    headers = login_as(client, "operator1@nexusai.demo")
    finding = next(item for item in client.get("/api/anomalies", headers=headers).json()["items"] if item["actions"] and item["severity"] in {"high", "critical"} and any(term in item["title"].lower() for term in ("ppap", "hazmat", "vda", "sds", "compliance", "document release")))
    preview = client.post("/api/changes/preview", headers=headers, json={"anomaly_id": finding["id"], "action_id": finding["actions"][0]["id"]}).json()
    created = client.post("/api/changes", headers=headers, json=preview)
    assert created.status_code == 201, created.text
    assert [step["required_role"] for step in created.json()["steps"]] == ["manager", "quality_compliance", "director"]
