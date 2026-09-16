# Warehouse AI Hackathon — SAP Domain Handbook

> Reference handbook for the Nexus AI Autonomous Supply Chain Control Tower.
> This document grounds the WALT Copilot and all specialist agents in SAP
> warehouse and logistics domain knowledge for the Hackathon synthetic dataset.

---

## SAP Table Reference

| Sheet Name           | SAP Analogue    | Key Fields                                                             |
|----------------------|-----------------|------------------------------------------------------------------------|
| Material_Master      | MARA / MARC     | Material, Description, Type, Group, UoM, Plant, Reorder/Safety Stock   |
| Inventory_Stock      | MARD / MCHB     | On-hand, Blocked, In-transit qty by Plant/Storage Location/Batch       |
| Warehouse_Bin        | LAGP / LQUA     | Bin, Storage Type, Assigned Material, Capacity vs Occupancy, Status    |
| Deliveries_Dispatch  | LIKP / LIPS     | Outbound deliveries: Material, Qty, Ship-to, Route, Dates, Status     |
| Purchase_Replenish   | EKKO / EKPO     | Purchase Orders: Material, Vendor, Qty, Price, Dates, Status           |
| Vendor_Master        | LFA1            | Vendor, Name, Country, Quality Rating, On-time %, Procurement Block    |

### Key Relationships

- **Material_Master ↔ Inventory_Stock**: Linked by `material` + `plant`. Every inventory position should have a corresponding master record.
- **Material_Master ↔ Warehouse_Bin**: Linked by `assigned_material`. Bins reference materials that must exist in the master.
- **Material_Master ↔ Deliveries_Dispatch**: Linked by `material`. Deliveries reference materials for dispatch.
- **Material_Master ↔ Purchase_Replenish**: Linked by `material`. Purchase orders reference materials for replenishment.
- **Vendor_Master ↔ Purchase_Replenish**: Linked by `vendor`. POs reference vendors that must exist and be unblocked.
- **Cross-System Orphan Detection**: A material appearing in transactional sheets (Inventory, Bins, Deliveries) but missing from Material_Master indicates an ERP/WMS replication gap.

---

## Anomaly Catalog — 24 Detection Rules

### A-Series: Master Data Quality

| Rule | Name                              | Severity | What It Detects                                                                 |
|------|-----------------------------------|----------|---------------------------------------------------------------------------------|
| A1   | Missing Base UoM                  | high     | Material with blank base unit of measure — unit conversion and valuation fail.  |
| A2   | Invalid Reorder Point             | high     | Missing or negative reorder point — replenishment trigger never fires.          |
| A3   | Duplicate Description             | medium   | Multiple material IDs sharing the same description text.                         |
| A4   | Safety Stock > Reorder Point      | medium   | Safety stock exceeds reorder point — procurement logic will misfire.            |
| A5   | Obsolete Material In Use          | critical | Material with lifecycle status OBSOLETE/BLOCKED still appears in open orders.   |
| A6   | Hazmat Material Missing Hazmat Flag | medium | Material stored in a hazardous bin but not flagged as hazmat in the master.     |

### B-Series: Inventory & Batch Anomalies

| Rule | Name                              | Severity | What It Detects                                                                 |
|------|-----------------------------------|----------|---------------------------------------------------------------------------------|
| B1   | Negative Net Stock                | critical | `qty_on_hand - blocked_qty < 0` — impossible physical stock state.             |
| B2   | Expired Batch with Active Stock   | critical | Batch with stock-on-hand whose `batch_expiry` is before the snapshot date.      |
| B3   | Missing Batch Expiry Date         | medium   | Inventory row references a batch but has no expiry date set.                    |
| B4   | Dead/Stale Stock                  | low      | No movement for 365+ days — capital is tied up with no consumption.             |
| B5   | Blocked Qty Exceeds On-Hand       | high     | Blocked quantity is greater than the quantity on hand.                           |

### C-Series: Warehouse Bin Anomalies

