"""Inventory and warehouse bin anomaly tests (B1-B5, C1-C4)."""
from __future__ import annotations

from datetime import date
from pathlib import Path
import pytest

from app.services.hackathon_ingest import load_hackathon_workbook
from app.services.hackathon_detectors import (
    SNAPSHOT_DATE,
    detect_b1_negative_stock,
    detect_b2_expired_batch_with_stock,
    detect_b4_stale_stock,
    detect_b5_blocked_exceeds_on_hand,
    detect_c1_bin_over_capacity,
    detect_c2_bin_status_mismatch,
    detect_c4_hazmat_in_nonhaz_bin,
)

XLSX_PATH = Path(r"C:\Users\Mohd Aftaab\Downloads\Telegram Desktop\Warehouse_AI_Hackathon_Synthetic_Dataset_FINAL 2.xlsx")


def _inv(**kwargs):
    base = {"material": "MAT-X", "plant": "1020", "storage_location": "0001",
            "batch": None, "uom": "EA", "qty_on_hand": 100.0, "blocked_qty": 0.0,
            "in_transit_qty": 0.0, "batch_expiry": None, "last_movement_date": date(2026, 8, 1)}
    base.update(kwargs)
    return base


def _bin(**kwargs):
    base = {"bin": "WH1-A01-1", "storage_type": "HIGH-RACK", "assigned_material": "MAT-X",
            "capacity": 500.0, "occupied": 200.0, "bin_status": "OCC", "plant": "1010"}
    base.update(kwargs)
    return base


def _mm(**kwargs):
    base = {"material": "MAT-X", "description": "Test", "material_type": "FERT",
            "material_group": "GRP", "base_uom": "EA", "plant": "1010",
            "reorder_point": 100.0, "safety_stock": 50.0, "lead_time_days": 5.0,
            "abc_class": "A", "hazmat_flag": "Y", "lifecycle_status": "ACTIVE"}
    base.update(kwargs)
    return base


# ----- B1: Negative On-Hand Stock ---------------------------------------

def test_inv_b1_negative_stock_detected():
    findings = detect_b1_negative_stock([_inv(qty_on_hand=-15.0)])
    assert len(findings) == 1
    assert findings[0]["severity"] == "critical"


def test_inv_b1_zero_is_valid():
    assert detect_b1_negative_stock([_inv(qty_on_hand=0.0)]) == []


def test_inv_b1_negative_with_in_transit():
    findings = detect_b1_negative_stock([_inv(qty_on_hand=-10.0, in_transit_qty=50.0)])
    assert len(findings) == 1
    assert findings[0]["in_transit_qty"] == 50.0


# ----- B2: Expired Batch with Stock -------------------------------------

def test_inv_b2_expired_with_stock():
    findings = detect_b2_expired_batch_with_stock(
        [_inv(batch_expiry=date(2026, 8, 15), qty_on_hand=80.0)]
    )
    assert len(findings) == 1
    assert findings[0]["severity"] == "high"


def test_inv_b2_expired_zero_stock_no_finding():
    assert detect_b2_expired_batch_with_stock(
        [_inv(batch_expiry=date(2026, 8, 1), qty_on_hand=0.0)]
    ) == []


def test_inv_b2_exact_snapshot_date_flagged():
    findings = detect_b2_expired_batch_with_stock(
        [_inv(batch_expiry=SNAPSHOT_DATE, qty_on_hand=50.0)]
    )
    assert len(findings) == 1


def test_inv_b2_fully_quarantined_downgraded():
    findings = detect_b2_expired_batch_with_stock(
        [_inv(batch_expiry=date(2026, 8, 1), qty_on_hand=80.0, blocked_qty=80.0)]
    )
    assert len(findings) == 1
    assert findings[0]["severity"] == "low"
    assert findings[0]["fully_blocked"] is True


def test_inv_b2_future_expiry_no_finding():
    assert detect_b2_expired_batch_with_stock(
        [_inv(batch_expiry=date(2027, 1, 1), qty_on_hand=80.0)]
    ) == []


# ----- B4: Stale / Dead Stock -------------------------------------------

def test_inv_b4_stale_over_365_days():
    stale_date = date(2025, 7, 31)
    findings = detect_b4_stale_stock([_inv(last_movement_date=stale_date, qty_on_hand=100.0)])
    assert len(findings) == 1
    assert findings[0]["days_stale"] > 365


