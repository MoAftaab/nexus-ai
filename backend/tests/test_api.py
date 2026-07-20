import pytest
from fastapi.testclient import TestClient

from main import app, store
from app.models import ChatRequest
from app.services.agent_mesh import deterministic_mesh


client = TestClient(app)


# ---------------------------------------------------------------------------
# Core read endpoints
# ---------------------------------------------------------------------------


def test_health_and_dashboard_are_available():
    assert client.get("/api/health").status_code == 200
    dashboard = client.get("/api/dashboard")
    assert dashboard.status_code == 200
    assert len(dashboard.json()["metrics"]) == 4


def test_anomaly_filters_and_detail():
    items = client.get("/api/anomalies").json()["items"]
    assert items, "The seeded dataset must produce findings"
    assert items == sorted(items, key=lambda item: item["impact"], reverse=True)
    severity = items[0]["severity"]
    filtered = client.get("/api/anomalies", params={"severity": severity}).json()["items"]
    assert filtered and all(item["severity"] == severity for item in filtered)
    detail = client.get(f"/api/anomalies/{items[0]['id']}")
    assert detail.status_code == 200
    assert detail.json()["id"] == items[0]["id"]


def test_unknown_ids_return_404():
    assert client.get("/api/anomalies/AN-0000").status_code == 404
    assert client.get("/api/cascades", params={"anomaly_id": "AN-0000"}).status_code == 404
    assert client.get("/api/documents/DOC-UP-MISSING").status_code == 404
    assert client.post("/api/anomalies/AN-0000/actions/FX-0/apply").status_code == 404
    assert client.get("/api/data/unknown-entity").status_code == 404


def test_seeded_cascade_has_clickable_graph_data():
    anomalies = client.get("/api/anomalies").json()["items"]
    response = client.get("/api/cascades", params={"anomaly_id": anomalies[0]["id"]})
    assert response.status_code == 200
    payload = response.json()
    assert payload["anomaly_id"] == anomalies[0]["id"]
    assert all(node["anomaly_id"] == anomalies[0]["id"] for node in payload["nodes"])


def test_reconciliation_summary_is_consistent():
    payload = client.get("/api/reconciliation").json()
    assert payload["rows"], "Reconciliation workbench needs rows"
    assert payload["summary"]["review_items"] == sum(1 for row in payload["rows"] if row["variance"])
    assert payload["summary"]["total_variance"] == sum(abs(int(row["variance"])) for row in payload["rows"])
    assert len(payload["timeline"]) == 4


def test_data_browse_is_paginated():
    first = client.get("/api/data/master-skus", params={"page": 1, "page_size": 5}).json()
    assert len(first["items"]) == 5
    assert first["total"] >= 5000
    second = client.get("/api/data/master-skus", params={"page": 2, "page_size": 5}).json()
    assert first["items"] != second["items"]


# ---------------------------------------------------------------------------
# State transitions: fix actions and scans
# ---------------------------------------------------------------------------


def _first_recommended_action():
    for anomaly in client.get("/api/anomalies").json()["items"]:
        for action in anomaly["actions"]:
            if action["status"] == "recommended":
                return anomaly, action
    pytest.fail("The seeded dataset must include a recommended action")


def test_apply_action_transitions_status_and_writes_audit():
    anomaly, action = _first_recommended_action()
    response = client.post(f"/api/anomalies/{anomaly['id']}/actions/{action['id']}/apply")
    assert response.status_code == 200
    payload = response.json()
    applied = next(item for item in payload["anomaly"]["actions"] if item["id"] == action["id"])
    assert applied["status"] == "applied"
    assert payload["audit"]["event"] in {"fix_action_applied", "anomaly_resolved"}
    # Approving every control on the finding closes the loop: the source data is
    # corrected, the finding resolves, and the outcome ledger records the value.
    for remaining in payload["anomaly"]["actions"]:
        client.post(f"/api/anomalies/{anomaly['id']}/actions/{remaining['id']}/apply")
    resolved = client.get(f"/api/anomalies/{anomaly['id']}").json()
    assert resolved["status"] == "resolved"
    audit_events = client.get("/api/audit").json()["items"]
    assert any(item["event"] in {"fix_action_applied", "anomaly_resolved"} and item.get("action_id") == action["id"] for item in audit_events)
    outcomes = client.get("/api/outcomes").json()
    assert outcomes["summary"]["fixes_applied"] >= 1
    assert outcomes["summary"]["value_protected"] >= anomaly["impact"]
    assert any(item["kind"] == "fix" and item.get("anomaly_id") == anomaly["id"] for item in outcomes["items"])
    # Applying the same action twice stays idempotent rather than erroring.
    assert client.post(f"/api/anomalies/{anomaly['id']}/actions/{action['id']}/apply").status_code == 200


