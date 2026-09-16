"""Dispatch, PO, and vendor anomaly tests (D2-D5, E1-E4, F1-F2)."""
from __future__ import annotations

from datetime import date
from pathlib import Path
import pytest

from app.services.hackathon_ingest import load_hackathon_workbook
from app.services.hackathon_detectors import (
    SNAPSHOT_DATE,
    detect_d2_missing_route,
    detect_d3_overdue_gi,
    detect_d5_route_shipto_mismatch,
    detect_e1_orphan_vendor,
    detect_e2_zero_missing_price,
    detect_e3_delivery_before_order,
    detect_e4_overdue_open_po,
    detect_f1_missing_vendor_country,
    detect_f2_blocked_vendor_open_po,
)

XLSX_PATH = Path(r"C:\Users\Mohd Aftaab\Downloads\Telegram Desktop\Warehouse_AI_Hackathon_Synthetic_Dataset_FINAL 2.xlsx")


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


def _vend(**kwargs):
    base = {"vendor": "VEND-001", "vendor_name": "Supplier A", "country": "DE",
            "quality_rating": "A", "otd_pct": 95.0, "procurement_block": "N"}
    base.update(kwargs)
    return base


# ----- D2: Missing Route -----------------------------------------------

def test_dsp_d2_no_route_flagged():
    findings = detect_d2_missing_route([_dlv(route=None)])
    assert len(findings) == 1
    assert findings[0]["catalog_id"] == "D2"


def test_dsp_d2_empty_string_route():
    findings = detect_d2_missing_route([_dlv(route="")])
    assert len(findings) == 1


def test_dsp_d2_route_on_delivered_also_flagged():
    findings = detect_d2_missing_route([_dlv(route=None, status="DELIVERED")])
    assert len(findings) == 1


def test_dsp_d2_with_route_no_finding():
    assert detect_d2_missing_route([_dlv(route="R-WEST")]) == []


# ----- D3: Overdue GI ---------------------------------------------------

def test_dsp_d3_open_past_gi_date():
    past_date = date(2026, 8, 17)
    findings = detect_d3_overdue_gi([_dlv(planned_gi_date=past_date, status="OPEN")])
    assert len(findings) == 1
    assert findings[0]["overdue_days"] > 0


def test_dsp_d3_delivered_past_gi_no_finding():
    past_date = date(2026, 8, 17)
    assert detect_d3_overdue_gi([_dlv(planned_gi_date=past_date, status="DELIVERED")]) == []


def test_dsp_d3_today_gi_date_not_overdue():
    findings = detect_d3_overdue_gi([_dlv(planned_gi_date=SNAPSHOT_DATE, status="OPEN")])
    assert len(findings) == 0


def test_dsp_d3_future_gi_no_finding():
    future = date(2026, 10, 1)
    assert detect_d3_overdue_gi([_dlv(planned_gi_date=future, status="OPEN")]) == []


# ----- D5: Route vs Ship-To Mismatch -----------------------------------

def test_dsp_d5_export_route_domestic_customer():
    findings = detect_d5_route_shipto_mismatch([_dlv(route="R-EXPORT", ship_to="CUST-2017")])
    assert len(findings) == 1
    assert findings[0]["catalog_id"] == "D5"


def test_dsp_d5_domestic_route_domestic_customer_valid():
    assert detect_d5_route_shipto_mismatch([_dlv(route="R-NORTH", ship_to="CUST-001")]) == []


# ----- E1: Orphan Vendor -----------------------------------------------

def test_rep_e1_unknown_vendor_flagged():
    po = [_po(vendor="VEND-9999")]
    vm = [_vend(vendor="VEND-001")]
    findings = detect_e1_orphan_vendor(po, vm)
    assert len(findings) == 1
    assert findings[0]["vendor"] == "VEND-9999"


def test_rep_e1_known_vendor_no_finding():
    po = [_po(vendor="VEND-001")]
    vm = [_vend(vendor="VEND-001")]
    assert detect_e1_orphan_vendor(po, vm) == []


# ----- E2: Zero / Missing Price ----------------------------------------

