"""Phase 2 Test Suite: Cascade Simulation, Topology, and Impact Horizon Engine.

Covers CAS-TOP-01 through CAS-GEN-03 (18 test cases).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
import networkx as nx
import pytest

from app.models import Anomaly, CascadeEdge, CascadeNode, Evidence, FixAction
from app.services.cascade_engine import CascadeEngine
from app.services.hackathon_adapter import convert_findings_to_anomalies


def _parse_frontend_minutes(time_str: str) -> int:
    """Mirrors the exact frontend minutesToImpact() function from dashboardKpis.js."""
    text = str(time_str or "").strip().lower()
    m_days = re.search(r"([\d.]+)\s*d", text)
    m_hours = re.search(r"([\d.]+)\s*h", text)
    m_mins = re.search(r"([\d.]+)\s*m", text)
    days = float(m_days.group(1)) if m_days else 0.0
    hours = float(m_hours.group(1)) if m_hours else 0.0
    minutes = float(m_mins.group(1)) if m_mins else 0.0
    total = int(days * 24 * 60 + hours * 60 + minutes)
    return total if total > 0 else 999999


@pytest.fixture
def sample_findings():
    """Synthetic sample findings covering X1, X2, B1, B2, C1, E1, F2, D3."""
    return {
        "X1": [{
            "catalog_id": "X1",
            "material": "MAT-999001",
            "present_in_sheets": ["Inventory_Stock", "Warehouse_Bin", "Deliveries_Dispatch"],
            "severity": "critical",
        }],
        "X2": [{
            "catalog_id": "X2",
            "material": "MAT-100003",
            "plant": "1710",
            "committed_qty": 5000.0,
            "net_atp": 215.0,
            "shortfall": 4785.0,
            "delivery_count": 3,
            "severity": "critical",
        }],
        "B1": [{
            "catalog_id": "B1",
            "material": "MAT-100003",
            "plant": "1710",
            "storage_location": "BULK",
            "qty_on_hand": -15.0,
            "in_transit_qty": 0.0,
            "severity": "critical",
        }],
        "B2": [{
            "catalog_id": "B2",
            "material": "MAT-100006",
            "plant": "1010",
            "batch": "BATCH-01",
            "batch_expiry": "2026-08-15",
            "qty_on_hand": 50.0,
            "severity": "high",
        }],
        "C1": [{
            "catalog_id": "C1",
            "bin": "WH1-A01-1",
            "storage_type": "HIGH-RACK",
            "capacity": 100.0,
            "occupied": 250.0,
            "overflow_pct": 150.0,
            "severity": "medium",
        }],
        "D3": [{
            "catalog_id": "D3",
            "delivery": "DLV-8001",
            "material": "MAT-100010",
            "plant": "1010",
            "planned_gi_date": "2026-08-20",
            "overdue_days": 16,
            "severity": "critical",
        }],
        "E1": [{
            "catalog_id": "E1",
            "purchase_order": "PO-4500005",
            "vendor": "VEND-9999",
            "material": "MAT-100020",
            "severity": "high",
        }],
        "F2": [{
            "catalog_id": "F2",
            "vendor": "VEND-5000",
            "purchase_order": "PO-4500010",
            "material": "MAT-100030",
            "po_status": "OPEN",
            "severity": "critical",
        }],
    }


# ===========================================================================
# Suite 1: Graph Topology & Multi-Hop Integrity (CAS-TOP-01 to CAS-TOP-06)
# ===========================================================================

def test_cas_top01_all_anomalies_form_strict_dag(sample_findings):
    """CAS-TOP-01: Generated cascade graph must be a valid Directed Acyclic Graph."""
    anomalies = convert_findings_to_anomalies(sample_findings)
    engine = CascadeEngine(seed=42)
    assert len(anomalies) >= 8
    for a in anomalies:
        graph = engine.build(a)
        assert nx.is_directed_acyclic_graph(graph), f"Cycle detected in anomaly graph: {a.id}"


def test_cas_top02_source_and_outcome_nodes_exist(sample_findings):
    """CAS-TOP-02: Every cascade has root sources (in-degree=0) and terminal outcomes (out-degree=0)."""
    anomalies = convert_findings_to_anomalies(sample_findings)
    engine = CascadeEngine(seed=42)
    for a in anomalies:
        graph = engine.build(a)
        roots = [n for n in graph.nodes if graph.in_degree(n) == 0]
        leaves = [n for n in graph.nodes if graph.out_degree(n) == 0]
        assert len(roots) >= 1, f"No root source in {a.id}"
        assert len(leaves) >= 1, f"No outcome leaf in {a.id}"
        assert any(graph.nodes[leaf].get("kind") == "outcome" for leaf in leaves), f"Leaf must be outcome kind in {a.id}"


def test_cas_top03_multi_hop_depth_at_least_three_for_critical(sample_findings):
    """CAS-TOP-03: Critical findings have multi-hop propagation depth >= 3."""
    anomalies = convert_findings_to_anomalies(sample_findings)
    engine = CascadeEngine(seed=42)
    critical_items = [a for a in anomalies if a.severity == "critical"]
    assert critical_items
    for a in critical_items:
        graph = engine.build(a)
        roots = [n for n in graph.nodes if graph.in_degree(n) == 0]
        leaves = [n for n in graph.nodes if graph.out_degree(n) == 0]
        max_path_len = 0
        for r in roots:
            for l in leaves:
                if nx.has_path(graph, r, l):
                    path = nx.shortest_path(graph, r, l)
                    max_path_len = max(max_path_len, len(path))
        assert max_path_len >= 4, f"Critical anomaly {a.id} depth is {max_path_len}, expected >= 4 nodes (3 hops)"


def test_cas_top04_bounded_edge_probabilities(sample_findings):
    """CAS-TOP-04: Every edge probability P satisfies 1 <= P <= 100."""
    anomalies = convert_findings_to_anomalies(sample_findings)
    for a in anomalies:
        for edge in a.cascade_edges:
            assert 1 <= edge.probability <= 100, f"Invalid probability {edge.probability} in edge {edge.source}->{edge.target}"


def test_cas_top05_outcome_carries_financial_exposure(sample_findings):
    """CAS-TOP-05: Terminal outcome node holds positive impact matching or scaling with total exposure."""
    anomalies = convert_findings_to_anomalies(sample_findings)
    for a in anomalies:
        outcome_nodes = [n for n in a.cascade_nodes if n.kind == "outcome"]
        assert outcome_nodes, f"No outcome node in {a.id}"
        total_outcome_impact = sum(n.impact for n in outcome_nodes)
        assert total_outcome_impact > 0, f"Outcome impact must be > 0 in {a.id}"
        assert total_outcome_impact >= a.impact * 0.5, f"Outcome impact should represent majority exposure in {a.id}"


def test_cas_top06_cross_system_compound_linkage(sample_findings):
    """CAS-TOP-06: Cross-system finding X1 links ERP, WMS, and Dispatch systems."""
    anomalies = convert_findings_to_anomalies(sample_findings)
    x1 = next((a for a in anomalies if "HAC-X1" in a.id), None)
    assert x1 is not None
    node_labels = " ".join(n.label.lower() for n in x1.cascade_nodes)
    assert "master" in node_labels or "sku" in node_labels
    assert "putaway" in node_labels or "picking" in node_labels
    assert "delivery" in node_labels or "gi" in node_labels or "shutdown" in node_labels


# ===========================================================================
# Suite 2: Monte-Carlo Simulation & Financial Accuracy (CAS-SIM-01 to CAS-SIM-05)
# ===========================================================================

def test_cas_sim01_reproducible_determinism(sample_findings):
    """CAS-SIM-01: Running Monte-Carlo with identical seed produces identical results."""
    anomalies = convert_findings_to_anomalies(sample_findings)
    x2 = next(a for a in anomalies if "HAC-X2" in a.id)
    engine1 = CascadeEngine(seed=1234)
    engine2 = CascadeEngine(seed=1234)
    sim1 = engine1.simulate(x2, trials=500)
    sim2 = engine2.simulate(x2, trials=500)
    assert sim1.propagation_probability == sim2.propagation_probability
    assert sim1.expected_impact == sim2.expected_impact
    assert sim1.p90_impact == sim2.p90_impact


def test_cas_sim02_monotonic_risk_damping(sample_findings):
    """CAS-SIM-02: Damping edge probabilities reduces propagation probability."""
    anomalies = convert_findings_to_anomalies(sample_findings)
    x1 = next(a for a in anomalies if "HAC-X1" in a.id)
    engine = CascadeEngine(seed=999)
    sim_base = engine.simulate(x1, trials=500)

    # Artificially damp edge probabilities to 10%
    damped = x1.model_copy(deep=True)
    for e in damped.cascade_edges:
        e.probability = max(1, int(e.probability * 0.1))
    sim_damped = engine.simulate(damped, trials=500)

    assert sim_damped.propagation_probability < sim_base.propagation_probability
    assert sim_damped.expected_impact <= sim_base.expected_impact


def test_cas_sim03_p90_greater_than_or_equal_to_expected(sample_findings):
    """CAS-SIM-03: P90 tail impact is always >= expected impact."""
    anomalies = convert_findings_to_anomalies(sample_findings)
    engine = CascadeEngine(seed=777)
    for a in anomalies:
        sim = engine.simulate(a, trials=500)
        assert sim.p90_impact >= sim.expected_impact, f"P90 ({sim.p90_impact}) < Expected ({sim.expected_impact}) in {a.id}"


def test_cas_sim04_whatif_mitigation_positive_avoided_exposure(sample_findings):
    """CAS-SIM-04: High-confidence control produces positive expected_impact_avoided."""
    anomalies = convert_findings_to_anomalies(sample_findings)
    engine = CascadeEngine(seed=555)
    for a in anomalies:
        if not a.actions:
            continue
        action = a.actions[0]
        whatif = engine.simulate_whatif(a, action)
        assert whatif["expected_impact_avoided"] >= 0
        assert whatif["mitigated"]["expected_impact"] <= whatif["baseline"]["expected_impact"]


def test_cas_sim05_empty_graph_fallback_safety():
    """CAS-SIM-05: Empty cascade nodes return 0 gracefully without exceptions."""
    empty_anomaly = Anomaly(
        id="EMPTY-01",
        title="Empty Anomaly",
        type="Test",
        severity="low",
        system="Test",
        zone="Test",
        sku="TEST-SKU",
        detected_at=datetime.now(timezone.utc),
        time_to_impact="1h",
        impact=0,
        confidence=90,
        summary="Empty",
        root_cause="None",
        evidence=[],
        actions=[],
        cascade_nodes=[],
        cascade_edges=[],
    )
    engine = CascadeEngine(seed=123)
    sim = engine.simulate(empty_anomaly)
    assert sim.trials == 1000
    assert sim.propagation_probability == 0
    assert sim.expected_impact == 0


# ===========================================================================
# Suite 3: Impact Horizon Timeline Bucketing (CAS-HOR-01 to CAS-HOR-04)
# ===========================================================================

def test_cas_hor01_immediate_under_two_hours(sample_findings):
    """CAS-HOR-01: Negative physical stock (B1) and overdue GI (D3) land in <2h bucket (<= 120 mins)."""
    anomalies = convert_findings_to_anomalies(sample_findings)
    b1 = next(a for a in anomalies if "HAC-B1" in a.id)
    d3 = next(a for a in anomalies if "HAC-D3" in a.id)
    assert _parse_frontend_minutes(b1.time_to_impact) <= 120
    assert _parse_frontend_minutes(d3.time_to_impact) <= 120


def test_cas_hor02_two_to_eight_hours_bucket(sample_findings):
    """CAS-HOR-02: Expired picking batch (B2) and bin overflow (C1) land in 2-8h bucket (121 - 480 mins)."""
    anomalies = convert_findings_to_anomalies(sample_findings)
    b2 = next(a for a in anomalies if "HAC-B2" in a.id)
    c1 = next(a for a in anomalies if "HAC-C1" in a.id)
    mins_b2 = _parse_frontend_minutes(b2.time_to_impact)
    mins_c1 = _parse_frontend_minutes(c1.time_to_impact)
    assert 120 < mins_b2 <= 480, f"B2 time '{b2.time_to_impact}' parsed as {mins_b2} mins, expected (120, 480]"
    assert 120 < mins_c1 <= 480, f"C1 time '{c1.time_to_impact}' parsed as {mins_c1} mins, expected (120, 480]"


def test_cas_hor03_eight_to_twenty_four_hours_bucket(sample_findings):
    """CAS-HOR-03: ATP shortfall (X2) lands in 8-24h bucket (481 - 1440 mins)."""
    anomalies = convert_findings_to_anomalies(sample_findings)
    x2 = next(a for a in anomalies if "HAC-X2" in a.id)
    mins_x2 = _parse_frontend_minutes(x2.time_to_impact)
    assert 480 < mins_x2 <= 1440, f"X2 time '{x2.time_to_impact}' parsed as {mins_x2} mins, expected (480, 1440]"


def test_cas_hor04_beyond_twenty_four_hours_bucket(sample_findings):
    """CAS-HOR-04: Blocked vendor on future PO (F2) and orphan vendor (E1) land in >24h bucket (> 1440 mins)."""
    anomalies = convert_findings_to_anomalies(sample_findings)
    f2 = next(a for a in anomalies if "HAC-F2" in a.id)
    e1 = next(a for a in anomalies if "HAC-E1" in a.id)
    mins_f2 = _parse_frontend_minutes(f2.time_to_impact)
    mins_e1 = _parse_frontend_minutes(e1.time_to_impact)
    assert mins_f2 > 1440, f"F2 time '{f2.time_to_impact}' parsed as {mins_f2} mins, expected > 1440"
    assert mins_e1 > 1440, f"E1 time '{e1.time_to_impact}' parsed as {mins_e1} mins, expected > 1440"


# ===========================================================================
# Suite 4: Generalization & Seed Variation (CAS-GEN-01 to CAS-GEN-03)
# ===========================================================================

def test_cas_gen01_dynamic_material_id_swap(sample_findings):
    """CAS-GEN-01: Changing material ID preserves valid DAG and simulation."""
    sample_findings["X1"][0]["material"] = "MAT-CUSTOM-9999"
    anomalies = convert_findings_to_anomalies(sample_findings)
    custom_x1 = next(a for a in anomalies if "MAT-CUSTOM-9999" in a.sku)
    engine = CascadeEngine(seed=42)
    graph = engine.build(custom_x1)
    assert nx.is_directed_acyclic_graph(graph)
    sim = engine.simulate(custom_x1)
    assert sim.propagation_probability > 0


def test_cas_gen02_extreme_quantity_scaling(sample_findings):
    """CAS-GEN-02: Shortfall scaling from 1 to 100,000 units scales financial exposure monotonically."""
    sample_findings["X2"][0]["shortfall"] = 1.0
    anom_small = convert_findings_to_anomalies(sample_findings)
    x2_small = next(a for a in anom_small if "HAC-X2" in a.id)

    sample_findings["X2"][0]["shortfall"] = 10000.0
    anom_large = convert_findings_to_anomalies(sample_findings)
    x2_large = next(a for a in anom_large if "HAC-X2" in a.id)

    assert x2_large.impact > x2_small.impact
    assert isinstance(x2_large.impact, int)


def test_cas_gen03_missing_optional_fields_resilience():
    """CAS-GEN-03: None batch or None dates do not crash cascade generation."""
    minimal_findings = {
        "B2": [{"catalog_id": "B2", "material": "MAT-X", "batch": None, "batch_expiry": None, "qty_on_hand": 10.0}],
        "D3": [{"catalog_id": "D3", "delivery": "DLV-X", "planned_gi_date": None, "overdue_days": 5}],
    }
    anomalies = convert_findings_to_anomalies(minimal_findings)
    assert len(anomalies) == 2
    engine = CascadeEngine(seed=42)
    for a in anomalies:
        assert nx.is_directed_acyclic_graph(engine.build(a))
