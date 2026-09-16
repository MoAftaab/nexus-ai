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


def convert_findings_to_anomalies(findings_by_rule: dict[str, list[dict[str, Any]]] | list[dict[str, Any]]) -> list[Anomaly]:
    """Transform raw dictionary findings from run_all_detectors into Pydantic Anomaly models.

    Ensures every finding has:
      • Deterministic, stable anomaly ID
      • Corroborating evidence rows
      • Realistic euro exposure calculation
      • Actionable Fix Actions with human approval owners
      • Multi-hop Cascade Graph (Source -> Process -> Risk -> Outcome)
      • Standardized time_to_impact aligned with UI Horizon buckets (<2h, 2-8h, 8-24h, >24h)
    """
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

            # Cascade DAG (Source -> Process -> Risk -> Outcome)
            slug = f"{rule_id}-{entity}-{idx}".replace(" ", "_")
            src_id = f"{slug}-src"
            proc_id = f"{slug}-proc"
            risk_id = f"{slug}-risk"
            out_id = f"{slug}-out"

            if rule_id == "X1":
                nodes = [
                    CascadeNode(id=src_id, label="Orphan Master Record (SKU)", kind="source", health="critical", impact=0, detail=f"{entity} missing in master data"),
                    CascadeNode(id=proc_id, label="Putaway & Picking Execution", kind="process", health="risk", impact=int(imp * 0.25), detail="Barcode scanners reject unrecognised material"),
                    CascadeNode(id=risk_id, label="GI & Invoicing Halt", kind="risk", health="critical", impact=int(imp * 0.55), detail="Post Goods Issue blocked by SAP validation"),
                    CascadeNode(id=out_id, label="Customer Delivery Shutdown", kind="outcome", health="critical", impact=imp, detail="OEM customer stockout penalties"),
                ]
            else:
                nodes = [
                    CascadeNode(id=src_id, label=f"{cfg['title']} Source", kind="source", health="critical" if severity == "critical" else "risk", impact=0, detail=f.get("detail", "Root trigger")),
                    CascadeNode(id=proc_id, label="Process Execution Bottleneck", kind="process", health="risk", impact=int(imp * 0.25), detail=f"Impacts plant {plant} operational flow"),
                    CascadeNode(id=risk_id, label="Operational Disruption Risk", kind="risk", health="critical" if severity in ("critical", "high") else "watch", impact=int(imp * 0.55), detail="Propagation to dependent orders"),
                    CascadeNode(id=out_id, label="Financial & SLA Exposure", kind="outcome", health="critical", impact=imp, detail=f"Potential loss €{imp:,}"),
                ]
            edges = [
                CascadeEdge(source=src_id, target=proc_id, label="triggers", probability=90),
                CascadeEdge(source=proc_id, target=risk_id, label="propagates", probability=85),
                CascadeEdge(source=risk_id, target=out_id, label="compounds", probability=80),
            ]

            actions = [
                FixAction(
                    id=f"FX-{rule_id}-{idx+1}",
                    title=f"Resolve {cfg['title']} for {entity}",
                    owner="Operations Controller" if severity == "critical" else "Logistics Supervisor",
                    eta="1h" if horizon in ("1h", "4h") else "1 shift",
                    confidence=92,
                    description=f"Apply remediation protocol for {f.get('detail', cfg['title'])}.",
                    impact_saved=int(imp * 0.85),
                )
            ]

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
                root_cause=f.get("root_cause") or f"System state failed validation rule {rule_id}.",
                evidence=ev_list[:5],
                actions=actions,
                cascade_nodes=nodes,
                cascade_edges=edges,
            ))

    return anomalies