| Rule | Name                              | Severity | What It Detects                                                                 |
|------|-----------------------------------|----------|---------------------------------------------------------------------------------|
| C1   | Bin Over-Capacity                 | critical | `occupied > capacity` — physical overflow risk and safety hazard.               |
| C2   | Bin Status vs Occupied Mismatch   | medium   | Bin status says EMPTY/BLOCKED but occupied quantity is non-zero.                |
| C3   | Unassigned Bin with Stock         | medium   | Bin has occupied quantity but no material assigned.                              |
| C4   | Hazmat Material in Non-HAZ Bin    | high     | Material flagged as hazmat stored in a non-HAZ storage type.                    |

### D-Series: Deliveries & Dispatch Anomalies

| Rule | Name                              | Severity | What It Detects                                                                 |
|------|-----------------------------------|----------|---------------------------------------------------------------------------------|
| D2   | Missing Transport Route           | high     | Delivery with a blank or missing route code — cannot be dispatched.             |
| D3   | Overdue Planned GI Date           | critical | Planned goods issue date has passed but delivery status is still open.          |
| D4   | Delivery Before Creation          | medium   | Planned GI date is before the creation date — data entry error.                 |
| D5   | Domestic Customer on Export Route  | medium  | Ship-to address is domestic but route is flagged as export.                     |

### E-Series: Purchase Order Anomalies

| Rule | Name                              | Severity | What It Detects                                                                 |
|------|-----------------------------------|----------|---------------------------------------------------------------------------------|
| E1   | Orphan Vendor in PO               | high     | PO references a vendor not present in Vendor_Master.                            |
| E2   | Zero-Price Purchase Order         | medium   | PO line item has unit price = 0 — valuation and cost analysis will fail.        |
| E3   | Delivery Before Order Date        | medium   | PO expected delivery date is before the order date — impossible timeline.       |
| E4   | Overdue Open PO                   | high     | PO expected delivery date has passed but status remains open.                   |

### F-Series: Vendor Master Anomalies

| Rule | Name                              | Severity | What It Detects                                                                 |
|------|-----------------------------------|----------|---------------------------------------------------------------------------------|
| F1   | Missing Vendor Country            | medium   | Vendor record has no country — compliance and tax routing cannot proceed.       |
| F2   | Blocked Vendor with Open POs      | critical | Vendor has procurement block = YES but open purchase orders still exist.        |

### X-Series: Cross-System Anomalies

| Rule | Name                              | Severity | What It Detects                                                                 |
|------|-----------------------------------|----------|---------------------------------------------------------------------------------|
| X1   | Orphan Material (Cross-System)    | critical | Material appears in Inventory/Bins/Deliveries but not in Material_Master.       |
| X2   | ATP Stockout Deficit              | critical | Available-to-Promise (on-hand − blocked − committed) is negative or zero.      |

---

## Standard Operating Procedures

### SOP-01: Resolve Cross-System Orphan Material

**Trigger**: Rule X1 detects material codes in transactional sheets with no master record.

1. **Verify** the orphan material code in all source systems (ERP, WMS, TMS).
2. **Determine root cause**: ERP/WMS replication failure, manual data entry, or migration artifact.
3. **Create** the missing master record in Material_Master with correct attributes (UoM, plant, reorder point, safety stock).
4. **Reconcile** inventory positions, bin assignments, and open deliveries referencing the orphan.
5. **Validate** ATP calculations are now accurate after master record creation.
6. **Human approval required** before committing any master data changes.

### SOP-02: Remediate Hazmat Storage Violations

**Trigger**: Rules A6 (hazmat flag mismatch) or C4 (hazmat material in non-HAZ bin).

1. **Quarantine** the affected bin immediately — prevent further picks or putaways.
2. **Verify** the material's SDS (Safety Data Sheet) classification.
3. **Transfer** the material to an approved HAZ storage type bin with appropriate handling equipment.
4. **Update** the Material_Master hazmat flag if the master record is incorrect.
5. **Log** the incident in the quality management system for regulatory compliance.
6. **Human approval required** for both the physical transfer and any master data corrections.

### SOP-03: Resolve ATP Stockout Deficit