def test_rep_e2_zero_price():
    findings = detect_e2_zero_missing_price([_po(unit_price=0.0)])
    assert len(findings) == 1


def test_rep_e2_none_price():
    findings = detect_e2_zero_missing_price([_po(unit_price=None)])
    assert len(findings) == 1


def test_rep_e2_valid_price_no_finding():
    assert detect_e2_zero_missing_price([_po(unit_price=10.5)]) == []


# ----- E3: Delivery before Order ----------------------------------------

def test_rep_e3_delivery_before_order():
    po = [_po(order_date=date(2026, 8, 20), expected_delivery=date(2026, 8, 10))]
    findings = detect_e3_delivery_before_order(po)
    assert len(findings) == 1


def test_rep_e3_same_day_no_finding():
    po = [_po(order_date=date(2026, 8, 10), expected_delivery=date(2026, 8, 10))]
    assert detect_e3_delivery_before_order(po) == []


def test_rep_e3_future_delivery_valid():
    po = [_po(order_date=date(2026, 8, 10), expected_delivery=date(2026, 8, 20))]
    assert detect_e3_delivery_before_order(po) == []


# ----- E4: Overdue Open PO ---------------------------------------------

def test_rep_e4_overdue_open_po():
    po = [_po(expected_delivery=date(2026, 8, 26), po_status="OPEN")]
    findings = detect_e4_overdue_open_po(po)
    assert len(findings) == 1
    assert findings[0]["overdue_days"] > 0


def test_rep_e4_overdue_closed_po_no_finding():
    po = [_po(expected_delivery=date(2026, 8, 26), po_status="CLOSED")]
    assert detect_e4_overdue_open_po(po) == []


def test_rep_e4_future_open_po_no_finding():
    po = [_po(expected_delivery=date(2026, 10, 1), po_status="OPEN")]
    assert detect_e4_overdue_open_po(po) == []


# ----- F1: Missing Vendor Country --------------------------------------

def test_vnd_f1_missing_country():
    findings = detect_f1_missing_vendor_country([_vend(country=None)])
    assert len(findings) == 1


def test_vnd_f1_country_present_no_finding():
    assert detect_f1_missing_vendor_country([_vend(country="DE")]) == []


# ----- F2: Blocked Vendor with Open PO ---------------------------------

def test_vnd_f2_blocked_with_open_po():
    vm = [_vend(vendor="VEND-001", procurement_block="Y")]
    po = [_po(vendor="VEND-001", po_status="OPEN")]
    findings = detect_f2_blocked_vendor_open_po(vm, po)
    assert len(findings) == 1
    assert findings[0]["severity"] == "critical"


def test_vnd_f2_blocked_vendor_closed_po_no_finding():
    vm = [_vend(vendor="VEND-001", procurement_block="Y")]
    po = [_po(vendor="VEND-001", po_status="CLOSED")]
    assert detect_f2_blocked_vendor_open_po(vm, po) == []


def test_vnd_f2_unblocked_vendor_no_finding():
    vm = [_vend(vendor="VEND-001", procurement_block="N")]
    po = [_po(vendor="VEND-001", po_status="OPEN")]
    assert detect_f2_blocked_vendor_open_po(vm, po) == []


# ----- Live workbook integration ----------------------------------------

@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not present")
def test_live_e1_orphan_vendor_vend_9999():
    wb = load_hackathon_workbook(XLSX_PATH)
    findings = detect_e1_orphan_vendor(wb["purchase_replenish"], wb["vendor_master"])
    vendors_found = {f["vendor"] for f in findings}
    assert "VEND-9999" in vendors_found


@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not present")
def test_live_f1_missing_country_at_least_one():
    wb = load_hackathon_workbook(XLSX_PATH)
    findings = detect_f1_missing_vendor_country(wb["vendor_master"])
    assert len(findings) >= 1


@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not present")
def test_live_f2_blocked_vendor_open_po():
    wb = load_hackathon_workbook(XLSX_PATH)
    findings = detect_f2_blocked_vendor_open_po(wb["vendor_master"], wb["purchase_replenish"])
    assert len(findings) >= 1
