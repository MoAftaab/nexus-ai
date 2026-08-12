from __future__ import annotations

from app.services.change_control import compute_snapshot_hash, diff_snapshots


def test_before_proposed_after_snapshots_and_field_level_diff(client, login_as):
    headers = login_as(client, "operator1@nexusai.demo")
    finding = next(item for item in client.get("/api/anomalies").json()["items"] if item["actions"])
    preview = client.post("/api/changes/preview", headers=headers, json={"anomaly_id": finding["id"], "action_id": finding["actions"][0]["id"]})
    assert preview.status_code == 200
    assert preview.json()["before_snapshot"]
    assert preview.json()["proposed_snapshot"]
    assert set(preview.json()["proposed_snapshot"]) <= set(preview.json()["before_snapshot"])
    request = client.post("/api/changes", headers=headers, json=preview.json()).json()
    before = request["before_snapshot"]
    diff = client.get(f"/api/changes/{request['request_id']}/diff", headers=headers).json()
    assert diff["fields"]
    assert request["source_hash"] == compute_snapshot_hash(before)
    assert before == client.get(f"/api/changes/{request['request_id']}", headers=headers).json()["before_snapshot"]


def test_nested_null_snapshot_diff_is_stable():
    before = {"sap": {"blockedstock": None, "location": "BN99"}, "optional": None}
    after = {"sap": {"blockedstock": 4, "location": "BN99"}, "optional": None}
    diff = diff_snapshots(before, after)
    assert diff == [{"field": "sap.blockedstock", "before": None, "proposed": 4, "after": None}]

