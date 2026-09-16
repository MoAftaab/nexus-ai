"""Cross-system correlation tests (X1 orphan materials, X2 ATP deficit)."""
from __future__ import annotations

from datetime import date
from pathlib import Path
import pytest

from app.services.hackathon_ingest import load_hackathon_workbook
from app.services.hackathon_detectors import (
    SNAPSHOT_DATE,
    detect_x1_orphan_material,
    detect_x2_dispatch_exceeds_atp,
)

XLSX_PATH = Path(r"C:\Users\Mohd Aftaab\Downloads\Telegram Desktop\Warehouse_AI_Hackathon_Synthetic_Dataset_FINAL 2.xlsx")


def _mm(**kw):
    base = {"material": "MAT-001", "description": "T", "material_type": "FERT",
            "material_group": "G", "base_uom": "EA", "plant": "1010",
            "reorder_point": 100.0, "safety_stock": 50.0, "lead_time_days": 5.0,
            "abc_class": "A", "hazmat_flag": "N", "lifecycle_status": "ACTIVE"}
    base.update(kw)
    return base


def _inv(**kw):
    base = {"material": "MAT-001", "plant": "1010", "storage_location": "0001",
            "batch": None, "uom": "EA", "qty_on_hand": 100.0, "blocked_qty": 0.0,
            "in_transit_qty": 0.0, "batch_expiry": None,
            "last_movement_date": date(2026, 8, 1)}
    base.update(kw)
    return base


def _bin(**kw):
    base = {"bin": "WH1-A01-1", "storage_type": "SHELF", "assigned_material": "MAT-001",
            "capacity": 500.0, "occupied": 100.0, "bin_status": "OCC", "plant": "1010"}
    base.update(kw)
    return base


def _dlv(**kw):
    base = {"delivery": "DLV-001", "material": "MAT-001", "plant": "1010",
            "order_qty": 50.0, "ship_to": "CUST-001", "route": "R-NORTH",
            "created_date": date(2026, 8, 1),
            "planned_gi_date": date(2026, 9, 10), "status": "OPEN"}
    base.update(kw)
    return base


# ----- X1: Orphan Material ---------------------------------------------

def test_x1_orphan_in_all_three_sheets_critical():
    mm = [_mm(material="MAT-001")]
    inv = [_inv(material="MAT-999")]
    bins = [_bin(assigned_material="MAT-999")]
    dlv = [_dlv(material="MAT-999")]
    findings = detect_x1_orphan_material(mm, inv, bins, dlv)
    assert len(findings) == 1
    f = findings[0]
    assert f["material"] == "MAT-999"
    assert f["severity"] == "critical"
    assert f["sheet_count"] == 3


def test_x1_partial_orphan_in_one_sheet_medium():
    mm = [_mm(material="MAT-001")]
    inv = [_inv(material="MAT-ORF")]
    findings = detect_x1_orphan_material(mm, inv, [], [])
    assert len(findings) == 1
    assert findings[0]["severity"] == "medium"


def test_x1_no_orphan_clean_data():
    mm = [_mm(material="MAT-001")]
    inv = [_inv(material="MAT-001")]
    assert detect_x1_orphan_material(mm, inv, [], []) == []


def test_x1_multiple_orphans_all_detected():
    mm = [_mm(material="MAT-001")]
    inv = [_inv(material="MAT-AAA"), _inv(material="MAT-BBB")]
    findings = detect_x1_orphan_material(mm, inv, [], [])
    orphan_mats = {f["material"] for f in findings}
    assert {"MAT-AAA", "MAT-BBB"} == orphan_mats


# ----- X2: Dispatch Exceeds ATP Stock ----------------------------------

def test_x2_single_delivery_exceeds_atp():
    mm = [_mm(material="MAT-001", plant="1010")]
    inv = [_inv(material="MAT-001", plant="1010", qty_on_hand=50.0)]
    dlv = [_dlv(material="MAT-001", plant="1010", order_qty=80.0, status="OPEN")]
    findings = detect_x2_dispatch_exceeds_atp(mm, inv, dlv)
    assert len(findings) == 1
    f = findings[0]
    assert f["shortfall"] == pytest.approx(30.0)
    assert f["severity"] == "critical"


