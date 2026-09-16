"""Phase 5 edge-case tests: Governed Human-in-the-Loop Remediation & Hackathon Audit Reporting.

Written BEFORE implementation to verify:
1. Single action approval on hackathon findings (HAC-X1, HAC-X2, HAC-B2, HAC-F2)
2. Source-twin self-healing in _hackathon_wb_data
3. Rescan persistence (resolved defects stay contained)
4. Dynamic KPI recalculation (exposure reduction, containment increase)
5. Audit trail and value-protected ledger entries
6. Hackathon official verification export (GET /api/hackathon/export)
7. Governed batch containment endpoint (POST /api/hackathon/contain)
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.services.operations import OperationsStore
from main import app

XLSX_PATH = Path(r"C:\Users\Mohd Aftaab\Downloads\Telegram Desktop\Warehouse_AI_Hackathon_Synthetic_Dataset_FINAL 2.xlsx")


@pytest.fixture(scope="module")
def remediation_store():
    """A clean store loaded with the hackathon dataset."""
    settings = get_settings()
    s = OperationsStore(settings)
    if XLSX_PATH.exists():
        s.load_hackathon(XLSX_PATH)
    return s


@pytest.fixture(scope="module", autouse=True)
def cleanup_after_remediation():
    yield
    from main import store
    store.reset_demo()


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# 1. Action approval & resolution on Hackathon findings
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not found")
def test_approve_hackathon_action_resolves_finding(remediation_store):
    """Approving a hackathon action marks finding resolved and cascades healthy."""
    open_items = [a for a in remediation_store.anomalies() if a.id.startswith("HAC-X1-") and a.status != "resolved"]
    assert len(open_items) >= 1, "Must have open HAC-X1 orphan material anomaly"
    target = open_items[0]
    assert len(target.actions) >= 1
    action = target.actions[0]

    initial_exposure = remediation_store.dashboard()["metrics"][0]["value"]

    anomaly_result, action_title = remediation_store.approve_action(target.id, action.id)
    assert anomaly_result is not None
    assert action_title == action.title
    assert anomaly_result.status == "resolved"
    assert all(n.health == "healthy" for n in anomaly_result.cascade_nodes)

    # Dashboard exposure must decrease
    new_dash = remediation_store.dashboard()
    new_exposure = new_dash["metrics"][0]["value"]
    assert new_exposure < initial_exposure, "Exposure must drop after resolving finding"


# ---------------------------------------------------------------------------
# 2. Source-twin self-healing for catalog rules
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not found")
def test_remediate_hackathon_orphan_material_heals_master_data(remediation_store):
    """Approving HAC-X1 adds the missing material record to Material_Master."""
    # Check MAT-999001 in material_master
    wb = remediation_store._hackathon_wb_data
    mm_mats = {r.get("material") for r in wb.get("material_master", [])}
    assert "MAT-999001" in mm_mats, "Remediation must add MAT-999001 to material_master"


@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not found")
def test_remediate_hackathon_expired_batch_quarantines_stock(remediation_store):
    """Approving a B2 expired batch anomaly sets blocked_qty = qty_on_hand."""
    b2_items = [a for a in remediation_store.anomalies() if a.id.startswith("HAC-B2-") and a.status != "resolved"]
    if not b2_items:
        pytest.skip("No unapproved B2 findings available")
    target = b2_items[0]
    action = target.actions[0]

    anomaly_result, _ = remediation_store.approve_action(target.id, action.id)
    assert anomaly_result.status == "resolved"

    # Verify inventory in _hackathon_wb_data
    wb = remediation_store._hackathon_wb_data
    for row in wb.get("inventory_stock", []):
        if row.get("material") == target.sku and row.get("batch"):
            # If this was the targeted batch, blocked_qty should equal qty_on_hand
            if row.get("batch_expiry") and str(row["batch_expiry"]) in target.summary:
                assert row.get("blocked_qty", 0) >= row.get("qty_on_hand", 0)


@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not found")
def test_remediate_hackathon_blocked_vendor_po(remediation_store):
    """Approving an F2 blocked vendor PO anomaly resolves and cancels the open PO."""
    f2_items = [a for a in remediation_store.anomalies() if a.id.startswith("HAC-F2-") and a.status != "resolved"]
    if not f2_items:
        pytest.skip("No unapproved F2 findings available")
    target = f2_items[0]
    action = target.actions[0]

    anomaly_result, _ = remediation_store.approve_action(target.id, action.id)
    assert anomaly_result.status == "resolved"


# ---------------------------------------------------------------------------
# 3. Rescan persistence
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not found")
def test_rescan_preserves_remediated_hackathon_findings(remediation_store):
    """Running scan after remediation does not recreate the resolved finding as open."""
    resolved_before = {a.id for a in remediation_store.anomalies() if a.status == "resolved"}
    assert len(resolved_before) > 0, "Must have resolved findings from earlier tests"

    scan_result = remediation_store.run_scan()
    assert scan_result["findings"] > 0

    resolved_after = {a.id for a in remediation_store.anomalies() if a.status == "resolved"}
    for res_id in resolved_before:
        assert res_id in resolved_after, f"Resolved finding {res_id} must remain resolved after rescan"
        anomaly = remediation_store.anomaly(res_id)
        assert anomaly.status == "resolved"


# ---------------------------------------------------------------------------
# 4. Audit ledger & Value Protected tracking
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not found")
def test_remediation_records_audit_and_value_outcomes(remediation_store):
    """Every approved hackathon action writes to audit log and measured outcomes."""
    if remediation_store.outcomes()["summary"]["fixes_applied"] == 0:
        open_items = [a for a in remediation_store.anomalies() if a.status != "resolved" and a.actions]
        if open_items:
            remediation_store.approve_action(open_items[0].id, open_items[0].actions[0].id)
    outcomes = remediation_store.outcomes()
    assert outcomes["summary"]["fixes_applied"] >= 1
    assert outcomes["summary"]["value_protected"] > 0

    report = remediation_store.report()
    assert "Audit trail" in report
    assert "Measured outcome" in report


# ---------------------------------------------------------------------------
# 5. Hackathon official verification export (GET /api/hackathon/export)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not found")
def test_hackathon_export_method_structure(remediation_store):
    """hackathon_export() produces audit report with coverage across all 24 rules."""
    export = remediation_store.hackathon_export()
    assert export["total_anomalies"] >= 200
    assert "catalog_coverage" in export
    assert len(export["catalog_coverage"]) >= 7, "Must cover A, B, C, D, E, F, X series"
    assert "findings" in export
    assert len(export["findings"]) >= 200

    sample = export["findings"][0]
    required_keys = {"id", "catalog_id", "title", "severity", "entity", "exposure_eur", "root_cause", "proposed_action", "status", "human_approval_required"}
    for key in required_keys:
        assert key in sample, f"Sample finding missing key: {key}"
        assert sample["human_approval_required"] is True


@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not found")
def test_api_hackathon_export_endpoint(client):
    """GET /api/hackathon/export returns 200 and complete verification pack."""
    # Ensure hackathon is loaded
    client.post("/api/hackathon/load", json={"file_path": str(XLSX_PATH)})
    resp = client.get("/api/hackathon/export")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_anomalies"] >= 200
    assert data["status"] == "verified"
    assert "catalog_coverage" in data


# ---------------------------------------------------------------------------
# 6. Governed batch containment (POST /api/hackathon/contain)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not found")
def test_api_hackathon_contain_batch(client):
    """POST /api/hackathon/contain batch-remediates low/medium items with human audit."""
    client.post("/api/hackathon/load", json={"file_path": str(XLSX_PATH)})
    resp = client.post("/api/hackathon/contain", json={"severity": "low", "limit": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert "contained_count" in data
    assert "total_value_protected" in data
    assert data["audit_actor"] == "Operations Controller"