def test_resolved_finding_stays_gone_after_rescan():
    resolved_ids = [item["id"] for item in client.get("/api/anomalies").json()["items"] if item["status"] == "resolved"]
    assert resolved_ids, "Previous test resolved a finding"
    client.post("/api/scan")
    items = client.get("/api/anomalies").json()["items"]
    survivors = {item["id"]: item["status"] for item in items if item["id"] in resolved_ids}
    assert all(status == "resolved" for status in survivors.values()), "Remediated defects must not be re-detected as open"


# ---------------------------------------------------------------------------
# Live incident injection and escalation previews
# ---------------------------------------------------------------------------


def test_inject_incident_is_discovered_by_detection():
    # Clear the seeded dispatch findings first: detection reports one finding per
    # type, so the injected defect is only visible once the seeded one is gone.
    for anomaly in client.get("/api/anomalies").json()["items"]:
        if anomaly["type"] == "Dispatch readiness" and anomaly["status"] != "resolved":
            for action in anomaly["actions"]:
                client.post(f"/api/anomalies/{anomaly['id']}/actions/{action['id']}/apply")
    client.post("/api/scan")
    open_capacity = [item for item in client.get("/api/anomalies").json()["items"] if item["status"] != "resolved" and "capacity" in item["title"].lower()]
    assert not open_capacity, "Remediation should have cleared the seeded overload"

    response = client.post("/api/demo/inject", params={"type": "overload"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["injected"] is True
    assert payload["incident"]["type"] == "overload"
    reopened = [item for item in client.get("/api/anomalies").json()["items"] if item["status"] != "resolved" and "capacity" in item["title"].lower()]
    assert reopened, "The injected overload must be rediscovered by the scan"
    assert client.post("/api/demo/inject", params={"type": "nonsense"}).status_code == 422


def test_injected_incident_can_be_fixed_and_stays_fixed():
    target = next(item for item in client.get("/api/anomalies").json()["items"] if item["status"] != "resolved" and "capacity" in item["title"].lower())
    for action in target["actions"]:
        client.post(f"/api/anomalies/{target['id']}/actions/{action['id']}/apply")
    client.post("/api/scan")
    assert client.get(f"/api/anomalies/{target['id']}").json()["status"] == "resolved"


def test_escalations_preview_covers_open_critical_and_high():
    payload = client.get("/api/escalations").json()
    open_items = [item for item in client.get("/api/anomalies").json()["items"] if item["status"] != "resolved" and item["severity"] in {"critical", "high"}]
    assert len(payload["items"]) == len(open_items)
    if payload["items"]:
        first = payload["items"][0]
        assert first["subject"].startswith(("[CRITICAL]", "[HIGH]"))
        assert "€" in first["body"]


def test_storm_injects_multiple_incidents():
    response = client.post("/api/demo/storm", params={"count": 3})
    assert response.status_code == 200
    payload = response.json()
    assert payload["injected"] is True
    assert len(payload["incidents"]) >= 2, "A storm should break several distinct record types"
    assert len({item["type"] for item in payload["incidents"]}) == len(payload["incidents"])


def test_demo_reset_regenerates_a_clean_board():
    response = client.post("/api/demo/reset")
    assert response.status_code == 200
    payload = response.json()
    assert payload["reset"] is True
    assert payload["findings"] > 0, "A fresh twin must rediscover its seeded defects"
    outcomes = client.get("/api/outcomes").json()
    assert outcomes["summary"] == {"value_protected": 0, "fixes_applied": 0, "anomalies_resolved": 0, "documents_ingested": 0}
    items = client.get("/api/anomalies").json()["items"]
    assert all(item["status"] != "resolved" for item in items)
    dashboard = client.get("/api/dashboard").json()
    assert next(metric["value"] for metric in dashboard["metrics"] if metric["label"] == "Cascades contained") == 0


def test_replenishment_gap_is_detected_and_fix_raises_a_po():
    def open_replenishment():
        return next((item for item in client.get("/api/anomalies").json()["items"] if item["type"] == "Replenishment risk" and item["status"] != "resolved"), None)

    finding = open_replenishment()
    if finding is None:
        # Earlier tests may have resolved the seeded gap; inject a fresh one.
        assert client.post("/api/demo/inject", params={"type": "replenish"}).json()["injected"] is True
        finding = open_replenishment()
    assert finding is not None, "A below-reorder-point gap must be detectable"
    assert "no inbound PO" in finding["title"]
    assert any(evidence["label"] == "Reorder point" for evidence in finding["evidence"])
    # Approving the control raises a covering PO, which resolves the finding
    # and keeps it resolved after a rescan (the detector sees the new coverage).
    for action in finding["actions"]:
        client.post(f"/api/anomalies/{finding['id']}/actions/{action['id']}/apply")
    resolved = client.get(f"/api/anomalies/{finding['id']}").json()
    assert resolved["status"] == "resolved"
    client.post("/api/scan")
    assert client.get(f"/api/anomalies/{finding['id']}").json()["status"] == "resolved"


def test_incident_report_downloads_as_markdown():
    anomaly = client.get("/api/anomalies").json()["items"][0]
    response = client.get(f"/api/anomalies/{anomaly['id']}/report")
    assert response.status_code == 200
    assert "text/markdown" in response.headers["content-type"]
    assert "attachment" in response.headers["content-disposition"]
    body = response.text
    assert body.startswith(f"# Incident report — {anomaly['id']}")
    for heading in ("## Summary", "## Verified evidence", "## Controls and approvals", "## Audit trail"):
        assert heading in body
    assert client.get("/api/anomalies/AN-0000/report").status_code == 404


# ---------------------------------------------------------------------------
# Value-ledger accounting invariant
# ---------------------------------------------------------------------------


def test_value_ledger_reconciles_with_dashboard():
    """Exposure at risk + value protected must equal the board's total exposure.

    Partial applies contribute €0; only resolution rows carry a finding's impact,
    exactly once — so the two pages are two views of one ledger.
    """
    anomalies = client.get("/api/anomalies").json()["items"]
    board_total = sum(item["impact"] for item in anomalies)
    outcomes = client.get("/api/outcomes").json()
    dashboard = client.get("/api/dashboard").json()
    exposure_at_risk = next(metric["value"] for metric in dashboard["metrics"] if metric["label"] == "Exposure at risk")
    assert exposure_at_risk + outcomes["summary"]["value_protected"] == board_total
    # Contained on the dashboard agrees with resolved rows in the ledger.
    contained = next(metric["value"] for metric in dashboard["metrics"] if metric["label"] == "Cascades contained")
    resolution_rows = [item for item in outcomes["items"] if item["kind"] == "fix" and item["saved"] > 0]
    assert contained == len(resolution_rows) == outcomes["summary"]["anomalies_resolved"]
    # No finding contributes more than its own impact.
    impacts = {item["id"]: item["impact"] for item in anomalies}
    for row in resolution_rows:
        assert row["saved"] <= impacts.get(row.get("anomaly_id"), 0) or row.get("anomaly_id") not in impacts


def test_scan_preserves_applied_action_status():
    anomaly, action = _first_recommended_action()
    client.post(f"/api/anomalies/{anomaly['id']}/actions/{action['id']}/apply")
    before = client.get("/api/dashboard").json()["scan_count"]
    scan = client.post("/api/scan")
    assert scan.status_code == 200
    assert scan.json()["findings"] > 0
    assert client.get("/api/dashboard").json()["scan_count"] == before + 1
    rescanned = client.get(f"/api/anomalies/{anomaly['id']}").json()
    re_action = next(item for item in rescanned["actions"] if item["id"] == action["id"])
    assert re_action["status"] == "applied", "Scans must not reset operator-applied controls"


# ---------------------------------------------------------------------------
# Chat mesh (deterministic fallback — no API key in tests)
# ---------------------------------------------------------------------------


def test_chat_falls_back_to_evidence_when_no_key():
    response = client.post("/api/chat", json={"message": "What needs attention first?"})
    assert response.status_code == 200
    assert response.json()["source"] == "nexus_deterministic"
    assert len(response.json()["agent_trace"]) == 6


def test_chat_stream_emits_trace_and_done_events():
    with client.stream("POST", "/api/chat/stream", json={"message": "What needs attention first?"}) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())
    assert "event: trace" in body
    assert "event: delta" in body
    assert "event: done" in body


def test_chat_rejects_invalid_payloads():
    assert client.post("/api/chat", json={"message": ""}).status_code == 422
    assert client.post("/api/chat", json={}).status_code == 422


def test_deterministic_mesh_survives_empty_board():
    class EmptyStore:
        def anomalies(self, **kwargs):
            return []

        def anomaly(self, anomaly_id):
            return None

        def knowledge_context(self, query):
            return []

    response = deterministic_mesh(ChatRequest(message="Anything urgent?"), EmptyStore())
    assert response.source == "nexus_deterministic"
    assert response.cited_anomaly_ids == []
    assert "No active findings" in response.answer


# ---------------------------------------------------------------------------
# Documents: listing, upload inspection, previews
# ---------------------------------------------------------------------------


def test_documents_and_agent_architecture_are_exposed():
    documents = client.get("/api/documents")
    architecture = client.get("/api/agents/architecture")
    assert documents.status_code == 200
    assert documents.json()["summary"]["source_documents"] > 0
    assert architecture.status_code == 200
    assert architecture.json()["model"], "The architecture endpoint must state its model"
    assert len(architecture.json()["specialists"]) == 5


def test_document_inspect_indexes_and_flags_missing_evidence():
    content = b"Delivery note for batch B-000. No release attachments included."
    response = client.post("/api/documents/inspect", files={"file": ("delivery_note.txt", content, "text/plain")})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "attention", "A note without PPAP/VDA evidence must be flagged"
    assert any(item["field"] == "PPAP approval" for item in payload["mismatches"])
    stored = client.get(f"/api/documents/{payload['document_id']}")
    assert stored.status_code == 200
    assert stored.json()["status"] == "attention"


def test_document_inspect_rejects_oversized_files():
    response = client.post("/api/documents/inspect", files={"file": ("big.txt", b"x" * 5_000_001, "text/plain")})
    assert response.status_code == 413


def test_document_preview_missing_returns_404():
    documents = client.get("/api/documents").json()["items"]
    source_doc = next((item for item in documents if item["status"] == "source"), None)
    if source_doc is None:
        pytest.skip("No generated source document available")
    assert client.get(f"/api/documents/{source_doc['id']}/preview").status_code == 404


# ---------------------------------------------------------------------------
# Startup persistence: the trained model must be reloaded, not retrained
# ---------------------------------------------------------------------------


def test_ml_scores_are_persisted_with_the_run():
    loaded = store.repository.load_run()
    assert loaded is not None
    ml_metadata = loaded["run"].metadata_json.get("ml_model", {})
    assert ml_metadata.get("inventory_scores"), "Persisted runs must carry ML scores so boots skip retraining"
    assert len(ml_metadata["inventory_scores"]) == len(store._dataset.inventory)


def test_remediation_is_scoped_to_one_finding():
    """Fixing one finding must not silently repair or vaporize a same-type sibling."""
    client.post("/api/demo/reset")
    items = client.get("/api/anomalies").json()["items"]
    master_data = [item for item in items if item["type"] == "Master data conflict" and item["status"] != "resolved"]
    assert len(master_data) >= 2, "Seeded board has fitment + weight findings of the same type"
    target, sibling = master_data[0], master_data[1]
    for action in target["actions"]:
        client.post(f"/api/anomalies/{target['id']}/actions/{action['id']}/apply")
    client.post("/api/scan")
    after = {item["id"]: item["status"] for item in client.get("/api/anomalies").json()["items"]}
    assert after.get(target["id"]) == "resolved"
    assert after.get(sibling["id"]) == "open", "The sibling finding must survive with its own defect intact"


def test_reinjected_entity_starts_with_fresh_actions():
    """A resolved entity re-broken by injection must not inherit 'applied' action flags."""
    for anomaly in client.get("/api/anomalies").json()["items"]:
        if anomaly["type"] == "Dispatch readiness" and anomaly["status"] != "resolved":
            for action in anomaly["actions"]:
                client.post(f"/api/anomalies/{anomaly['id']}/actions/{action['id']}/apply")
    client.post("/api/scan")
    response = client.post("/api/demo/inject", params={"type": "overload"}).json()
    assert response["injected"] is True
    assert response["new_findings"], "Re-broken entity must be reported as a new finding even if its ID was seen before"
    fresh = client.get(f"/api/anomalies/{response['new_findings'][0]['id']}").json()
    assert fresh["status"] == "open"
    assert all(action["status"] == "recommended" for action in fresh["actions"]), "Fresh incarnation must not inherit applied flags"


def test_injected_findings_survive_in_database():
    """Live-injected findings must be inserted (not just updated) so restarts keep them."""
    from app.db import AnomalyModel
    from sqlalchemy import select as sa_select
    response = client.post("/api/demo/inject", params={"type": "weight"}).json()
    assert response["injected"] is True and response["new_findings"]
    injected_id = response["new_findings"][0]["id"]
    with store.repository.session() as session:
        row = session.scalar(sa_select(AnomalyModel).where(AnomalyModel.anomaly_id == injected_id))
    assert row is not None, "persist_anomalies must INSERT findings born after boot"
    assert row.status == "open"