def test_x2_cumulative_deficit_across_two_deliveries():
    mm = [_mm(material="MAT-001", plant="1010")]
    inv = [_inv(material="MAT-001", plant="1010", qty_on_hand=100.0)]
    dlv = [
        _dlv(delivery="DLV-001", material="MAT-001", plant="1010", order_qty=80.0, status="OPEN"),
        _dlv(delivery="DLV-002", material="MAT-001", plant="1010", order_qty=80.0, status="OPEN"),
    ]
    findings = detect_x2_dispatch_exceeds_atp(mm, inv, dlv)
    assert len(findings) == 1
    f = findings[0]
    assert f["shortfall"] == pytest.approx(60.0)
    assert f["delivery_count"] == 2


def test_x2_blocked_stock_excluded_from_atp():
    mm = [_mm(material="MAT-001", plant="1010")]
    inv = [_inv(material="MAT-001", plant="1010", qty_on_hand=100.0, blocked_qty=40.0)]
    dlv = [_dlv(material="MAT-001", plant="1010", order_qty=70.0, status="OPEN")]
    findings = detect_x2_dispatch_exceeds_atp(mm, inv, dlv)
    assert len(findings) == 1
    assert findings[0]["net_atp"] == pytest.approx(60.0)
    assert findings[0]["shortfall"] == pytest.approx(10.0)


def test_x2_expired_stock_excluded_from_atp():
    mm = [_mm(material="MAT-001", plant="1010")]
    expired = date(2026, 8, 1)
    inv = [_inv(material="MAT-001", plant="1010", qty_on_hand=100.0, blocked_qty=0.0,
               batch_expiry=expired)]
    dlv = [_dlv(material="MAT-001", plant="1010", order_qty=50.0, status="OPEN")]
    findings = detect_x2_dispatch_exceeds_atp(mm, inv, dlv)
    assert len(findings) == 1
    assert findings[0]["net_atp"] == pytest.approx(0.0)


def test_x2_sufficient_stock_no_finding():
    mm = [_mm(material="MAT-001", plant="1010")]
    inv = [_inv(material="MAT-001", plant="1010", qty_on_hand=200.0)]
    dlv = [_dlv(material="MAT-001", plant="1010", order_qty=50.0, status="OPEN")]
    assert detect_x2_dispatch_exceeds_atp(mm, inv, dlv) == []


def test_x2_delivered_order_not_counted_in_demand():
    mm = [_mm(material="MAT-001", plant="1010")]
    inv = [_inv(material="MAT-001", plant="1010", qty_on_hand=30.0)]
    dlv = [_dlv(material="MAT-001", plant="1010", order_qty=80.0, status="DELIVERED")]
    assert detect_x2_dispatch_exceeds_atp(mm, inv, dlv) == []


# ----- Live workbook integration ----------------------------------------

@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not present")
def test_live_x1_orphan_mat_999001_detected():
    wb = load_hackathon_workbook(XLSX_PATH)
    findings = detect_x1_orphan_material(
        wb["material_master"], wb["inventory_stock"],
        wb["warehouse_bin"], wb["deliveries_dispatch"],
    )
    orphan_mats = {f["material"] for f in findings}
    assert "MAT-999001" in orphan_mats, "Seeded orphan MAT-999001 must be detected"


@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not present")
def test_live_x1_mat_999001_is_critical():
    wb = load_hackathon_workbook(XLSX_PATH)
    findings = detect_x1_orphan_material(
        wb["material_master"], wb["inventory_stock"],
        wb["warehouse_bin"], wb["deliveries_dispatch"],
    )
    for f in findings:
        if f["material"] == "MAT-999001":
            assert f["severity"] == "critical", "MAT-999001 appears in 3 sheets — must be critical"
            assert f["sheet_count"] >= 2
            return
    pytest.fail("MAT-999001 not found in X1 findings")


@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not present")
def test_live_x2_at_least_one_atp_shortfall():
    wb = load_hackathon_workbook(XLSX_PATH)
    findings = detect_x2_dispatch_exceeds_atp(
        wb["material_master"], wb["inventory_stock"], wb["deliveries_dispatch"]
    )
    assert len(findings) >= 1, "At least one delivery should exceed ATP stock"