**Trigger**: Rule X2 detects materials where `qty_on_hand - blocked_qty - committed_deliveries ≤ 0`.

1. **Calculate** the net ATP shortfall: `ATP = on_hand - blocked - Σ(open_delivery_qty)`.
2. **Check** open purchase orders for incoming replenishment with expected delivery dates.
3. **Prioritize** deliveries by customer SLA urgency — delay non-critical shipments if necessary.
4. **Expedite** open POs with the vendor or place emergency procurement.
5. **Communicate** delay risk to affected dispatch planners and customer service.
6. **Human approval required** before rescheduling any customer delivery.

### SOP-04: Handle Blocked Vendor with Open POs

**Trigger**: Rule F2 detects vendors with `procurement_block = YES` but open purchase orders.

1. **Review** the procurement block reason (quality, payment, compliance, or administrative).
2. **Assess** the criticality of open POs — are the materials sole-sourced or multi-sourced?
3. **Either** resolve the block condition (e.g., payment terms) and unblock the vendor, **or** redirect the PO to an approved alternative vendor.
4. **Cancel** or amend POs that cannot be fulfilled by the blocked vendor.
5. **Update** the Vendor_Master record with the resolution and unblock timestamp.
6. **Human approval required** before unblocking or redirecting purchase orders.

### SOP-05: Quarantine Expired Batch Stock

**Trigger**: Rule B2 detects batches with `batch_expiry < snapshot_date` and `qty_on_hand > 0`.

1. **Block** the expired batch immediately — set blocked_qty = qty_on_hand.
2. **Prevent** any picks from the expired batch via WMS hold.
3. **Assess** disposal or rework options based on material type and regulatory requirements.
4. **Coordinate** with Quality & Compliance for disposition approval.
5. **Write off** or return the stock and update the inventory journals.
6. **Human approval required** before any disposition or write-off action.

### SOP-06: Correct Bin Capacity Overflow

**Trigger**: Rule C1 detects bins where `occupied > capacity`.

1. **Verify** the physical state of the bin — is it truly overfilled or is the data stale?
2. **Redistribute** excess material to bins with available capacity in the same storage type.
3. **Update** the Warehouse_Bin occupied quantity to reflect the true physical state.
4. **Review** putaway strategy rules to prevent future overflow.
5. **Log** the capacity breach in the warehouse operations incident register.
6. **Human approval required** before any bin reassignment or capacity adjustment.

---

## Business Impact Scoring

| Impact Dimension         | How It Is Calculated                                                      |
|--------------------------|---------------------------------------------------------------------------|
| Financial Exposure (€)   | `unit_price × qty_at_risk` or estimated carrying cost for stale stock.    |
| SLA Breach Risk          | Days overdue × daily penalty rate for affected deliveries.                |
| Compliance Exposure      | Regulatory fine potential for hazmat violations or expired goods shipment. |
| Working Capital Tied Up  | Carrying cost of dead stock, blocked stock, or overstocked bins.          |

---

## Human-in-the-Loop Governance

Every corrective action proposed by WALT or any specialist agent follows the **suggest-then-approve** pattern:

1. **Detection**: Autonomous agents detect the anomaly and score its business impact.
2. **Recommendation**: The Fix agent proposes a concrete remediation with owner, ETA, and confidence %.
3. **Preview**: The operator reviews the proposed action, evidence chain, and downstream impact.
4. **Approval**: A human operator or manager explicitly approves or rejects the action.
5. **Execution**: Only after human approval is the corrective action committed to source systems.
6. **Audit**: The full decision trail (who detected, who approved, what changed) is immutably logged.

> **No agent is permitted to mutate live master data, inventory positions, or vendor records without explicit human approval.**

---

## Dataset Snapshot Reference

- **Snapshot Date**: 05 September 2026 (used for all overdue, expired, and stale calculations).
- **Plants**: 1010 (primary), 1710 (secondary).
- **Seeded Anomaly Entities**: MAT-999001 (orphan material), VEND-9999 (orphan vendor), VEND-5000 (blocked vendor).
- **Total Anomalies Detected**: ~209 findings across all 24 catalog rules.
