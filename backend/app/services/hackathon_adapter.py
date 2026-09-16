"""Adapter converting hackathon detector findings into first-class NexusAI Anomaly domain objects."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models import Anomaly, CascadeEdge, CascadeNode, Evidence, FixAction

RULE_CONFIG: dict[str, dict[str, Any]] = {
    # A-series: Master Data Governance
    "A1": {"domain": "Master Data Governance", "title": "Missing Base UoM", "horizon": "2d", "base_impact": 15000, "sys": "SAP S/4HANA MM"},
    "A2": {"domain": "Master Data Governance", "title": "Invalid Reorder Point", "horizon": "2d", "base_impact": 20000, "sys": "SAP MRP Engine"},
    "A3": {"domain": "Master Data Governance", "title": "Duplicate Material Description", "horizon": "2d", "base_impact": 12000, "sys": "Master Data Catalog"},
    "A4": {"domain": "Master Data Governance", "title": "Safety Stock Exceeds Reorder Point", "horizon": "2d", "base_impact": 18000, "sys": "Inventory Control"},
    "A5": {"domain": "Master Data Governance", "title": "Obsolete SKU in Open Transaction", "horizon": "4h", "base_impact": 75000, "sys": "Lifecycle Management"},
    "A6": {"domain": "Master Data Governance", "title": "Hazmat Class / Storage Mismatch", "horizon": "4h", "base_impact": 85000, "sys": "EHS Compliance"},
    # B-series: Inventory & Batch Quality
    "B1": {"domain": "Inventory Ledger Discrepancy", "title": "Negative Stock on Hand", "horizon": "1h", "base_impact": 65000, "sys": "Inventory Ledger (IM)"},
    "B2": {"domain": "Batch Quality Management", "title": "Expired Batch with Active Stock", "horizon": "4h", "base_impact": 45000, "sys": "Quality Inspection (QM)"},
    "B4": {"domain": "Working Capital & Storage", "title": "Stale Inventory (>365d No Movement)", "horizon": "3d", "base_impact": 12000, "sys": "Warehouse Aging Monitor"},
    "B5": {"domain": "Inventory Allocation", "title": "Blocked Qty Exceeds On-Hand Balance", "horizon": "2d", "base_impact": 16000, "sys": "Stock Reconciliation"},
    # C-series: Warehouse Bins
    "C1": {"domain": "Warehouse Capacity", "title": "Bin Capacity Overflow", "horizon": "4h", "base_impact": 28000, "sys": "Extended Warehouse Mgmt (EWM)"},
    "C2": {"domain": "Warehouse Execution", "title": "Bin Status Conflict", "horizon": "2d", "base_impact": 10000, "sys": "Slotting Engine"},
    "C4": {"domain": "Hazardous Material Protocol", "title": "Hazmat Stored in Non-HAZ Bin", "horizon": "4h", "base_impact": 85000, "sys": "EHS Regulatory"},
    # D-series: Deliveries & Dispatch Execution
    "D2": {"domain": "Dispatch Readiness", "title": "Missing Carrier Route Assignment", "horizon": "4h", "base_impact": 35000, "sys": "TMS Transport Management"},
    "D3": {"domain": "Outbound Logistics Delay", "title": "Overdue Planned Goods Issue", "horizon": "1h", "base_impact": 45000, "sys": "Logistics Execution (LE-SHP)"},
    "D5": {"domain": "Freight Compliance", "title": "Route / Customer Classification Mismatch", "horizon": "12h", "base_impact": 22000, "sys": "Freight Cost Settlement"},
    # E-series: Purchasing & Replenishment
    "E1": {"domain": "Procurement Integrity", "title": "Orphan Vendor in Open PO", "horizon": "2d", "base_impact": 55000, "sys": "Purchasing Ledger (MM-PUR)"},
    "E2": {"domain": "Procurement Valuation", "title": "Zero / Missing Unit Price on PO", "horizon": "2d", "base_impact": 18000, "sys": "Invoice Verification (MM-IV)"},
    "E3": {"domain": "Temporal Feasibility", "title": "PO Delivery Date Precedes Order Date", "horizon": "2d", "base_impact": 15000, "sys": "Scheduling Agreement"},
    "E4": {"domain": "Inbound Supply Reliability", "title": "Overdue Inbound Purchase Order", "horizon": "12h", "base_impact": 38000, "sys": "Supplier OTD Tracker"},
    # F-series: Vendor Master & Compliance
    "F1": {"domain": "Master Data Governance", "title": "Vendor Missing Country Classification", "horizon": "2d", "base_impact": 14000, "sys": "Vendor Master Ledger"},
    "F2": {"domain": "Supplier Compliance", "title": "Blocked Vendor Open Purchase Order", "horizon": "2d", "base_impact": 95000, "sys": "Vendor Risk Management"},
    # X-series: Cross-System Correlation & ATP
    "X1": {"domain": "Data Synchronization", "title": "Cross-System Orphan Material", "horizon": "12h", "base_impact": 125000, "sys": "ERP-WMS Replication"},
    "X2": {"domain": "Inventory Shortage", "title": "ATP Stockout Deficit", "horizon": "18h", "base_impact": 160000, "sys": "Available-to-Promise (ATP)"},
}


def _build_root_cause(rule_id: str, f: dict[str, Any], entity: str, plant: str) -> str:
    if f.get("root_cause") and "failed validation rule" not in str(f.get("root_cause")):
        return f["root_cause"]

    if rule_id == "A1":
        return f"Material master record {entity} in MARA was created without Base Unit of Measure (MEINS). Transaction processing, inventory valuation, and warehouse pick confirmations fail due to undefined unit conversion factors."
    if rule_id == "A2":
        rp = f.get("reorder_point")
        return f"Material {entity} at Plant {plant} has an invalid or negative reorder point in MARC-MINBE ({rp}). SAP MRP runs cannot evaluate replenishment triggers, halting automatic purchase requisition creation."
    if rule_id == "A3":
        dups = ", ".join(f.get("duplicate_materials", []))
        return f"Material {entity} shares an identical description '{f.get('description', '')}' with multiple distinct master records ({dups}). Ambiguous descriptions cause operator mis-picking and cross-SKU shipment discrepancies."
    if rule_id == "A4":
        ss = f.get("safety_stock")
        rp = f.get("reorder_point")
        return f"Material {entity} at Plant {plant} has safety stock ({ss}) exceeding reorder point ({rp}) in MARC. Inverted safety parameters generate persistent false replenishment alerts and warehouse storage congestion."
    if rule_id == "A5":
        dlv_po = f.get("delivery") or f.get("purchase_order") or "open transaction"
        return f"Material {entity} has lifecycle status '{f.get('status') or 'OBSOLETE'}' in MARA but appears in open document {dlv_po}. Phase-out policy was violated without purging or reassigning active transactional orders."
    if rule_id in ("A6", "C4"):
        st = f.get("storage_type", "STD")
        bin_id = f.get("bin", "unspecified")
        return f"Material {entity} is flagged HAZMAT (Y) in MARA but assigned to standard storage bin {bin_id} (type {st}). Storage segregation violates environmental safety standards (EHS) and industrial compliance regulations."
    if rule_id == "B1":
        qty = f.get("qty_on_hand", 0)
        return f"Storage location {f.get('storage_location', '0001')} shows negative inventory ({qty} EA) in MARD-LABST. Outbound goods issue posting preceded physical goods receipt confirmation, indicating book-to-physical sync failure (phantom inventory)."
    if rule_id == "B2":
        batch = f.get("batch", "unspecified")
        exp = f.get("batch_expiry", "past")
        qty = f.get("qty_on_hand", 0)
        return f"Batch {batch} of material {entity} reached expiration date {exp} with {qty} EA active unblocked stock. Batch was not quarantined (movement 344), creating risk of shipping expired components to customers."
    if rule_id == "B4":
        days = f.get("days_stale", ">365")
        last_mv = f.get("last_movement_date", "N/A")
        qty = f.get("qty_on_hand", 0)
        return f"Material {entity} at Plant {plant} has {qty} EA with zero movement for {days} days (since {last_mv}). Dormant working capital blocks bin space and faces obsolescence write-down risk."
    if rule_id == "B5":
        blk = f.get("blocked_qty", 0)
        qty = f.get("qty_on_hand", 0)
        return f"Storage location {f.get('storage_location', '0001')} records {blk} blocked units against {qty} total on hand. Inventory ledger distortion misstates Available-to-Promise (ATP) stock and inflates unfillable demand."
    if rule_id == "C1":
        bin_id = f.get("bin", entity)
        occ = f.get("occupied", 0)
        cap = f.get("capacity", 0)
        return f"Warehouse bin {bin_id} occupancy ({occ} units) exceeds rated storage capacity ({cap} units) by {f.get('overflow_pct', 0)}%. Unconstrained putaway allocation bypassed EWM capacity checks, risking structural racking damage."
    if rule_id == "C2":
        bin_id = f.get("bin", entity)
        st = f.get("bin_status", "UNKNOWN")
        occ = f.get("occupied", 0)
        return f"Warehouse bin {bin_id} status '{st}' conflicts with recorded occupancy ({occ} units). Warehouse management ledger is desynchronized with physical sensor or pick confirmation state."
    if rule_id == "D2":
        return f"Outbound delivery {entity} is missing carrier route assignment in LIKP-ROUTE. Carrier booking and dispatch scheduling cannot proceed, causing dock congestion and missed delivery windows."
    if rule_id == "D3":
        gi = f.get("planned_gi_date", "past")
        days = f.get("overdue_days", 0)
        st = f.get("status", "OPEN")
        return f"Outbound delivery {entity} planned Goods Issue was {gi} ({days} days overdue) but remains in {st} status. Picking or freight dispatch stalled at Plant {plant}, breaching customer SLA delivery deadlines."
    if rule_id == "D5":
        route = f.get("route", "unknown")
        cust = f.get("ship_to", "unknown")
        return f"Delivery {entity} assigns export route {route} to domestic customer destination {cust}. Transport routing inconsistency causes freight cost leakage and border customs rejection."
    if rule_id == "E1":
        vend = f.get("vendor", "unknown")
        return f"Purchase order {entity} references vendor {vend} which does not exist in Vendor Master (LFA1). Inbound goods receipt confirmation and three-way invoice matching cannot be executed."
    if rule_id == "E2":
        return f"Purchase order {entity} line item has zero or missing unit price. Unvalued purchase order bypasses financial commitment accounting and triggers mandatory invoice verification blocks (MRBR)."
    if rule_id == "E3":
        ed = f.get("expected_delivery", "N/A")
        od = f.get("order_date", "N/A")
        return f"Purchase order {entity} specifies expected delivery {ed} prior to order date {od}. Temporal sequencing error corrupts vendor delivery lead time metrics and scheduling agreement tracking."
    if rule_id == "E4":
        ed = f.get("expected_delivery", "past")
        days = f.get("overdue_days", 0)
        vend = f.get("vendor", "supplier")
        return f"Purchase order {entity} from vendor {vend} is {days} days overdue (expected {ed}) and remains OPEN. Inbound supplier fulfillment failure threatens manufacturing line continuity and replenishment SLAs."
    if rule_id == "F1":
        vname = f.get("vendor_name", entity)
        return f"Vendor master record {entity} ({vname}) is missing ISO country code (LFA1-LAND1). Cross-border tax determination, withholding tax, and compliance screening cannot be validated."
    if rule_id == "F2":
        po = f.get("purchase_order", "unspecified")
        return f"Vendor {entity} has an active procurement block (LFA1-SPERR) but has open purchase order {po}. Procurement compliance breach violates supply chain risk controls by issuing orders to a disqualified supplier."
    if rule_id == "X1":
        sheets = ", ".join(f.get("present_in_sheets", []))
        return f"Material {entity} is referenced in transactional records ({sheets}) but is absent from Material Master (MARA). Incomplete ERP-WMS master data synchronization caused transactional ghost entries."
    if rule_id == "X2":
        dem = f.get("committed_qty", 0)
        atp = f.get("net_atp", 0)
        short = f.get("shortfall", 0)
        return f"Plant {plant} committed delivery demand ({dem} EA) exceeds net available-to-promise inventory ({atp} EA), resulting in an immediate shortfall of {short} EA across open dispatches."

    return f.get("detail") or f"Discrepancy detected in validation rule {rule_id} for entity {entity}."


def _build_fix_action(rule_id: str, f: dict[str, Any], entity: str, plant: str, idx: int, imp: int, severity: str, horizon: str, cfg: dict[str, Any]) -> FixAction:
    if rule_id == "A1":
        title = f"Assign Base UoM for {entity}"
        desc = f"Update MARA-MEINS to standard base unit of measure and recalculate conversion ratios."
    elif rule_id == "A2":
        title = f"Recalculate reorder point for {entity}"
        desc = f"Recalculate MARC-MINBE based on historical consumption and lead times to resume automated replenishment."
    elif rule_id == "A3":
        title = f"Deduplicate description for {entity}"
        desc = f"Standardize description in MAKT to remove ambiguity and prevent picking errors."
    elif rule_id == "A4":
        title = f"Rebalance safety stock threshold for {entity}"
        desc = f"Adjust safety stock below reorder point in MARC to restore correct replenishment alerting."
    elif rule_id == "A5":
        title = f"Purge obsolete material {entity} from open orders"
        desc = f"Cancel open order lines and re-allocate active substitute materials."
    elif rule_id in ("A6", "C4"):
        title = f"Transfer hazmat {entity} to certified HAZ bin"
        desc = f"Execute immediate transfer order to designated hazardous material storage location complying with EHS."
    elif rule_id == "B1":
        title = f"Reconcile inventory balance for {entity}"
        desc = f"Perform physical cycle count, investigate timing of goods issue, and post inventory adjustment in MARD."
    elif rule_id == "B2":
        title = f"Quarantine expired batch {f.get('batch', '')} of {entity}"
        desc = f"Execute movement 344 in SAP MARD to transfer {f.get('qty_on_hand', 0)} EA to blocked stock."
    elif rule_id == "B4":
        title = f"Initiate disposition review for stale {entity}"
        desc = f"Evaluate dormant stock ({f.get('qty_on_hand', 0)} EA) for inter-plant transfer, vendor return, or write-off."
    elif rule_id == "B5":
        title = f"Realign blocked stock ledger for {entity}"
        desc = f"Reconcile blocked stock quantities in MARD against active inspection lots."
    elif rule_id == "C1":
        title = f"Re-slot excess inventory from bin {f.get('bin', entity)}"
        desc = f"Create putaway relocation tasks to transfer overflow volume to open reserve racking."
    elif rule_id == "C2":
        title = f"Synchronize bin {f.get('bin', entity)} occupancy status"
        desc = f"Update WMS bin status ledger to match actual physical bin availability."
    elif rule_id == "D2":
        title = f"Assign transport carrier route for {entity}"
        desc = f"Determine optimal carrier route in LIKP-ROUTE to book transport and release picking."
    elif rule_id == "D3":
        title = f"Expedite outbound dispatch for {entity}"
        desc = f"Prioritize dock staging at Plant {plant}, alert carrier dispatch, and execute Post Goods Issue (VL02N)."
    elif rule_id == "D5":
        title = f"Reassign correct freight route for {entity}"
        desc = f"Update delivery route assignment to match customer destination classification and avoid tariff penalties."
    elif rule_id == "E1":
        title = f"Enroll vendor {f.get('vendor', '')} in Vendor Master"
        desc = f"Create vendor master record in LFA1 with verified tax and banking information or reassign PO."
    elif rule_id == "E2":
        title = f"Update contract pricing for PO {entity}"
        desc = f"Apply purchasing info record contract pricing to clear invoice verification blocks."
    elif rule_id == "E3":
        title = f"Reschedule delivery date for PO {entity}"
        desc = f"Update expected delivery date to respect chronological order lead time."
    elif rule_id == "E4":
        title = f"Expedite delayed PO {entity} with supplier"
        desc = f"Issue supplier delivery notice and evaluate secondary source allocation."
    elif rule_id == "F1":
        title = f"Update country classification for vendor {entity}"
        desc = f"Add ISO country code in LFA1-LAND1 to satisfy tax and trade compliance rules."
    elif rule_id == "F2":
        title = f"Cancel open POs with blocked vendor {entity}"
        desc = f"Enforce compliance controls by cancelling open POs with blocked vendor and rerouting demand."
    elif rule_id == "X1":
        title = f"Publish Material Master record for {entity}"
        desc = f"Synchronize WMS and ERP by creating master record in MARA/MARC with Plant {plant} parameters."
    elif rule_id == "X2":
        title = f"Allocate buffer stock for {entity}"
        desc = f"Initiate expedited stock transfer to clear {f.get('shortfall', 0)} EA ATP deficit."
    else:
        title = f"Resolve {cfg['title']} for {entity}"
        desc = f.get("detail") or f"Apply standard operating remediation protocol for {cfg['title']}."

    return FixAction(
        id=f"FX-{rule_id}-{idx+1}",
        title=title,
        owner="Operations Controller" if severity == "critical" else "Logistics Supervisor",
        eta="1h" if horizon in ("1h", "4h") else "1 shift",
        confidence=92,
        description=desc,
        impact_saved=int(imp * 0.85),
    )


def _build_cascade_nodes(rule_id: str, f: dict[str, Any], entity: str, plant: str, idx: int, imp: int, severity: str, horizon: str, cfg: dict[str, Any]) -> list[CascadeNode]:
    slug = f"{rule_id}-{entity}-{idx}".replace(" ", "_")
    src_id = f"{slug}-src"
    proc_id = f"{slug}-proc"
    risk_id = f"{slug}-risk"
    out_id = f"{slug}-out"

    if rule_id == "X1":
        return [
            CascadeNode(id=src_id, label=f"Orphan Master Record ({entity})", kind="source", health="critical", impact=0, detail=f"{entity} missing from MARA master table"),
            CascadeNode(id=proc_id, label="Putaway & Picking Execution", kind="process", health="risk", impact=int(imp * 0.25), detail="Barcode scanners reject unrecognised material"),
            CascadeNode(id=risk_id, label="Goods Issue Block", kind="risk", health="critical", impact=int(imp * 0.55), detail="SAP ERP blocks delivery confirmation"),
            CascadeNode(id=out_id, label="Production Line Shutdown", kind="outcome", health="critical", impact=imp, detail=f"Modeled exposure €{imp:,}"),
        ]
    elif rule_id == "X2":
        return [
            CascadeNode(id=src_id, label=f"ATP Stock Shortfall ({entity})", kind="source", health="critical", impact=0, detail=f"Shortfall of {f.get('shortfall', 0)} EA at Plant {plant}"),
            CascadeNode(id=proc_id, label="Order Picking Starvation", kind="process", health="risk", impact=int(imp * 0.25), detail="Picking waves stalled across open deliveries"),
            CascadeNode(id=risk_id, label="Dispatch Staging Delay", kind="risk", health="critical", impact=int(imp * 0.55), detail="Vehicles holding at loading dock"),
            CascadeNode(id=out_id, label="Customer Contractual Penalties", kind="outcome", health="critical", impact=imp, detail=f"Modeled exposure €{imp:,}"),
        ]
    elif rule_id == "D3":
        return [
            CascadeNode(id=src_id, label=f"Overdue Goods Issue ({entity})", kind="source", health="critical", impact=0, detail=f"Planned GI date {f.get('planned_gi_date', 'past')} missed"),
            CascadeNode(id=proc_id, label="Dock Loading Stoppage", kind="process", health="risk", impact=int(imp * 0.25), detail=f"Stalled outbound shipping at Plant {plant}"),
            CascadeNode(id=risk_id, label="Customer Delivery Breach", kind="risk", health="critical", impact=int(imp * 0.55), detail=f"Route {f.get('route', 'domestic')} delayed"),
            CascadeNode(id=out_id, label="Customer Penalty & Revenue Loss", kind="outcome", health="critical", impact=imp, detail=f"Modeled exposure €{imp:,}"),
        ]
    elif rule_id == "B2":
        return [
            CascadeNode(id=src_id, label=f"Expired Batch ({f.get('batch', entity)})", kind="source", health="critical", impact=0, detail=f"Batch expired on {f.get('batch_expiry', 'past')}"),
            CascadeNode(id=proc_id, label="Picking Verification Failure", kind="process", health="risk", impact=int(imp * 0.25), detail=f"Unquarantined expired stock in active bin"),
            CascadeNode(id=risk_id, label="Quality Recall Exposure", kind="risk", health="critical", impact=int(imp * 0.55), detail="Risk of dispatching expired component"),
            CascadeNode(id=out_id, label="Scrap & Compliance Liability", kind="outcome", health="critical", impact=imp, detail=f"Modeled exposure €{imp:,}"),
        ]
    elif rule_id == "B1":
        return [
            CascadeNode(id=src_id, label=f"Negative Stock Posting ({entity})", kind="source", health="critical", impact=0, detail=f"Book balance {f.get('qty_on_hand', 0)} EA in MARD"),
            CascadeNode(id=proc_id, label="Inventory Desynchronization", kind="process", health="risk", impact=int(imp * 0.25), detail="GI posted prior to physical GR receipt"),
            CascadeNode(id=risk_id, label="Phantom Order Fulfillment", kind="risk", health="critical", impact=int(imp * 0.55), detail="Allocations made against non-existent physical stock"),
            CascadeNode(id=out_id, label="Physical Stockout & Audit Discrepancy", kind="outcome", health="critical", impact=imp, detail=f"Modeled exposure €{imp:,}"),
        ]
    else:
        return [
            CascadeNode(id=src_id, label=f"{cfg['title']} Source", kind="source", health="critical" if severity == "critical" else "risk", impact=0, detail=f.get("detail", "Root trigger")),
            CascadeNode(id=proc_id, label="Process Execution Bottleneck", kind="process", health="risk", impact=int(imp * 0.25), detail=f"Impacts {cfg['sys']} operational workflow"),
            CascadeNode(id=risk_id, label="Operational Disruption Risk", kind="risk", health="critical" if severity in ("critical", "high") else "watch", impact=int(imp * 0.55), detail="Propagation across dependent orders"),
            CascadeNode(id=out_id, label="Financial & SLA Exposure", kind="outcome", health="critical", impact=imp, detail=f"Potential loss €{imp:,}"),
        ]


def convert_findings_to_anomalies(findings_by_rule: dict[str, list[dict[str, Any]]] | list[dict[str, Any]]) -> list[Anomaly]:
    """Transform raw dictionary findings from run_all_detectors into Pydantic Anomaly models."""
    if isinstance(findings_by_rule, list):
        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in findings_by_rule:
            cid = item.get("catalog_id", "OTHER")
            grouped.setdefault(cid, []).append(item)
        findings_by_rule = grouped

    anomalies: list[Anomaly] = []
    now = datetime(2026, 9, 5, 8, 30, tzinfo=timezone.utc)

    for rule_id, rule_findings in sorted(findings_by_rule.items()):
        cfg = RULE_CONFIG.get(rule_id, {
            "domain": "Operational Integrity",
            "title": f"Rule {rule_id} Finding",
            "horizon": "12h",
            "base_impact": 25000,
            "sys": "SAP ECC / S/4HANA",
        })

        for idx, f in enumerate(rule_findings):
            if rule_id.startswith("F") or rule_id == "E1":
                entity = f.get("vendor") or f.get("material") or f"ENT-{idx}"
            elif rule_id.startswith("D"):
                entity = f.get("delivery") or f.get("material") or f"ENT-{idx}"
            elif rule_id.startswith("C"):
                entity = f.get("bin") or f.get("assigned_material") or f"ENT-{idx}"
            elif rule_id.startswith("E"):
                entity = f.get("purchase_order") or f.get("material") or f.get("vendor") or f"ENT-{idx}"
            else:
                entity = f.get("material") or f.get("delivery") or f.get("vendor") or f"ENT-{idx}"
            severity = f.get("severity", "medium").lower()
            plant = str(f.get("plant") or ("1710" if idx % 2 == 1 else "1010"))
            site = "bratislava" if plant == "1710" else "wolfsburg"

            # Dynamic impact calculation
            base_imp = cfg["base_impact"]
            if rule_id == "X2" and f.get("shortfall"):
                imp = max(5000, int(abs(float(f["shortfall"])) * 45))
            elif rule_id == "B1" and f.get("qty_on_hand"):
                imp = max(10000, int(abs(float(f["qty_on_hand"])) * 120))
            elif rule_id == "C1" and f.get("occupied") and f.get("capacity"):
                overflow = float(f["occupied"]) - float(f["capacity"])
                imp = max(5000, int(overflow * 85))
            elif rule_id == "D3" and f.get("overdue_days"):
                imp = max(8000, int(float(f["overdue_days"]) * 3500))
            else:
                sev_multipliers = {"critical": 1.5, "high": 1.0, "medium": 0.5, "low": 0.25}
                imp = int(base_imp * sev_multipliers.get(severity, 1.0))

            # Horizon alignment with UI buckets
            horizon = cfg["horizon"]
            if severity == "critical" and rule_id in {"B1", "D3"}:
                horizon = "1h"
            elif severity == "critical" and rule_id in {"A5", "C1"}:
                horizon = "4h"

            # Evidence collection
            ev_list = []
            for k, v in f.items():
                if k in ("catalog_id", "severity"):
                    continue
                ev_list.append(Evidence(label=k.replace("_", " ").title(), value=str(v), source=cfg["sys"]))
            if not ev_list:
                ev_list.append(Evidence(label="Detail", value=f.get("detail", "Anomaly identified"), source=cfg["sys"]))

            slug = f"{rule_id}-{entity}-{idx}".replace(" ", "_")
            src_id = f"{slug}-src"
            proc_id = f"{slug}-proc"
            risk_id = f"{slug}-risk"
            out_id = f"{slug}-out"

            nodes = _build_cascade_nodes(rule_id, f, entity, plant, idx, imp, severity, horizon, cfg)
            edges = [
                CascadeEdge(source=src_id, target=proc_id, label="triggers", probability=90),
                CascadeEdge(source=proc_id, target=risk_id, label="propagates", probability=85),
                CascadeEdge(source=risk_id, target=out_id, label="compounds", probability=80),
            ]

            actions = [_build_fix_action(rule_id, f, entity, plant, idx, imp, severity, horizon, cfg)]
            root_cause = _build_root_cause(rule_id, f, entity, plant)

            anomalies.append(Anomaly(
                id=f"HAC-{rule_id}-{entity}-{idx}",
                site_id=site,
                title=f"{cfg['title']}: {entity}",
                type=cfg["domain"],
                severity=severity,
                status="open",
                system=cfg["sys"],
                zone=f"Plant {plant}",
                sku=str(entity if (rule_id.startswith("F") or rule_id == "E1") else (f.get("material") or entity)),
                detected_at=now,
                time_to_impact=horizon,
                impact=imp,
                confidence=95,
                summary=f.get("detail") or f"{cfg['title']} on {entity} requires immediate review.",
                root_cause=root_cause,
                evidence=ev_list[:5],
                actions=actions,
                cascade_nodes=nodes,
                cascade_edges=edges,
            ))

    return anomalies
