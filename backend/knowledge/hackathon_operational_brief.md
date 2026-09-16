# Hackathon Operational Brief

> Auto-generated when the SAP hackathon dataset was loaded.

## Dataset Scope

- **61** materials across **3** plants (1010, 1020, 1710)
- **82** inventory stock positions
- **50** warehouse bins
- **120** delivery/dispatch records
- **80** purchase/replenishment orders
- **25** vendors (VEND-5000, VEND-5001, VEND-5002, VEND-5003, VEND-5004…)

## Anomaly Summary

**209** total findings detected across 24 catalog rules:

- **Critical**: 73
- **High**: 55
- **Medium**: 80
- **Low**: 1

### Top Detection Rules

- **D3**: 48 findings
- **E4**: 30 findings
- **D5**: 23 findings
- **C1**: 22 findings
- **B4**: 16 findings
- **F2**: 15 findings

## Key Entities Under Watch

- **MAT-999001**: Orphan material — exists in transactional systems (Inventory, Bins, Deliveries) but missing from Material_Master. ERP/WMS replication gap.
- **VEND-9999**: Orphan vendor — referenced in open purchase orders but absent from Vendor_Master.
- **VEND-5000**: Blocked vendor — procurement block active but open purchase orders still exist.
- **Plant 1010** and **Plant 1710**: Primary and secondary plants with ATP stockout deficits.

## Snapshot Date

All overdue, expired, and stale calculations use **05 September 2026** as the reference date.

## Governance

All corrective actions require human approval before source data changes. The audit trail records what was detected, why, what action was proposed, by which agent, and who approved it.
