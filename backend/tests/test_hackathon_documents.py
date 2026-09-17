import threading
from pathlib import Path

from app.services.hackathon_adapter import convert_findings_to_anomalies
from app.services.hackathon_detectors import run_all_detectors
from app.services.hackathon_ingest import load_hackathon_workbook
from app.services.operations import OperationsStore


ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "backend" / "datasets" / "Warehouse_AI_Hackathon_Synthetic_Dataset_FINAL 2.xlsx"
FIXTURES = ROOT / "test-fixtures" / "hackathon-document-control"


def _hackathon_store() -> OperationsStore:
    store = object.__new__(OperationsStore)
    workbook = load_hackathon_workbook(DATASET)
    store._lock = threading.RLock()
    store._hackathon_loaded = True
    store._hackathon_wb_data = workbook
    store._anomalies = convert_findings_to_anomalies(run_all_detectors(workbook))
    return store


def test_hackathon_document_links_x1_across_official_sheets():
    store = _hackathon_store()
    result = store.inspect_document("01_orphan_material_x1.txt", (FIXTURES / "01_orphan_material_x1.txt").read_text())

    assert result.source_dataset == "SAP Hackathon six-sheet workbook"
    assert result.status == "attention"
    assert "HAC-X1-MAT-999001-0" in result.related_anomaly_ids
    assert {record["sheet"] for record in result.linked_records} >= {"Inventory_Stock", "Warehouse_Bin", "Deliveries_Dispatch"}


def test_hackathon_document_clean_record_has_no_legacy_release_warning():
    store = _hackathon_store()
    result = store.inspect_document("05_clean_material.txt", (FIXTURES / "05_clean_material.txt").read_text())

    assert result.status == "clean"
    assert result.related_anomaly_ids == []
    assert {record["sheet"] for record in result.linked_records} >= {"Material_Master", "Inventory_Stock"}


def test_hackathon_document_without_identifier_requests_a_link():
    store = _hackathon_store()
    result = store.inspect_document("06_missing_identifier.txt", (FIXTURES / "06_missing_identifier.txt").read_text())

    assert result.status == "attention"
    assert result.linked_records == []
    assert result.mismatches[0]["field"] == "Hackathon record link"
