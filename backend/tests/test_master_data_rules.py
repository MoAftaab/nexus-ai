"""Master data anomaly detector tests (A1–A6) with edge cases."""
from __future__ import annotations

from datetime import date
from pathlib import Path
import pytest

from app.services.hackathon_ingest import load_hackathon_workbook
from app.services.hackathon_detectors import (
    detect_a1_missing_uom,
    detect_a2_invalid_reorder_point,
    detect_a3_duplicate_description,
    detect_a4_safety_gt_reorder,
    detect_a5_obsolete_in_use,
    detect_a6_hazmat_mismatch,
)

XLSX_PATH = Path(r"C:\Users\Mohd Aftaab\Downloads\Telegram Desktop\Warehouse_AI_Hackathon_Synthetic_Dataset_FINAL 2.xlsx")


def _mm(**kwargs):
    base = {"material": "MAT-X", "description": "Test", "material_type": "FERT",
            "material_group": "GRP", "base_uom": "EA", "plant": "1010",
            "reorder_point": 100.0, "safety_stock": 50.0, "lead_time_days": 5.0,
            "abc_class": "A", "hazmat_flag": "N", "lifecycle_status": "ACTIVE"}
    base.update(kwargs)
    return base


def _bin(**kwargs):
    base = {"bin": "WH1-A01-1", "storage_type": "HAZ", "assigned_material": "MAT-X",
            "capacity": 500.0, "occupied": 100.0, "bin_status": "OCC", "plant": "1010"}
    base.update(kwargs)
    return base


def _dlv(**kwargs):
    base = {"delivery": "DLV-001", "material": "MAT-X", "plant": "1010",
            "order_qty": 50.0, "ship_to": "CUST-001", "route": "R-NORTH",
            "created_date": date(2026, 8, 1), "planned_gi_date": date(2026, 8, 5),
            "status": "OPEN"}
    base.update(kwargs)
    return base


def _po(**kwargs):
    base = {"purchase_order": "PO-001", "material": "MAT-X", "vendor": "VEND-001",
            "plant": "1010", "po_qty": 100.0, "unit_price": 10.0, "currency": "EUR",
            "order_date": date(2026, 8, 1), "expected_delivery": date(2026, 8, 10),
            "po_status": "OPEN"}
    base.update(kwargs)
    return base


# --------------- A1: Missing Base UoM ------------------------------------

def test_md_a1_blank_uom():
    findings = detect_a1_missing_uom([_mm(base_uom=None)])
    assert len(findings) == 1
    assert findings[0]["catalog_id"] == "A1"
    assert findings[0]["severity"] == "high"


def test_md_a1_valid_uom_no_finding():
    assert detect_a1_missing_uom([_mm(base_uom="EA")]) == []


def test_md_a1_blank_on_obsolete_still_flagged():
    findings = detect_a1_missing_uom([_mm(base_uom=None, lifecycle_status="OBSOLETE")])
    assert len(findings) == 1


# --------------- A2: Invalid Reorder Point -------------------------------

def test_md_a2_negative_reorder():
    findings = detect_a2_invalid_reorder_point([_mm(reorder_point=-50.0)])
    assert len(findings) == 1
    assert findings[0]["catalog_id"] == "A2"


def test_md_a2_none_reorder():
    findings = detect_a2_invalid_reorder_point([_mm(reorder_point=None)])
    assert len(findings) == 1


def test_md_a2_zero_reorder_is_flagged():
    findings = detect_a2_invalid_reorder_point([_mm(reorder_point=0.0)])
    assert len(findings) == 0


def test_md_a2_valid_reorder_no_finding():
    assert detect_a2_invalid_reorder_point([_mm(reorder_point=100.0)]) == []


# --------------- A3: Duplicate Description -------------------------------

def test_md_a3_exact_duplicate():
    mm = [_mm(material="MAT-001", description="TRANS component 018"),
          _mm(material="MAT-002", description="TRANS component 018")]
    findings = detect_a3_duplicate_description(mm)
    assert len(findings) == 1
    assert "MAT-001" in findings[0]["duplicate_materials"]
    assert "MAT-002" in findings[0]["duplicate_materials"]


