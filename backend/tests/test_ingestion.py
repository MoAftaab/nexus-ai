"""Ingestion edge case tests (ING-01 through ING-08)."""
from __future__ import annotations

from datetime import date
from pathlib import Path
import pytest

from app.services.hackathon_ingest import (
    _clean, _parse_date, _parse_float, _str_exact, _str_upper,
    _normalize_inventory_stock, _normalize_material_master,
    _normalize_warehouse_bin, _normalize_deliveries_dispatch,
    _normalize_purchase_replenish, _normalize_vendor_master,
    load_hackathon_workbook, build_material_set, build_vendor_index,
    REQUIRED_SHEETS,
)

XLSX_PATH = Path(r"C:\Users\Mohd Aftaab\Downloads\Telegram Desktop\Warehouse_AI_Hackathon_Synthetic_Dataset_FINAL 2.xlsx")


# ---------------------------------------------------------------------------
# ING-01: Null / whitespace / sentinel normalisation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    (None, None),
    ("", None),
    ("   ", None),
    ("N/A", None),
    ("#N/A", None),
    ("n/a", None),
    ("none", None),
    ("NULL", None),
    ("hello", "hello"),
    ("  hello  ", "hello"),
    (42, 42),
])
def test_ing01_clean_nulls(raw, expected):
    assert _clean(raw) == expected


# ---------------------------------------------------------------------------
# ING-02: Blank Batch treated as valid (non-batch-managed)
# ---------------------------------------------------------------------------

def test_ing02_blank_batch_is_valid():
    row = ("MAT-100000", "1020", "0001", None, "EA", 120, 0, 60, None, "2026-07-21")
    result = _normalize_inventory_stock(row)
    assert result["batch"] is None
    assert result["material"] == "MAT-100000"
    assert result["qty_on_hand"] == 120.0


def test_ing02_blank_batch_string():
    row = ("MAT-100001", "1710", "BULK", "", "KG", 20, 0, 30, None, "2026-08-25")
    result = _normalize_inventory_stock(row)
    assert result["batch"] is None


# ---------------------------------------------------------------------------
# ING-03: Leading zeros preserved for Plant / Storage Location
# ---------------------------------------------------------------------------

def test_ing03_plant_leading_zero():
    row = ("MAT-X", "desc", "FERT", "GRP", "EA", "1010", 100, 50, 5, "A", "N", "ACTIVE")
    result = _normalize_material_master(row)
    assert result["plant"] == "1010", "Plant code must remain string '1010', not int 1010"


def test_ing03_storage_location_leading_zero():
    row = ("MAT-X", "1020", "0001", None, "EA", 50, 0, 0, None, "2026-01-01")
    result = _normalize_inventory_stock(row)
    assert result["storage_location"] == "0001", "'0001' must not be coerced to 1"


@pytest.mark.parametrize("loc", ["0001", "0002", "RECV", "PICK", "BULK"])
def test_ing03_all_storage_locs(loc):
    row = ("MAT-X", "1710", loc, None, "EA", 10, 0, 0, None, "2026-01-01")
    result = _normalize_inventory_stock(row)
    assert result["storage_location"] == loc


# ---------------------------------------------------------------------------
# ING-04: Date parsing from ISO string, Excel serial, datetime object
# ---------------------------------------------------------------------------

def test_ing04_iso_date_string():
    assert _parse_date("2026-08-15") == date(2026, 8, 15)


def test_ing04_excel_epoch_serial():
    result = _parse_date(46249)
    assert result is not None
    assert result.year == 2026


def test_ing04_datetime_object():
    from datetime import datetime, timezone
    dt = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
    assert _parse_date(dt) == date(2026, 9, 5)


def test_ing04_blank_date():
    assert _parse_date(None) is None
    assert _parse_date("") is None
    assert _parse_date("N/A") is None


# ---------------------------------------------------------------------------
# ING-05: Plant extension gap
# ---------------------------------------------------------------------------

def test_ing05_cross_plant_reference():
    mm = [{"material": "MAT-X", "plant": "1010", "description": "Test",
           "material_type": "FERT", "material_group": "GRP", "base_uom": "EA",
           "reorder_point": 100.0, "safety_stock": 50.0, "lead_time_days": 5.0,
           "abc_class": "A", "hazmat_flag": "N", "lifecycle_status": "ACTIVE"}]
    from app.services.hackathon_ingest import build_material_index
    idx = build_material_index(mm)
    assert ("MAT-X", "1010") in idx
    assert ("MAT-X", "1020") not in idx, "Cross-plant reference should show as absent in index"


# ---------------------------------------------------------------------------
# ING-06: Case normalisation on Material IDs
# ---------------------------------------------------------------------------

def test_ing06_material_id_case_preservation():
    assert _str_exact("mat-100000") == "mat-100000"
    assert _str_upper("mat-100000") == "MAT-100000"


# ---------------------------------------------------------------------------
# ING-07: Comma-formatted and decimal quantities
# ---------------------------------------------------------------------------

def test_ing07_comma_qty():
    assert _parse_float("1,500") == 1500.0
    assert _parse_float("1,500.75") == 1500.75


def test_ing07_decimal_in_int_field():
    assert _parse_float("12.500") == 12.5
    assert _parse_float(5000) == 5000.0


# ---------------------------------------------------------------------------
# ING-08: Missing required sheet graceful handling
# ---------------------------------------------------------------------------

def test_ing08_missing_sheet_set():
    expected = {
        "Material_Master", "Inventory_Stock", "Warehouse_Bin",
        "Deliveries_Dispatch", "Purchase_Replenish", "Vendor_Master",
    }
    assert expected == REQUIRED_SHEETS


# ---------------------------------------------------------------------------
# Live workbook integration test
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not present")
def test_live_workbook_loads_all_sheets():
    wb = load_hackathon_workbook(XLSX_PATH)
    assert wb["missing_sheets"] == [], f"Required sheets missing: {wb['missing_sheets']}"
    assert len(wb["material_master"]) == 61
    assert len(wb["inventory_stock"]) == 82
    assert len(wb["warehouse_bin"]) == 50
    assert len(wb["deliveries_dispatch"]) == 120
    assert len(wb["purchase_replenish"]) == 80
    assert len(wb["vendor_master"]) == 25


@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not present")
def test_live_plant_codes_are_strings():
    wb = load_hackathon_workbook(XLSX_PATH)
    for row in wb["material_master"]:
        plant = row["plant"]
        assert isinstance(plant, str), f"Plant must be string, got {type(plant)}: {plant}"
        assert not plant.startswith(" "), f"Plant has leading whitespace: '{plant}'"


@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not present")
def test_live_orphan_material_present():
    wb = load_hackathon_workbook(XLSX_PATH)
    mat_set = build_material_set(wb["material_master"])
    inv_mats = {r["material"] for r in wb["inventory_stock"] if r.get("material")}
    orphans = inv_mats - mat_set
    assert "MAT-999001" in orphans, "Seeded orphan MAT-999001 must be detectable"


@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not present")
def test_live_orphan_vendor_present():
    wb = load_hackathon_workbook(XLSX_PATH)
    vend_idx = build_vendor_index(wb["vendor_master"])
    po_vendors = {r["vendor"] for r in wb["purchase_replenish"] if r.get("vendor")}
    orphan_vends = po_vendors - set(vend_idx.keys())
    assert "VEND-9999" in orphan_vends, "Seeded orphan vendor VEND-9999 must be detectable"
