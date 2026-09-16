"""Edge case tests for OperationsStore hackathon integration and API endpoints (Phase 3)."""
from __future__ import annotations

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.services.operations import OperationsStore
from main import app

XLSX_PATH = Path(r"C:\Users\Mohd Aftaab\Downloads\Telegram Desktop\Warehouse_AI_Hackathon_Synthetic_Dataset_FINAL 2.xlsx")


@pytest.fixture(scope="module")
def clean_store():
    settings = get_settings()
    return OperationsStore(settings)


@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def clean_up_after_hackathon_tests():
    yield
    from main import store
    store.reset_demo()


@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not found")
def test_store_load_hackathon_from_valid_path(clean_store):
    """Loading the hackathon workbook updates store anomalies and flags."""
    stats = clean_store.load_hackathon(XLSX_PATH)
    assert stats["status"] == "loaded"
    assert stats["anomalies_count"] >= 200
    assert clean_store._hackathon_loaded is True
    assert len(clean_store._anomalies) >= 200


@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not found")
def test_store_dashboard_reflects_hackathon_data(clean_store):
    """Dashboard KPIs and severity breakdown match the hackathon anomalies."""
    clean_store.load_hackathon(XLSX_PATH)
    dash = clean_store.dashboard()

    metrics = {m["label"]: m for m in dash["metrics"]}
    assert "Exposure at risk" in metrics
    assert metrics["Exposure at risk"]["value"] > 1_000_000, "Hackathon exposure should exceed 1M"

    counts = dash["severity_counts"]
    assert counts["critical"] >= 70, f"Expected at least 70 critical, got {counts['critical']}"
    assert counts["high"] >= 50, f"Expected at least 50 high, got {counts['high']}"
    assert counts["medium"] >= 50, f"Expected at least 50 medium, got {counts['medium']}"


@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not found")
def test_store_anomalies_filtering_on_hackathon_data(clean_store):
    """Filter by severity and search terms (material, vendor)."""
    clean_store.load_hackathon(XLSX_PATH)

    critical_items = clean_store.anomalies(severity="critical")
    assert len(critical_items) >= 70
    assert all(item.severity == "critical" for item in critical_items)

    mat_results = clean_store.anomalies(search="MAT-999001")
    assert len(mat_results) >= 1
    assert any("MAT-999001" in item.sku or "MAT-999001" in item.title for item in mat_results)

    vend_results = clean_store.anomalies(search="VEND-9999")
    assert len(vend_results) >= 1
    assert any("VEND-9999" in item.summary or "VEND-9999" in item.title for item in vend_results)


@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not found")
def test_store_graph_generates_valid_cascade_for_hackathon_finding(clean_store):
    """Cascade graph for a hackathon anomaly contains valid DAG nodes and simulation."""
    clean_store.load_hackathon(XLSX_PATH)
    critical_items = clean_store.anomalies(severity="critical")
    assert len(critical_items) > 0
    target = critical_items[0]

    graph = clean_store.graph(target.id)
    assert graph["anomaly_id"] == target.id
    assert len(graph["nodes"]) >= 3, "Expected at least 3 nodes (Source, Process, Outcome)"
    assert len(graph["edges"]) >= 2
    assert "simulation" in graph
    assert graph["simulation"]["expected_impact"] > 0


def test_store_load_hackathon_missing_path_raises_file_not_found(clean_store):
    """Non-existent path raises FileNotFoundError."""
    bogus_path = Path("C:/non_existent_directory_12345/missing_dataset.xlsx")
    with pytest.raises(FileNotFoundError):
        clean_store.load_hackathon(bogus_path)


@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not found")
def test_api_hackathon_load_endpoint(test_client):
    """POST /api/hackathon/load switches active dataset to hackathon."""
    resp = test_client.post("/api/hackathon/load", json={"file_path": str(XLSX_PATH)})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "loaded"
    assert data["anomalies_count"] >= 200

    dash_resp = test_client.get("/api/dashboard")
    assert dash_resp.status_code == 200
    dash_data = dash_resp.json()
    assert dash_data["severity_counts"]["critical"] >= 70

    search_resp = test_client.get("/api/anomalies", params={"search": "MAT-999001"})
    assert search_resp.status_code == 200
    search_data = search_resp.json()
    assert search_data["total"] >= 1


@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not found")
def test_api_hackathon_status_endpoint(test_client):
    """GET /api/hackathon/status returns active state."""
    test_client.post("/api/hackathon/load", json={"file_path": str(XLSX_PATH)})
    resp = test_client.get("/api/hackathon/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["loaded"] is True
    assert data["anomalies_count"] >= 200


def test_api_hackathon_load_missing_file_returns_404(test_client):
    """POST /api/hackathon/load with invalid path returns 404."""
    resp = test_client.post("/api/hackathon/load", json={"file_path": "C:/invalid/bogus.xlsx"})
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not found")
def test_store_run_scan_preserves_hackathon_data(clean_store):
    """Running scan after hackathon load re-evaluates hackathon detectors."""
    clean_store.load_hackathon(XLSX_PATH)
    initial_count = len(clean_store._anomalies)

    scan_result = clean_store.run_scan()
    assert clean_store._hackathon_loaded is True
    assert len(clean_store._anomalies) == initial_count
    assert scan_result.get("anomalies_count", len(clean_store._anomalies)) == initial_count
