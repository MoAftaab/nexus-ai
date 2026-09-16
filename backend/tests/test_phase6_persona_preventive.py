"""Phase 6 edge-case tests: Multi-Persona Role Filtering, Preventive Risk Prediction, and WALT Persona Guidance.

Written BEFORE implementation to verify:
1. Persona filtering for Dispatcher (D-series + X2 ATP deficits)
2. Persona filtering for Inventory Controller (B-series stock + C-series bins)
3. Persona filtering for Master Data Steward (A-series + X1 orphan material)
4. Persona filtering for Procurement Lead (E-series POs + F-series vendor compliance)
5. Default / operations_lead returns full 209-anomaly portfolio
6. API endpoint GET /api/anomalies?persona=...
7. Preventive intelligence engine analyzing near-breach records (Section 3.3 bonus)
8. API endpoint GET /api/hackathon/preventive
9. WALT Copilot persona query resolution
"""
from __future__ import annotations

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.services.operations import OperationsStore
from main import app

XLSX_PATH = Path(r"C:\Users\Mohd Aftaab\Downloads\Telegram Desktop\Warehouse_AI_Hackathon_Synthetic_Dataset_FINAL 2.xlsx")


@pytest.fixture(scope="module")
def persona_store():
    """A clean store loaded with the hackathon dataset."""
    settings = get_settings()
    s = OperationsStore(settings)
    if XLSX_PATH.exists():
        s.load_hackathon(XLSX_PATH)
    return s


@pytest.fixture(scope="module", autouse=True)
def cleanup_after_tests():
    yield
    from main import store
    store.reset_demo()


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# 1. Multi-Persona Filtering
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not found")
def test_dispatcher_persona_filters_dispatch_and_atp_anomalies(persona_store):
    """Dispatcher sees only outbound deliveries, overdue GI, routes, and ATP shortfalls."""
    items = persona_store.anomalies(persona="dispatcher")
    assert len(items) > 0, "Dispatcher worklist must not be empty"
    allowed_catalog = {"D2", "D3", "D5", "X2"}
    for item in items:
        parts = item.id.split("-")
        cat = parts[1] if len(parts) >= 2 else ""
        assert cat in allowed_catalog, f"Unexpected item for dispatcher: {item.id} (catalog: {cat})"


@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not found")
def test_inventory_controller_persona_filters_stock_and_bin_anomalies(persona_store):
    """Inventory Controller sees stock integrity and warehouse bin allocations."""
    items = persona_store.anomalies(persona="inventory_controller")
    assert len(items) > 0, "Inventory Controller worklist must not be empty"
    allowed_catalog = {"B1", "B2", "B4", "B5", "C1", "C2", "C4"}
    for item in items:
        parts = item.id.split("-")
        cat = parts[1] if len(parts) >= 2 else ""
        assert cat in allowed_catalog, f"Unexpected item for inventory controller: {item.id} (catalog: {cat})"


@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not found")
def test_master_data_steward_persona_filters_master_data_and_orphan(persona_store):
    """Master Data Steward sees UoM, reorder/safety stock, and orphan materials."""
    items = persona_store.anomalies(persona="master_data_steward")
    assert len(items) > 0, "Master Data Steward worklist must not be empty"
    allowed_catalog = {"A1", "A2", "A3", "A4", "A5", "A6", "X1"}
    for item in items:
        parts = item.id.split("-")
        cat = parts[1] if len(parts) >= 2 else ""
        assert cat in allowed_catalog, f"Unexpected item for master data steward: {item.id} (catalog: {cat})"


@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not found")
def test_procurement_lead_persona_filters_po_and_vendor(persona_store):
    """Procurement Lead sees purchase replenishment and vendor compliance."""
    items = persona_store.anomalies(persona="procurement_lead")
    assert len(items) > 0, "Procurement Lead worklist must not be empty"
    allowed_catalog = {"E1", "E2", "E3", "E4", "F1", "F2"}
    for item in items:
        parts = item.id.split("-")
        cat = parts[1] if len(parts) >= 2 else ""
        assert cat in allowed_catalog, f"Unexpected item for procurement lead: {item.id} (catalog: {cat})"


@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not found")
def test_all_or_operations_lead_returns_full_portfolio(persona_store):
    """Operations Lead sees all 209 anomalies across all domains."""
    full = persona_store.anomalies()
    ops = persona_store.anomalies(persona="operations_lead")
    assert len(full) >= 200
    assert len(ops) == len(full)


# ---------------------------------------------------------------------------
# 2. API Endpoint Persona Filter
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not found")
def test_api_anomalies_supports_persona_query_param(client):
    """GET /api/anomalies?persona=dispatcher filters response to dispatcher scope."""
    client.post("/api/hackathon/load", json={"file_path": str(XLSX_PATH)})
    resp = client.get("/api/anomalies?persona=dispatcher")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) > 0
    for item in items:
        parts = item["id"].split("-")
        cat = parts[1] if len(parts) >= 2 else ""
        assert cat in {"D2", "D3", "D5", "X2"}


# ---------------------------------------------------------------------------
# 3. Preventive Intelligence Engine (Section 3.3 Bonus)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not found")
def test_hackathon_preventive_intelligence_engine(persona_store):
    """hackathon_preventive() surfaces near-breach signals before disruptions occur."""
    result = persona_store.hackathon_preventive()
    assert "total_preventive_signals" in result
    assert result["total_preventive_signals"] > 0
    assert "stockout_watch" in result
    assert "bin_saturation_watch" in result
    assert "batch_expiry_watch" in result
    assert "vendor_reliability_watch" in result


@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not found")
def test_api_hackathon_preventive_endpoint(client):
    """GET /api/hackathon/preventive returns 200 and preventive signal breakdown."""
    client.post("/api/hackathon/load", json={"file_path": str(XLSX_PATH)})
    resp = client.get("/api/hackathon/preventive")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "active"
    assert data["total_preventive_signals"] > 0


# ---------------------------------------------------------------------------
# 4. WALT Persona Query Grounding
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not found")
def test_walt_resolves_persona_priority_questions(client):
    """WALT answers role-targeted questions citing relevant verified evidence."""
    client.post("/api/hackathon/load", json={"file_path": str(XLSX_PATH)})
    login_resp = client.post(
        "/api/auth/signin",
        json={"email": "operator1@nexusai.demo", "password": "nexusai2026"},
    )
    headers = {"Authorization": f"Bearer {login_resp.json()['session_token']}"}
    resp = client.post("/api/chat", headers=headers, json={"message": "What should the Dispatcher prioritize today?"})
    assert resp.status_code == 200
    data = resp.json()
    answer = data["answer"]
    assert "Decision brief" in answer or "dispatch" in answer.lower() or "atp" in answer.lower()
    assert "recommendation" in answer.lower() or "human approval" in answer.lower()
