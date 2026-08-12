from __future__ import annotations

from app.services.operations import (
    detect_blocked_restricted_stock,
    detect_deletion_maintenance_flags,
    detect_fiscal_year_desync,
    detect_storage_location_fragmentation,
    detect_unreconciled_inventory,
)


def test_fiscal_year_desync_severity_impact_evidence_and_grouping(sap_record):
    rows = [sap_record(id=f"SAP-{year}", fiscalyearofcurrentperiod=year, storagelocation=f"L{year}") for year in (2022, 2023, 2024)]
    findings = detect_fiscal_year_desync(rows)
    assert {finding.severity for finding in findings} == {"critical", "high", "medium"}
    assert all(15_000 <= finding.impact <= 85_000 for finding in findings)
    assert all(any("fiscalyearofcurrentperiod" in evidence.label for evidence in finding.evidence) for finding in findings)
    assert all(any(row["storagelocation"] in evidence.value for evidence in finding.evidence) for row, finding in zip(rows, findings))
    assert any(any("Period-Close" in node.label for node in finding.cascade_nodes) for finding in findings)


def test_fiscal_year_desync_does_not_flag_active_or_malformed_records(sap_record):
    rows = [sap_record(fiscalyearofcurrentperiod=2026, currentperiod="12"), sap_record(id="SAP-2", fiscalyearofcurrentperiod="", currentperiod="12"), sap_record(id="SAP-3", fiscalyearofcurrentperiod=None)]
    assert detect_fiscal_year_desync(rows) == []


def test_physical_inventory_flags_zero_old_and_invalid_counts_but_not_recent(sap_record):
    rows = [
        sap_record(dateoflastpostedcount="00000000"),
        sap_record(id="SAP-2", dateoflastpostedcount="20240101"),
        sap_record(id="SAP-3", dateoflastpostedcount="20260601"),
        sap_record(id="SAP-4", dateoflastpostedcount="not-a-date"),
    ]
    findings = detect_unreconciled_inventory(rows)
    assert findings
    assert 25_000 <= findings[0].impact <= 120_000
    assert any("dateoflastpostedcount" in evidence.label for evidence in findings[0].evidence)
    assert any("FBM1" in evidence.value for evidence in findings[0].evidence)


def test_physical_inventory_batch_critical_threshold_and_single_posted_record(sap_record):
    rows = [sap_record(id=f"SAP-{index}", storagelocation="BN99", dateoflastpostedcount="00000000") for index in range(20)]
    finding = detect_unreconciled_inventory(rows)[0]
    assert finding.severity == "critical"
    assert "Ghost Inventory" in finding.cascade_nodes[0].label
    assert detect_unreconciled_inventory([sap_record(dateoflastpostedcount="20260601")]) == []


def test_blocked_stock_detector_exact_quantities_impact_and_aggregation(sap_record):
    rows = [
        sap_record(blockedstock=10, freeavailablestock=0),
        sap_record(id="SAP-2", stockinqualityinspection=7, freeavailablestock=0),
        sap_record(id="SAP-3", blockedstock=8, freeavailablestock=101),
        sap_record(id="SAP-4", stockintransfer=99, freeavailablestock=0),
    ]
    findings = detect_blocked_restricted_stock(rows)
    assert findings
    assert 18_000 <= findings[0].impact <= 95_000
    values = " ".join(evidence.value for evidence in findings[0].evidence)
    assert "10" in values and "7" in values
    assert "17" in values
    assert len(findings[0].cascade_nodes) >= 3


def test_blocked_stock_edge_values_do_not_crash_or_false_positive(sap_record):
    rows = [sap_record(blockedstock=0, stockinqualityinspection=0, freeavailablestock=0), sap_record(id="SAP-2", blockedstock=-2, freeavailablestock=-1)]
    assert detect_blocked_restricted_stock(rows) == []


def test_deletion_detector_flags_x_incomplete_maintenance_bn99_and_fix(sap_record):
    rows = [
        sap_record(deletionflag="x", storagelocation="BN99"),
        sap_record(id="SAP-2", maintenancestatus="D", storagelocation="XN12"),
        sap_record(id="SAP-3", deletionflag="", maintenancestatus="DL"),
    ]
    findings = detect_deletion_maintenance_flags(rows)
    assert findings
    assert 10_000 <= findings[0].impact <= 50_000
    assert any("BN99" in evidence.value for evidence in findings[0].evidence)
    assert any("block" in action.title.lower() for action in findings[0].actions)
    assert any(finding.severity == "critical" for finding in detect_deletion_maintenance_flags([sap_record(deletionflag="X", freeavailablestock=5)]))


def test_deletion_detector_handles_empty_and_none_flags(sap_record):
    assert detect_deletion_maintenance_flags([sap_record(deletionflag=None, maintenancestatus="DL")]) == []


def test_fragmentation_detector_boundary_real_material_and_evidence(sap_record):
    exactly_15 = [sap_record(id=f"15-{i}", material="HEALTHY", storagelocation=f"L{i}", freeavailablestock=0) for i in range(15)]
    exactly_16 = [sap_record(id=f"16-{i}", material="FRAGMENTED", storagelocation=f"L{i}", freeavailablestock=0) for i in range(16)]
    real = [sap_record(id=f"R-{i}", material="0DD311159B", storagelocation=f"R{i}", freeavailablestock=0) for i in range(18)]
    assert detect_storage_location_fragmentation(exactly_15) == []
    findings = detect_storage_location_fragmentation(exactly_16 + real)
    assert len(findings) == 2
    assert all(12_000 <= finding.impact <= 45_000 for finding in findings)
    fragmented = next(finding for finding in findings if "FRAGMENTED" in finding.title)
    real_finding = next(finding for finding in findings if "0DD311159B" in finding.title)
    assert any("L15" in evidence.value for evidence in fragmented.evidence)
    assert any("R17" in evidence.value for evidence in real_finding.evidence)


def test_fragmentation_requires_zero_stock(sap_record):
    rows = [sap_record(id=f"SAP-{i}", material="STOCKED", storagelocation=f"L{i}", freeavailablestock=1) for i in range(20)]
    assert detect_storage_location_fragmentation(rows) == []
