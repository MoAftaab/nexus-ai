from __future__ import annotations

from datetime import date
from typing import Any

SNAPSHOT_DATE = date(2026, 9, 5)

_DOMESTIC_ROUTES = {"R-NORTH", "R-SOUTH", "R-EAST", "R-WEST", "R-CENTRAL"}
_EXPORT_ROUTES = {"R-EXPORT"}
_HAZMAT_SAFE_STORAGE = {"HAZ"}


def _qty(v: Any) -> float:
    if v is None:
        return 0.0
    try:
        return float(v)
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# A-Series: Master Data
# ---------------------------------------------------------------------------

def detect_a1_missing_uom(material_master: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings = []
    for row in material_master:
        if not row.get("base_uom"):
            findings.append({
                "catalog_id": "A1",
                "severity": "high",
                "material": row.get("material"),
                "plant": row.get("plant"),
                "description": row.get("description"),
                "lifecycle_status": row.get("lifecycle_status"),
                "detail": "Base UoM is blank — unit conversion and valuation will fail.",
            })
    return findings


def detect_a2_invalid_reorder_point(material_master: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings = []
    for row in material_master:
        rp = row.get("reorder_point")
        if rp is None or rp < 0:
            findings.append({
                "catalog_id": "A2",
                "severity": "high",
                "material": row.get("material"),
                "plant": row.get("plant"),
                "reorder_point": rp,
                "detail": f"Reorder point is {'missing' if rp is None else rp} — replenishment trigger will never fire.",
            })
    return findings


def detect_a3_duplicate_description(material_master: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from collections import defaultdict
    desc_map: dict[str, list[str]] = defaultdict(list)
    for row in material_master:
        desc = (row.get("description") or "").strip().lower()
        mat = row.get("material")
        if desc and mat:
            desc_map[desc].append(mat)
    findings = []
    for desc, mats in desc_map.items():
        if len(mats) > 1:
            findings.append({
                "catalog_id": "A3",
                "severity": "medium",
                "description": desc,
                "duplicate_materials": sorted(mats),
                "detail": f"Description shared by {len(mats)} materials: {', '.join(sorted(mats))}.",
            })
    return findings


def detect_a4_safety_gt_reorder(material_master: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings = []
    for row in material_master:
        rp = row.get("reorder_point")
        ss = row.get("safety_stock")
        if rp is None or ss is None:
            continue
        if ss > rp:
            findings.append({
                "catalog_id": "A4",
                "severity": "medium",
                "material": row.get("material"),
                "plant": row.get("plant"),
                "safety_stock": ss,
                "reorder_point": rp,
                "detail": f"Safety stock ({ss}) exceeds reorder point ({rp}) — will produce constant false replenishment alerts.",
            })
    return findings


def detect_a5_obsolete_in_use(
    material_master: list[dict[str, Any]],
    deliveries_dispatch: list[dict[str, Any]],
    purchase_replenish: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    inactive = {
        row["material"]
        for row in material_master
        if row.get("lifecycle_status") in ("OBSOLETE", "BLOCKED")
        and row.get("material")
    }
    findings = []
    for dlv in deliveries_dispatch:
        mat = dlv.get("material")
        if mat in inactive and (dlv.get("status") or "") not in ("DELIVERED", "CANCELLED"):
            findings.append({
                "catalog_id": "A5",
                "severity": "critical",
                "material": mat,
                "delivery": dlv.get("delivery"),
                "status": dlv.get("status"),
                "detail": f"Material {mat} has non-ACTIVE lifecycle status but appears in open delivery {dlv.get('delivery')}.",
            })
    for po in purchase_replenish:
        mat = po.get("material")
        if mat in inactive and (po.get("po_status") or "") in ("OPEN", "PARTIAL"):
            findings.append({
                "catalog_id": "A5",
                "severity": "critical",
                "material": mat,
                "purchase_order": po.get("purchase_order"),
                "po_status": po.get("po_status"),
                "detail": f"Material {mat} has non-ACTIVE lifecycle status but appears in open PO {po.get('purchase_order')}.",
            })
    return findings


def detect_a6_hazmat_mismatch(
    material_master: list[dict[str, Any]],
    warehouse_bin: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    hazmat_materials = {
        row["material"]
        for row in material_master
        if (row.get("hazmat_flag") or "").upper() == "Y"
        and row.get("material")
    }
    findings = []
    for bin_row in warehouse_bin:
        mat = bin_row.get("assigned_material")
        st = (bin_row.get("storage_type") or "").upper()
        if mat in hazmat_materials and st not in _HAZMAT_SAFE_STORAGE:
            findings.append({
                "catalog_id": "A6",
                "severity": "high",
                "material": mat,
                "bin": bin_row.get("bin"),
                "storage_type": st,
                "detail": f"Hazmat material {mat} is stored in non-HAZ bin {bin_row.get('bin')} (type={st}) — compliance breach.",
            })
    return findings


# ---------------------------------------------------------------------------
# B-Series: Inventory
# ---------------------------------------------------------------------------

def detect_b1_negative_stock(inventory_stock: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "catalog_id": "B1",
            "severity": "critical",
            "material": r.get("material"),
            "plant": r.get("plant"),
            "storage_location": r.get("storage_location"),
            "qty_on_hand": r.get("qty_on_hand"),
            "in_transit_qty": r.get("in_transit_qty"),
            "detail": f"Negative on-hand stock ({r.get('qty_on_hand')}) — impossible quantity, book/physical sync failure.",
        }
        for r in inventory_stock
        if _qty(r.get("qty_on_hand")) < 0
    ]


def detect_b2_expired_batch_with_stock(
    inventory_stock: list[dict[str, Any]],
    snapshot: date = SNAPSHOT_DATE,
) -> list[dict[str, Any]]:
    findings = []
    for r in inventory_stock:
        expiry = r.get("batch_expiry")
        qty = _qty(r.get("qty_on_hand"))
        blocked = _qty(r.get("blocked_qty"))
        if expiry is None or qty <= 0:
            continue
        if expiry <= snapshot:
            fully_blocked = blocked >= qty
            findings.append({
                "catalog_id": "B2",
                "severity": "low" if fully_blocked else "high",
                "material": r.get("material"),
                "plant": r.get("plant"),
                "batch": r.get("batch"),
                "batch_expiry": str(expiry),
                "qty_on_hand": qty,
                "blocked_qty": blocked,
                "fully_blocked": fully_blocked,
                "detail": (
                    f"Batch expired {expiry} with {qty} on hand"
                    + (" (fully quarantined in blocked stock)." if fully_blocked else " — expired stock eligible for dispatch.")
                ),
            })
    return findings


def detect_b4_stale_stock(
    inventory_stock: list[dict[str, Any]],
    snapshot: date = SNAPSHOT_DATE,
    threshold_days: int = 365,
) -> list[dict[str, Any]]:
    findings = []
    for r in inventory_stock:
        last_mv = r.get("last_movement_date")
        qty = _qty(r.get("qty_on_hand"))
        if last_mv is None or qty <= 0:
            continue
        age = (snapshot - last_mv).days
        if age > threshold_days:
            findings.append({
                "catalog_id": "B4",
                "severity": "medium",
                "material": r.get("material"),
                "plant": r.get("plant"),
                "storage_location": r.get("storage_location"),
                "qty_on_hand": qty,
                "last_movement_date": str(last_mv),
                "days_stale": age,
                "detail": f"No movement in {age} days (>{threshold_days} threshold). Capital and space are tied up.",
            })
    return findings


def detect_b5_blocked_exceeds_on_hand(inventory_stock: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings = []
    for r in inventory_stock:
        qty = _qty(r.get("qty_on_hand"))
        blocked = _qty(r.get("blocked_qty"))
        if blocked > qty and blocked > 0:
            findings.append({
                "catalog_id": "B5",
                "severity": "medium",
                "material": r.get("material"),
                "plant": r.get("plant"),
                "storage_location": r.get("storage_location"),
                "qty_on_hand": qty,
                "blocked_qty": blocked,
                "detail": f"Blocked qty ({blocked}) exceeds on-hand ({qty}) — available stock is misstated.",
            })
    return findings


# ---------------------------------------------------------------------------
# C-Series: Warehouse Bin
# ---------------------------------------------------------------------------

def detect_c1_bin_over_capacity(warehouse_bin: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings = []
    for r in warehouse_bin:
        cap = _qty(r.get("capacity"))
        occ = _qty(r.get("occupied"))
        if cap > 0 and occ > cap:
            findings.append({
                "catalog_id": "C1",
                "severity": "medium",
                "bin": r.get("bin"),
                "storage_type": r.get("storage_type"),
                "plant": r.get("plant"),
                "capacity": cap,
                "occupied": occ,
                "overflow_pct": round((occ - cap) / cap * 100, 1),
                "detail": f"Bin {r.get('bin')}: occupied={occ} exceeds capacity={cap} (overflow {round((occ-cap)/cap*100,1)}%).",
            })
    return findings


def detect_c2_bin_status_mismatch(warehouse_bin: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings = []
    for r in warehouse_bin:
        status = (r.get("bin_status") or "").upper()
        occ = _qty(r.get("occupied"))
        if status == "FREE" and occ > 0:
            findings.append({
                "catalog_id": "C2",
                "severity": "medium",
                "bin": r.get("bin"),
                "plant": r.get("plant"),
                "bin_status": status,
                "occupied": occ,
                "mismatch_type": "FREE_but_occupied",
                "detail": f"Bin {r.get('bin')} is marked FREE but has {occ} occupied units — putaway conflict.",
            })
        elif status == "OCC" and occ == 0:
            findings.append({
                "catalog_id": "C2",
                "severity": "low",
                "bin": r.get("bin"),
                "plant": r.get("plant"),
                "bin_status": status,
                "occupied": occ,
                "mismatch_type": "OCC_but_empty",
                "detail": f"Bin {r.get('bin')} is marked OCC but has 0 occupied units — ghost occupancy blocks putaways.",
            })
    return findings


def detect_c4_hazmat_in_nonhaz_bin(
    material_master: list[dict[str, Any]],
    warehouse_bin: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    hazmat_mats = {
        r["material"]
        for r in material_master
        if (r.get("hazmat_flag") or "").upper() == "Y" and r.get("material")
    }
    findings = []
    for r in warehouse_bin:
        mat = r.get("assigned_material")
        st = (r.get("storage_type") or "").upper()
        if mat in hazmat_mats and st not in _HAZMAT_SAFE_STORAGE:
            findings.append({
                "catalog_id": "C4",
                "severity": "high",
                "material": mat,
                "bin": r.get("bin"),
                "storage_type": st,
                "plant": r.get("plant"),
                "detail": f"Hazmat material {mat} is in {st} bin {r.get('bin')} — must be HAZ type.",
            })
    return findings


# ---------------------------------------------------------------------------
# D-Series: Deliveries & Dispatch
# ---------------------------------------------------------------------------

def detect_d2_missing_route(deliveries_dispatch: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "catalog_id": "D2",
            "severity": "high",
            "delivery": r.get("delivery"),
            "material": r.get("material"),
            "plant": r.get("plant"),
            "status": r.get("status"),
            "detail": f"Delivery {r.get('delivery')} has no route assigned — carrier cannot be booked.",
        }
        for r in deliveries_dispatch
        if not r.get("route")
    ]


def detect_d3_overdue_gi(
    deliveries_dispatch: list[dict[str, Any]],
    snapshot: date = SNAPSHOT_DATE,
) -> list[dict[str, Any]]:
    active_statuses = {"OPEN", "PICKED", "CREATED"}
    findings = []
    for r in deliveries_dispatch:
        gi_date = r.get("planned_gi_date")
        status = (r.get("status") or "").upper()
        if gi_date is None:
            continue
        if gi_date < snapshot and status in active_statuses:
            overdue_days = (snapshot - gi_date).days
            findings.append({
                "catalog_id": "D3",
                "severity": "critical" if overdue_days > 7 else "high",
                "delivery": r.get("delivery"),
                "material": r.get("material"),
                "plant": r.get("plant"),
                "planned_gi_date": str(gi_date),
                "status": status,
                "overdue_days": overdue_days,
                "detail": f"Delivery {r.get('delivery')} planned GI was {gi_date} ({overdue_days} days overdue). SLA breach.",
            })
    return findings


def detect_d5_route_shipto_mismatch(deliveries_dispatch: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings = []
    for r in deliveries_dispatch:
        route = (r.get("route") or "").upper()
        ship_to = (r.get("ship_to") or "").upper()
        if not route or not ship_to:
            continue
        is_export_route = route in _EXPORT_ROUTES
        is_domestic_customer = ship_to.startswith("CUST-")
        if is_export_route and is_domestic_customer:
            findings.append({
                "catalog_id": "D5",
                "severity": "medium",
                "delivery": r.get("delivery"),
                "material": r.get("material"),
                "plant": r.get("plant"),
                "route": route,
                "ship_to": r.get("ship_to"),
                "detail": f"Delivery {r.get('delivery')}: export route {route} used for domestic customer {r.get('ship_to')} — freight cost leakage.",
            })
    return findings


# ---------------------------------------------------------------------------
# E-Series: Purchase / Replenishment
# ---------------------------------------------------------------------------

def detect_e1_orphan_vendor(
    purchase_replenish: list[dict[str, Any]],
    vendor_master: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    known_vendors = {r["vendor"] for r in vendor_master if r.get("vendor")}
    return [
        {
            "catalog_id": "E1",
            "severity": "high",
            "purchase_order": r.get("purchase_order"),
            "material": r.get("material"),
            "vendor": r.get("vendor"),
            "po_status": r.get("po_status"),
            "detail": f"PO {r.get('purchase_order')} references vendor {r.get('vendor')} not in Vendor_Master.",
        }
        for r in purchase_replenish
        if r.get("vendor") and r["vendor"] not in known_vendors
    ]


def detect_e2_zero_missing_price(purchase_replenish: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "catalog_id": "E2",
            "severity": "medium",
            "purchase_order": r.get("purchase_order"),
            "material": r.get("material"),
            "vendor": r.get("vendor"),
            "unit_price": r.get("unit_price"),
            "detail": f"PO {r.get('purchase_order')} has zero or missing unit price — valuation error and GR invoice block.",
        }
        for r in purchase_replenish
        if r.get("unit_price") is None or _qty(r.get("unit_price")) <= 0
    ]


def detect_e3_delivery_before_order(purchase_replenish: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings = []
    for r in purchase_replenish:
        od = r.get("order_date")
        ed = r.get("expected_delivery")
        if od is None or ed is None:
            continue
        if ed < od:
            findings.append({
                "catalog_id": "E3",
                "severity": "medium",
                "purchase_order": r.get("purchase_order"),
                "material": r.get("material"),
                "order_date": str(od),
                "expected_delivery": str(ed),
                "detail": f"PO {r.get('purchase_order')}: expected delivery {ed} is before order date {od} — temporal logic error.",
            })
    return findings


def detect_e4_overdue_open_po(
    purchase_replenish: list[dict[str, Any]],
    snapshot: date = SNAPSHOT_DATE,
) -> list[dict[str, Any]]:
    findings = []
    for r in purchase_replenish:
        ed = r.get("expected_delivery")
        status = (r.get("po_status") or "").upper()
        if ed is None:
            continue
        if ed < snapshot and status in ("OPEN", "PARTIAL"):
            overdue_days = (snapshot - ed).days
            findings.append({
                "catalog_id": "E4",
                "severity": "high",
                "purchase_order": r.get("purchase_order"),
                "material": r.get("material"),
                "vendor": r.get("vendor"),
                "expected_delivery": str(ed),
                "overdue_days": overdue_days,
                "detail": f"PO {r.get('purchase_order')} expected {ed} ({overdue_days} days overdue) still {status} — replenishment failure.",
            })
    return findings


# ---------------------------------------------------------------------------
# F-Series: Vendor Master
# ---------------------------------------------------------------------------

def detect_f1_missing_vendor_country(vendor_master: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "catalog_id": "F1",
            "severity": "medium",
            "vendor": r.get("vendor"),
            "vendor_name": r.get("vendor_name"),
            "detail": f"Vendor {r.get('vendor')} ({r.get('vendor_name')}) has no country — tax and route determination will fail.",
        }
        for r in vendor_master
        if not r.get("country")
    ]


def detect_f2_blocked_vendor_open_po(
    vendor_master: list[dict[str, Any]],
    purchase_replenish: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    blocked_vendors = {
        r["vendor"]
        for r in vendor_master
        if (r.get("procurement_block") or "").upper() == "Y" and r.get("vendor")
    }
    findings = []
    for r in purchase_replenish:
        vend = r.get("vendor")
        status = (r.get("po_status") or "").upper()
        if vend in blocked_vendors and status in ("OPEN", "PARTIAL"):
            findings.append({
                "catalog_id": "F2",
                "severity": "critical",
                "vendor": vend,
                "purchase_order": r.get("purchase_order"),
                "material": r.get("material"),
                "po_status": status,
                "detail": f"Vendor {vend} is procurement-blocked but has {status} PO {r.get('purchase_order')} — non-compliant procurement.",
            })
    return findings


# ---------------------------------------------------------------------------
# X-Series: Cross-System Correlations
# ---------------------------------------------------------------------------

def detect_x1_orphan_material(
    material_master: list[dict[str, Any]],
    inventory_stock: list[dict[str, Any]],
    warehouse_bin: list[dict[str, Any]],
    deliveries_dispatch: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    known = {r["material"] for r in material_master if r.get("material")}
    orphan_details: dict[str, dict[str, Any]] = {}

    for r in inventory_stock:
        mat = r.get("material")
        if mat and mat not in known:
            info = orphan_details.setdefault(mat, {"sheets": set(), "inventory_rows": [], "bin_rows": [], "delivery_rows": []})
            info["sheets"].add("Inventory_Stock")
            info["inventory_rows"].append(r)

    for r in warehouse_bin:
        mat = r.get("assigned_material")
        if mat and mat not in known:
            info = orphan_details.setdefault(mat, {"sheets": set(), "inventory_rows": [], "bin_rows": [], "delivery_rows": []})
            info["sheets"].add("Warehouse_Bin")
            info["bin_rows"].append(r)

    for r in deliveries_dispatch:
        mat = r.get("material")
        if mat and mat not in known:
            info = orphan_details.setdefault(mat, {"sheets": set(), "inventory_rows": [], "bin_rows": [], "delivery_rows": []})
            info["sheets"].add("Deliveries_Dispatch")
            info["delivery_rows"].append(r)

    findings = []
    for mat, info in sorted(orphan_details.items()):
        sheets = sorted(info["sheets"])
        severity = "critical" if len(sheets) >= 3 else "high" if len(sheets) == 2 else "medium"
        findings.append({
            "catalog_id": "X1",
            "severity": severity,
            "material": mat,
            "present_in_sheets": sheets,
            "sheet_count": len(sheets),
            "root_cause": "Material exists in transactional systems without a master record — ERP/WMS replication gap.",
            "detail": f"Orphan material {mat} found in {len(sheets)} sheet(s): {', '.join(sheets)} — no master record in Material_Master.",
        })
    return findings


def detect_x2_dispatch_exceeds_atp(
    material_master: list[dict[str, Any]],
    inventory_stock: list[dict[str, Any]],
    deliveries_dispatch: list[dict[str, Any]],
    snapshot: date = SNAPSHOT_DATE,
) -> list[dict[str, Any]]:
    from collections import defaultdict

    net_atp: dict[tuple[str, str], float] = defaultdict(float)
    for r in inventory_stock:
        mat = r.get("material")
        plant = r.get("plant")
        if not mat or not plant:
            continue
        qty = _qty(r.get("qty_on_hand"))
        blocked = _qty(r.get("blocked_qty"))
        expiry = r.get("batch_expiry")
        expired_qty = qty if (expiry and expiry <= snapshot and qty > 0) else 0.0
        usable = max(0.0, qty - blocked - expired_qty)
        net_atp[(mat, plant)] += usable

    committed: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    active_statuses = {"OPEN", "PICKED", "CREATED"}
    for r in deliveries_dispatch:
        mat = r.get("material")
        plant = r.get("plant")
        status = (r.get("status") or "").upper()
        if mat and plant and status in active_statuses:
            committed[(mat, plant)].append(r)

    findings = []
    for (mat, plant), dlvs in committed.items():
        total_demand = sum(_qty(d.get("order_qty")) for d in dlvs)
        atp = net_atp.get((mat, plant), 0.0)
        if total_demand > atp:
            shortfall = total_demand - atp
            findings.append({
                "catalog_id": "X2",
                "severity": "critical",
                "material": mat,
                "plant": plant,
                "net_atp": round(atp, 2),
                "committed_qty": round(total_demand, 2),
                "shortfall": round(shortfall, 2),
                "delivery_count": len(dlvs),
                "deliveries": [d.get("delivery") for d in dlvs],
                "root_cause": "No ATP check performed before order release — committed demand exceeds available stock.",
                "detail": f"{mat}@{plant}: committed={total_demand}, net_atp={round(atp,2)}, shortfall={round(shortfall,2)}.",
            })
    return findings


# ---------------------------------------------------------------------------
# Master runner
# ---------------------------------------------------------------------------

def run_all_detectors(wb_data: dict[str, Any], snapshot: date = SNAPSHOT_DATE) -> dict[str, list[dict[str, Any]]]:
    mm = wb_data.get("material_master", [])
    inv = wb_data.get("inventory_stock", [])
    bins = wb_data.get("warehouse_bin", [])
    dlv = wb_data.get("deliveries_dispatch", [])
    po = wb_data.get("purchase_replenish", [])
    vm = wb_data.get("vendor_master", [])

    return {
        "A1": detect_a1_missing_uom(mm),
        "A2": detect_a2_invalid_reorder_point(mm),
        "A3": detect_a3_duplicate_description(mm),
        "A4": detect_a4_safety_gt_reorder(mm),
        "A5": detect_a5_obsolete_in_use(mm, dlv, po),
        "A6": detect_a6_hazmat_mismatch(mm, bins),
        "B1": detect_b1_negative_stock(inv),
        "B2": detect_b2_expired_batch_with_stock(inv, snapshot),
        "B4": detect_b4_stale_stock(inv, snapshot),
        "B5": detect_b5_blocked_exceeds_on_hand(inv),
        "C1": detect_c1_bin_over_capacity(bins),
        "C2": detect_c2_bin_status_mismatch(bins),
        "C4": detect_c4_hazmat_in_nonhaz_bin(mm, bins),
        "D2": detect_d2_missing_route(dlv),
        "D3": detect_d3_overdue_gi(dlv, snapshot),
        "D5": detect_d5_route_shipto_mismatch(dlv),
        "E1": detect_e1_orphan_vendor(po, vm),
        "E2": detect_e2_zero_missing_price(po),
        "E3": detect_e3_delivery_before_order(po),
        "E4": detect_e4_overdue_open_po(po, snapshot),
        "F1": detect_f1_missing_vendor_country(vm),
        "F2": detect_f2_blocked_vendor_open_po(vm, po),
        "X1": detect_x1_orphan_material(mm, inv, bins, dlv),
        "X2": detect_x2_dispatch_exceeds_atp(mm, inv, dlv, snapshot),
    }