def test_md_a3_case_insensitive_detection():
    mm = [_mm(material="MAT-001", description="BRK-SYS component 002"),
          _mm(material="MAT-002", description="BRK-SYS Component 002")]
    findings = detect_a3_duplicate_description(mm)
    assert len(findings) == 1


def test_md_a3_unique_descriptions_no_finding():
    mm = [_mm(material="MAT-001", description="Part A"),
          _mm(material="MAT-002", description="Part B")]
    assert detect_a3_duplicate_description(mm) == []


# --------------- A4: Safety Stock > Reorder Point -----------------------

def test_md_a4_safety_gt_reorder():
    findings = detect_a4_safety_gt_reorder([_mm(safety_stock=120.0, reorder_point=100.0)])
    assert len(findings) == 1
    assert findings[0]["catalog_id"] == "A4"


def test_md_a4_boundary_equal_is_valid():
    assert detect_a4_safety_gt_reorder([_mm(safety_stock=100.0, reorder_point=100.0)]) == []


def test_md_a4_safety_lt_reorder_is_valid():
    assert detect_a4_safety_gt_reorder([_mm(safety_stock=80.0, reorder_point=100.0)]) == []


# --------------- A5: Obsolete / Blocked in use --------------------------

def test_md_a5_obsolete_in_open_delivery():
    mm = [_mm(material="MAT-OBS", lifecycle_status="OBSOLETE")]
    dlv = [_dlv(material="MAT-OBS", status="OPEN")]
    findings = detect_a5_obsolete_in_use(mm, dlv, [])
    assert len(findings) == 1
    assert findings[0]["severity"] == "critical"


def test_md_a5_obsolete_in_historical_delivery_no_finding():
    mm = [_mm(material="MAT-OBS", lifecycle_status="OBSOLETE")]
    dlv = [_dlv(material="MAT-OBS", status="DELIVERED")]
    findings = detect_a5_obsolete_in_use(mm, dlv, [])
    assert len(findings) == 0


def test_md_a5_blocked_in_open_po():
    mm = [_mm(material="MAT-BLK", lifecycle_status="BLOCKED")]
    po = [_po(material="MAT-BLK", po_status="OPEN")]
    findings = detect_a5_obsolete_in_use(mm, [], po)
    assert len(findings) == 1


def test_md_a5_active_material_no_finding():
    mm = [_mm(material="MAT-ACT", lifecycle_status="ACTIVE")]
    dlv = [_dlv(material="MAT-ACT", status="OPEN")]
    assert detect_a5_obsolete_in_use(mm, dlv, []) == []


# --------------- A6: Hazmat Handling Mismatch ---------------------------

def test_md_a6_hazmat_in_shelf():
    mm = [_mm(material="MAT-HAZ", hazmat_flag="Y")]
    bins = [_bin(assigned_material="MAT-HAZ", storage_type="SHELF")]
    findings = detect_a6_hazmat_mismatch(mm, bins)
    assert len(findings) == 1
    assert findings[0]["catalog_id"] == "A6"


def test_md_a6_hazmat_in_haz_bin_is_valid():
    mm = [_mm(material="MAT-HAZ", hazmat_flag="Y")]
    bins = [_bin(assigned_material="MAT-HAZ", storage_type="HAZ")]
    assert detect_a6_hazmat_mismatch(mm, bins) == []


def test_md_a6_non_hazmat_in_shelf_is_valid():
    mm = [_mm(material="MAT-STD", hazmat_flag="N")]
    bins = [_bin(assigned_material="MAT-STD", storage_type="SHELF")]
    assert detect_a6_hazmat_mismatch(mm, bins) == []


# --------------- Live workbook A-series integration ----------------------

@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not present")
def test_live_a1_at_least_one_missing_uom():
    wb = load_hackathon_workbook(XLSX_PATH)
    findings = detect_a1_missing_uom(wb["material_master"])
    assert len(findings) >= 1, "Workbook must contain at least one A1 finding (MAT-100002 has blank UoM)"


@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not present")
def test_live_a4_safety_gt_reorder_detected():
    wb = load_hackathon_workbook(XLSX_PATH)
    findings = detect_a4_safety_gt_reorder(wb["material_master"])
    assert len(findings) >= 1