def test_inv_b4_zero_stock_no_finding():
    stale_date = date(2024, 1, 1)
    assert detect_b4_stale_stock([_inv(last_movement_date=stale_date, qty_on_hand=0.0)]) == []


def test_inv_b4_recent_movement_no_finding():
    recent = date(2026, 8, 1)
    assert detect_b4_stale_stock([_inv(last_movement_date=recent, qty_on_hand=50.0)]) == []


# ----- B5: Blocked Exceeds On-Hand -------------------------------------

def test_inv_b5_blocked_gt_on_hand():
    findings = detect_b5_blocked_exceeds_on_hand([_inv(qty_on_hand=100.0, blocked_qty=150.0)])
    assert len(findings) == 1
    assert findings[0]["catalog_id"] == "B5"


def test_inv_b5_blocked_equals_on_hand_no_finding():
    assert detect_b5_blocked_exceeds_on_hand([_inv(qty_on_hand=100.0, blocked_qty=100.0)]) == []


def test_inv_b5_blocked_zero_no_finding():
    assert detect_b5_blocked_exceeds_on_hand([_inv(qty_on_hand=100.0, blocked_qty=0.0)]) == []


# ----- C1: Bin Over-Capacity -------------------------------------------

def test_bin_c1_over_capacity():
    findings = detect_c1_bin_over_capacity([_bin(capacity=100.0, occupied=250.0)])
    assert len(findings) == 1
    assert findings[0]["catalog_id"] == "C1"
    assert findings[0]["overflow_pct"] == 150.0


def test_bin_c1_at_100pct_no_finding():
    assert detect_c1_bin_over_capacity([_bin(capacity=500.0, occupied=500.0)]) == []


def test_bin_c1_under_capacity_no_finding():
    assert detect_c1_bin_over_capacity([_bin(capacity=500.0, occupied=250.0)]) == []


# ----- C2: Status / Occupancy Mismatch ---------------------------------

def test_bin_c2_free_but_occupied():
    findings = detect_c2_bin_status_mismatch([_bin(bin_status="FREE", occupied=120.0)])
    assert len(findings) == 1
    assert findings[0]["mismatch_type"] == "FREE_but_occupied"
    assert findings[0]["severity"] == "medium"


def test_bin_c2_occ_but_empty():
    findings = detect_c2_bin_status_mismatch([_bin(bin_status="OCC", occupied=0.0)])
    assert len(findings) == 1
    assert findings[0]["mismatch_type"] == "OCC_but_empty"
    assert findings[0]["severity"] == "low"


def test_bin_c2_valid_occ_no_finding():
    assert detect_c2_bin_status_mismatch([_bin(bin_status="OCC", occupied=100.0)]) == []


# ----- C4: Hazmat in Non-HAZ Bin ----------------------------------------

def test_bin_c4_hazmat_in_cold():
    mm = [_mm(material="MAT-HAZ", hazmat_flag="Y")]
    bins = [_bin(assigned_material="MAT-HAZ", storage_type="COLD")]
    findings = detect_c4_hazmat_in_nonhaz_bin(mm, bins)
    assert len(findings) == 1
    assert findings[0]["catalog_id"] == "C4"


def test_bin_c4_hazmat_in_haz_bin_valid():
    mm = [_mm(material="MAT-HAZ", hazmat_flag="Y")]
    bins = [_bin(assigned_material="MAT-HAZ", storage_type="HAZ")]
    assert detect_c4_hazmat_in_nonhaz_bin(mm, bins) == []


# ----- Live workbook integration ----------------------------------------

@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not present")
def test_live_b1_negative_stock_found():
    wb = load_hackathon_workbook(XLSX_PATH)
    findings = detect_b1_negative_stock(wb["inventory_stock"])
    assert len(findings) >= 1, "MAT-100003 at Plant 1710 must have negative stock"


@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not present")
def test_live_b2_expired_batches_found():
    wb = load_hackathon_workbook(XLSX_PATH)
    findings = detect_b2_expired_batch_with_stock(wb["inventory_stock"])
    assert len(findings) >= 8, "At least 8 expired batches seeded in workbook"


@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not present")
def test_live_c1_bin_overflow_count():
    wb = load_hackathon_workbook(XLSX_PATH)
    findings = detect_c1_bin_over_capacity(wb["warehouse_bin"])
    assert len(findings) >= 22, "At least 22 over-capacity bins seeded in workbook"
