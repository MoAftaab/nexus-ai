"""Interactive CLI scanner for the hackathon workbook."""
from __future__ import annotations

import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.hackathon_ingest import load_hackathon_workbook
from app.services.hackathon_detectors import run_all_detectors, SNAPSHOT_DATE

DEFAULT_XLSX = Path(r"C:\Users\Mohd Aftaab\Downloads\Telegram Desktop\Warehouse_AI_Hackathon_Synthetic_Dataset_FINAL 2.xlsx")


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_XLSX
    if not path.exists():
        print(f"[ERROR] Excel workbook not found at: {path}")
        sys.exit(1)

    print("=" * 75)
    print("      NEXUS-AI: HACKATHON WORKBOOK OPERATIONAL SCAN")
    print(f"      Snapshot Reference Date: {SNAPSHOT_DATE}")
    print(f"      File: {path.name}")
    print("=" * 75)

    print("\n[1/2] Ingesting SAP sheets...")
    data = load_hackathon_workbook(path)
    sheet_counts = {
        "Material Master": len(data["material_master"]),
        "Inventory Stock": len(data["inventory_stock"]),
        "Warehouse Bin": len(data["warehouse_bin"]),
        "Deliveries Dispatch": len(data["deliveries_dispatch"]),
        "Purchase Replenish": len(data["purchase_replenish"]),
        "Vendor Master": len(data["vendor_master"]),
    }
    for name, count in sheet_counts.items():
        print(f"  • {name:22s} : {count:3d} records")

    print("\n[2/2] Running 24 catalog anomaly detector rules...")
    findings_by_rule = run_all_detectors(data)

    descriptions = {
        "A1": "Missing Base UoM",
        "A2": "Invalid/Negative Reorder Point",
        "A3": "Duplicate Material Descriptions",
        "A4": "Safety Stock > Reorder Point",
        "A5": "Obsolete/Blocked Material in Active Open Delivery/PO",
        "A6": "Hazmat Handling Storage Mismatch",
        "B1": "Negative On-Hand Stock (Book/Physical Desync)",
        "B2": "Expired Batch with On-Hand Stock",
        "B4": "Stale/Dead Stock (>365 Days Inactive)",
        "B5": "Blocked Quantity Exceeds Total On-Hand",
        "C1": "Bin Over-Capacity (Occupied > Capacity)",
        "C2": "Bin Status/Occupancy Inconsistency",
        "C4": "Hazmat Material Stored in Non-HAZ Bin",
        "D2": "Delivery Missing Assigned Shipping Route",
        "D3": "Overdue Planned Goods Issue (Past 2026-09-05)",
        "D5": "Export Route Used on Domestic Customer",
        "E1": "Orphan Vendor Referenced in Purchase Order",
        "E2": "Zero or Missing PO Unit Price",
        "E3": "Purchase Order Expected Delivery Before Order Date",
        "E4": "Overdue Open Purchase Order (Past 2026-09-05)",
        "F1": "Vendor Missing Country in Vendor Master",
        "F2": "Procurement-Blocked Vendor with Open/Partial PO",
        "X1": "Cross-System Orphan Material (No Master Record)",
        "X2": "Commitment Deficit: Demand Exceeds Net Available ATP",
    }

    print("\n" + "-" * 75)
    print(f"{'Rule':<6} {'Description':<42} {'Count':<7} {'Severity Breakdown'}")
    print("-" * 75)

    total_findings = 0
    crit_count = 0
    high_count = 0

    for rule_code, flist in sorted(findings_by_rule.items()):
        cnt = len(flist)
        total_findings += cnt
        sevs = {}
        for item in flist:
            s = item.get("severity", "medium")
            sevs[s] = sevs.get(s, 0) + 1
            if s == "critical":
                crit_count += 1
            elif s == "high":
                high_count += 1
        sev_str = ", ".join(f"{k.upper()}: {v}" for k, v in sorted(sevs.items()))
        desc = descriptions.get(rule_code, rule_code)
        print(f"{rule_code:<6} {desc:<42} {cnt:<7} {sev_str}")

    print("-" * 75)
    print(f"TOTAL FINDINGS: {total_findings} | CRITICAL: {crit_count} | HIGH: {high_count}")
    print("=" * 75)

    print("\n--- Key High-Impact Seeded Findings Highlight ---")
    if findings_by_rule.get("X1"):
        x1 = findings_by_rule["X1"][0]
        print(f"  [X1] Orphan Material: {x1.get('material')} across {x1.get('present_in_sheets')} (no Material Master record)")
    if findings_by_rule.get("E1"):
        e1 = findings_by_rule["E1"][0]
        print(f"  [E1] Orphan Vendor:   PO {e1.get('purchase_order')} references unknown vendor {e1.get('vendor')}")
    if findings_by_rule.get("B1"):
        b1 = findings_by_rule["B1"][0]
        print(f"  [B1] Negative Stock:  {b1.get('material')} at Plant {b1.get('plant')} has on-hand qty {b1.get('qty_on_hand')}")
    if findings_by_rule.get("B2"):
        b2 = findings_by_rule["B2"][0]
        print(f"  [B2] Expired Batches: Found {len(findings_by_rule['B2'])} expired batches (e.g. {b2.get('material')} batch {b2.get('batch')} expired {b2.get('batch_expiry')})")
    if findings_by_rule.get("C1"):
        print(f"  [C1] Bin Overflow:    {len(findings_by_rule['C1'])} bins exceed 100% capacity limit")
    if findings_by_rule.get("X2"):
        x2 = findings_by_rule["X2"][0]
        print(f"  [X2] ATP Deficit:     {x2.get('material')}@{x2.get('plant')} committed={x2.get('committed_qty')}, net_atp={x2.get('net_atp')}, shortfall={x2.get('shortfall')}")
    print("=" * 75)


if __name__ == "__main__":
    main()
