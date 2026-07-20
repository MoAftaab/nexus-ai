"""Synthetic operational data and derived findings for a no-dataset demo.

The data generator creates normal master, inventory, dispatch, supplier, document and
container records first. It then introduces realistic source-system drift. Findings are
derived by scanning those records; no anomaly payload is pre-authored for the UI.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import random
from typing import Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import Anomaly, CascadeEdge, CascadeNode, Evidence, FixAction


def _models():
    """Delay Pydantic imports so dataset export is runnable as a pure-stdlib operation."""
    from app.models import Anomaly, CascadeEdge, CascadeNode, Evidence, FixAction
    return Anomaly, CascadeEdge, CascadeNode, Evidence, FixAction


PART_FAMILIES = {
    "Powertrain": ("Torque converter", "Gear selector", "Fuel rail", "Clutch actuator"),
    "Electronics": ("ECU control module", "Camera harness", "Power distribution unit", "Radar sensor"),
    "Interior": ("Wiring harness assembly", "Door trim panel", "Seat rail", "Console module"),
    "Chassis": ("Brake line manifold", "Steering knuckle", "Wheel carrier", "Control arm"),
    "Fluids": ("Coolant additive", "Brake fluid reservoir", "Washer concentrate", "Sealant cartridge"),
}
SUPPLIERS = ("Nordwerk Components", "RheinMotion Systems", "Autotec Werke", "Vektor Mobility", "Helios Parts")
WAREHOUSES = ("WH-01", "WH-02")
ZONES = ("A-12", "B-07", "JIS-07", "Q-04", "HZ-02")
TARGET_COUNTS = {"master_skus": 5_000, "inventory_positions": 15_000, "inbound_orders": 2_000, "outbound_orders": 10_000, "dispatch_schedule": 500, "workforce_logs": 20_000, "documents": 200, "containers": 20_000}


@dataclass
class SyntheticDataset:
    seed: int
    generated_at: datetime
    skus: list[dict[str, Any]]
    inventory: list[dict[str, Any]]
    inbound_orders: list[dict[str, Any]]
    outbound_orders: list[dict[str, Any]]
    suppliers: list[dict[str, Any]]
    dispatches: list[dict[str, Any]]
    workforce: list[dict[str, Any]]
    documents: list[dict[str, Any]]
    containers: list[dict[str, Any]]


def _id(prefix: str, rng: random.Random) -> str:
    # Six digits: ~900k ID space so deterministic per-entity IDs cannot collide
    # within a session (4 digits gave ~0.7% birthday odds per fresh board).
    return f"{prefix}-{rng.randint(100000, 999999)}"


def _node(node_id: str, label: str, kind: str, health: str, detail: str, impact: int = 0, eta: str = "Monitored") -> CascadeNode:
    _, CascadeEdge, CascadeNode, _, _ = _models()
    return CascadeNode(id=node_id, label=label, kind=kind, health=health, detail=detail, impact=impact, time_to_impact=eta)


def _edge(source: str, target: str, label: str, probability: int) -> CascadeEdge:
    _, CascadeEdge, _, _, _ = _models()
    return CascadeEdge(source=source, target=target, label=label, probability=probability)


def generate_dataset(seed: int | None = None) -> SyntheticDataset:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0)
    effective_seed = seed if seed is not None else int(generated_at.timestamp() * 1000) % 2_147_483_647
    rng = random.Random(effective_seed)
    supplier_names = [*SUPPLIERS, *(f"{rng.choice(('Alpine', 'Hansa', 'Kern', 'Motive', 'Prisma'))} {rng.choice(('Automotive', 'Mobility', 'Systems', 'Components'))} {index:03}" for index in range(6, 201))]
    # Observed lead time tracks the configured master (drift < 3 days) so only the
    # injected stale-lead supplier below trips the reliability detector.
    suppliers = [{"id": f"SUP-{index + 1:03}", "name": name, "configured_lead": (configured_lead := rng.randint(3, 7)), "actual_lead": round(configured_lead + rng.uniform(-.8, 1.6), 1), "reliability": round(rng.uniform(.84, .98), 2)} for index, name in enumerate(supplier_names)]
    skus: list[dict[str, Any]] = []
    for index in range(TARGET_COUNTS["master_skus"]):
        family = rng.choice(tuple(PART_FAMILIES))
        name = rng.choice(PART_FAMILIES[family])
        # Hazmat storage and handling flag stay consistent at generation time; the
        # single conflicting record is injected below for the compliance detector.
        is_hazmat = family == "Fluids" and rng.random() < .35
        sku = {
            "id": f"{family[:2].upper()}-{rng.randint(1000, 9999)}-{index:03}",
            "description": f"{name} {rng.choice(('LH', 'RH', 'Gen 2', 'Premium'))}",
            "family": family,
            "weight_kg": round(rng.uniform(.4, 24.5), 2),
            "wms_weight_kg": None,
            "erp_weight_kg": None,
            "fitment_wms": rng.choice(("LH", "RH")),
            "fitment_erp": None,
            "storage_class": "hazmat" if is_hazmat else "ambient",
            "hazmat": is_hazmat,
            "supplier": rng.choice(suppliers)["id"],
            "bin": f"{rng.choice(ZONES)}-{rng.randint(1, 18):02}",
            "bin_active": True,
            "reorder_point": rng.randint(60, 220),
            "safety_stock": rng.randint(25, 90),
        }
        sku["erp_weight_kg"] = sku["weight_kg"]
        sku["wms_weight_kg"] = sku["weight_kg"]
        sku["fitment_erp"] = sku["fitment_wms"]
        skus.append(sku)
    inventory = []
    for index in range(TARGET_COUNTS["inventory_positions"]):
        sku = skus[index % len(skus)]
        actual = rng.randint(30, 760)
        inventory.append({"id": f"INV-{index + 1:05}", "sku": sku["id"], "warehouse": rng.choice(WAREHOUSES), "zone": sku["bin"].rsplit("-", 1)[0], "bin": f"{sku['bin']}-{index % 3 + 1}", "wms": actual, "erp": actual, "tms": actual, "physical": actual, "allocated": rng.randint(0, min(80, actual // 4)), "last_count": generated_at - timedelta(minutes=rng.randint(8, 900))})
    inbound_orders = []
    for index in range(TARGET_COUNTS["inbound_orders"]):
        supplier, sku = rng.choice(suppliers), rng.choice(skus)
        inbound_orders.append({"id": f"PO-{index + 1:06}", "supplier": supplier["id"], "sku": sku["id"], "expected_qty": rng.randint(50, 1000), "received_qty": rng.randint(35, 1000), "expected_date": (generated_at + timedelta(days=rng.randint(-16, 18))).date().isoformat(), "warehouse": rng.choice(WAREHOUSES), "quality_status": rng.choice(("accepted", "accepted", "pending", "partial"))})
    outbound_orders = []
    for index in range(TARGET_COUNTS["outbound_orders"]):
        sku = rng.choice(skus); ordered = rng.randint(4, 150)
        outbound_orders.append({"id": f"ORD-{index + 1:06}", "customer": f"Plant-{rng.randint(1, 48):02}", "sku": sku["id"], "ordered_qty": ordered, "picked_qty": rng.randint(0, ordered), "shipped_qty": 0, "promised_at": (generated_at + timedelta(hours=rng.randint(-12, 156))).isoformat(), "warehouse": rng.choice(WAREHOUSES), "pick_status": rng.choice(("pending", "in_progress", "completed")), "priority": rng.randint(1, 10)})
    dispatches = [{"id": f"DSP-{index + 1:05}", "dock": rng.choice(("Dock 3", "Dock 5", "Dock 7", "Dock 9", "Dock 11")), "departure": generated_at + timedelta(minutes=rng.randint(80, 1_680)), "label_success": 12, "total_labels": 12, "staged_units": rng.randint(70, 220), "vehicle_capacity_kg": rng.randint(7_000, 18_000), "total_load_kg": 0, "carrier": f"Carrier-{rng.randint(1, 22):02}"} for index in range(TARGET_COUNTS["dispatch_schedule"])]
    for dispatch in dispatches:
        dispatch["total_load_kg"] = int(dispatch["vehicle_capacity_kg"] * rng.uniform(.45, .88))
    task_types = ("picking", "replenishment", "packing", "quality")
    workforce = []
    for index in range(TARGET_COUNTS["workforce_logs"]):
        task = rng.choice(task_types)
        baseline_rate = {"picking": 94, "replenishment": 68, "packing": 77, "quality": 53}[task]
        workforce.append({"id": f"WKR-{index + 1:05}", "worker": f"Operator {rng.randint(1, 850):03}", "zone": rng.choice(ZONES), "shift": rng.choice(("A", "B", "C")), "task_type": task, "pick_rate": max(18, int(rng.gauss(baseline_rate, 10))), "exceptions": rng.randint(0, 4), "overtime_hours": round(max(0, rng.gauss(.55, .45)), 1), "recorded_at": (generated_at - timedelta(days=rng.randint(0, 59), minutes=rng.randint(0, 1_439))).isoformat()})
    documents = [{"id": f"DOC-{index + 1:05}", "sku": rng.choice(skus)["id"], "batch": f"B-{rng.randint(100, 999)}", "ppap_attached": True, "vda_attached": True, "type": rng.choice(("PPAP", "ASN", "VDA", "Invoice", "Cycle count"))} for index in range(TARGET_COUNTS["documents"])]
    containers = [{"id": f"KLT-{index + 1:06}", "supplier": rng.choice(suppliers)["id"], "location": rng.choice(("Supplier", "Carrier", "WH-01", "WH-02")), "overdue_hours": 0} for index in range(TARGET_COUNTS["containers"])]

    # Inject source-record defects after normal data generation. Detectors below discover them.
    harness = next(sku for sku in skus if sku["family"] == "Interior")
    harness["fitment_wms"] = "LH"; harness["fitment_erp"] = "RH"
    harness["description"] = "Wiring harness assembly JIS"
    fitment_dispatch = next(item for item in dispatches if item["dock"] == "Dock 7")
    fitment_dispatch["staged_units"] = rng.randint(118, 180)

    inventory_fault = rng.choice(inventory)
    inventory_fault["wms"] += rng.randint(20, 55); inventory_fault["erp"] += rng.randint(6, 18); inventory_fault["tms"] -= rng.randint(3, 11); inventory_fault["physical"] -= rng.randint(5, 16)
    weight_fault = rng.choice(skus); weight_fault["wms_weight_kg"] = round(weight_fault["weight_kg"] * rng.uniform(7.8, 10.4), 2); weight_fault["tms_weight_kg"] = weight_fault["weight_kg"]
    docs_fault = rng.choice(documents); docs_fault["ppap_attached"] = False
    lead_supplier = rng.choice(suppliers); lead_supplier["actual_lead"] = round(lead_supplier["configured_lead"] + rng.uniform(3.6, 5.4), 1)
    dispatch_fault = next(item for item in dispatches if item["dock"] == "Dock 7"); dispatch_fault["label_success"] = rng.randint(6, 9)
    capacity_fault = rng.choice(dispatches); capacity_fault["total_load_kg"] = int(capacity_fault["vehicle_capacity_kg"] * rng.uniform(1.18, 1.42))
    for order in rng.sample(outbound_orders, k=18):
        order["promised_at"] = (generated_at + timedelta(hours=rng.randint(1, 10))).isoformat(); order["picked_qty"] = 0; order["pick_status"] = "pending"; order["priority"] = 1
    workforce_fault_zone, workforce_fault_task = rng.choice(ZONES), rng.choice(task_types)
    recent_fault_records = [record for record in workforce if record["zone"] == workforce_fault_zone and record["task_type"] == workforce_fault_task and datetime.fromisoformat(record["recorded_at"]) >= generated_at - timedelta(days=7)]
    for record in recent_fault_records[:min(45, len(recent_fault_records))]:
        record["pick_rate"] = rng.randint(18, 34); record["exceptions"] = rng.randint(6, 12); record["overtime_hours"] = round(rng.uniform(4.5, 7.5), 1)
    chemical = next(sku for sku in skus if sku["family"] == "Fluids"); chemical["storage_class"] = "hazmat"; chemical["hazmat"] = False
    overdue = rng.sample(containers, k=rng.randint(26, 46));
    for container in overdue: container["overdue_hours"] = rng.randint(25, 66)
    retired = rng.choice(skus); retired["bin_active"] = False

    # Replenishment gap: consumption drained one part below its reorder point and
    # no inbound PO exists. Balances stay equal so only the coverage check fires.
    incoming_skus = {order["sku"] for order in inbound_orders if order["expected_date"] >= generated_at.date().isoformat()}
    replenish_fault = next(sku for sku in skus if sku["id"] not in incoming_skus and sku["id"] not in (inventory_fault["sku"], retired["id"]))
    drained_level = max(4, replenish_fault["reorder_point"] // 8)
    for row in inventory:
        if row["sku"] == replenish_fault["id"]:
            row["wms"] = row["erp"] = row["tms"] = row["physical"] = drained_level

    return SyntheticDataset(effective_seed, generated_at, skus, inventory, inbound_orders, outbound_orders, suppliers, dispatches, workforce, documents, containers)


def _make_action(anomaly_id: str, title: str, owner: str, eta: str, confidence: int, description: str, saved: int) -> FixAction:
    _, _, _, _, FixAction = _models()
    return FixAction(id=f"FX-{anomaly_id.split('-')[-1]}-{owner[:2].upper()}", title=title, owner=owner, eta=eta, confidence=confidence, description=description, impact_saved=saved)


def detect_anomalies(data: SyntheticDataset, inventory_scores: dict[str, float] | None = None) -> list[Anomaly]:
    """Specialist detectors inspect generated source records and output explainable findings."""
    Anomaly, _, _, Evidence, _ = _models()
    now = data.generated_at
    findings: list[Anomaly] = []

    for sku in data.skus:
        if sku["fitment_wms"] != sku["fitment_erp"]:
            anomaly_id = _id("AN", random.Random(f"{data.seed}:{sku['id']}:fitment"))
            dispatch = min(data.dispatches, key=lambda item: item["departure"])
            eta_minutes = max(30, int((dispatch["departure"] - now).total_seconds() / 60))
            impact = dispatch["staged_units"] * 4200 + 420000
            source, sequence, dock, station = [f"{anomaly_id}-{key}" for key in ("source", "sequence", "dock", "station")]
            findings.append(Anomaly(id=anomaly_id, title=f"{sku['description']} maps to conflicting JIS fitment", type="Master data conflict", severity="critical", system="ERP · WMS", zone="JIS staging", sku=sku["id"], detected_at=now - timedelta(minutes=18), time_to_impact=f"{eta_minutes // 60}h {eta_minutes % 60}m", impact=impact, confidence=96, summary=f"WMS routes {sku['fitment_wms']} while ERP routes {sku['fitment_erp']}; {dispatch['staged_units']} units are staged for the next JIS departure.", root_cause="The engineering fitment revision diverged between master-data publishing jobs.", evidence=[Evidence(label="ERP fitment", value=sku["fitment_erp"], source="ERP master"), Evidence(label="WMS fitment", value=sku["fitment_wms"], source="WMS master"), Evidence(label="Staged units", value=str(dispatch["staged_units"]), source=dispatch["id"])], actions=[_make_action(anomaly_id, "Freeze JIS release and align WMS fitment", "Master Data", "18 min", 98, "Publish the approved ERP fitment to WMS, validate the route, then regenerate the sequence.", int(impact * .95)), _make_action(anomaly_id, "Move verified harnesses to a safe lane", "Dock 7", "12 min", 89, "Keep confirmed variants out of automated sequencing while the master correction propagates.", int(impact * .79))], cascade_nodes=[_node(source, "Fitment data conflict", "source", "critical", f"ERP {sku['fitment_erp']} conflicts with WMS {sku['fitment_wms']}."), _node(sequence, "JIS sequence builder", "process", "risk", f"{dispatch['staged_units']} staged units inherit the wrong variant."), _node(dock, dispatch["dock"], "process", "risk", f"The controlled departure is due in {eta_minutes // 60}h {eta_minutes % 60}m."), _node(station, "Assembly line feed", "outcome", "critical", "Mixed variants require manual intervention at line side.", impact, f"{eta_minutes // 60}h {eta_minutes % 60}m")], cascade_edges=[_edge(source, sequence, "maps part variant", 93), _edge(sequence, dock, "loads JIS racks", 88), _edge(dock, station, "feeds production", 76)]))

    for sku in data.skus:
        expected_weight = max(float(sku.get("erp_weight_kg") or 0), float(sku.get("tms_weight_kg") or 0))
        wms_weight = float(sku.get("wms_weight_kg") or 0)
        variance_ratio = abs(wms_weight - expected_weight) / expected_weight if expected_weight else 0
        if variance_ratio >= .1:
            anomaly_id = _id("AN", random.Random(f"{data.seed}:{sku['id']}:weight")); impact = int(48_000 + variance_ratio * 85_000)
            source, load, outcome = [f"{anomaly_id}-{key}" for key in ("source", "load", "outcome")]
            findings.append(Anomaly(id=anomaly_id, title=f"Declared weight conflicts across systems for {sku['id']}", type="Master data conflict", severity="high", system="WMS · ERP · TMS", zone=sku["bin"].rsplit("-", 1)[0], sku=sku["id"], detected_at=now - timedelta(minutes=27), time_to_impact="9h", impact=impact, confidence=94, summary=f"WMS records {wms_weight:.2f} kg while ERP/TMS record {expected_weight:.2f} kg for the same unit.", root_cause="A master-data publishing or unit-conversion update was accepted by one source system only.", evidence=[Evidence(label="WMS weight", value=f"{wms_weight:.2f} kg", source="WMS master"), Evidence(label="ERP/TMS weight", value=f"{expected_weight:.2f} kg", source="ERP/TMS master"), Evidence(label="Variance", value=f"{variance_ratio * 100:.0f}%", source="Cross-system validator")], actions=[_make_action(anomaly_id, "Quarantine affected shipment weights and republish master", "Master Data", "20 min", 96, "Validate the approved unit weight, republish it to WMS and TMS, then recalculate open loads.", int(impact * .86))], cascade_nodes=[_node(source, "Weight master conflict", "source", "critical", "A unit weight differs materially across source systems."), _node(load, "Carrier load planning", "process", "risk", "Planning can understate vehicle load and freight cost."), _node(outcome, "Dispatch compliance", "outcome", "risk", "An affected load can fail carrier or safety checks.", impact, "9h")], cascade_edges=[_edge(source, load, "misstates shipment mass", 87), _edge(load, outcome, "creates non-compliant load", 66)]))

    for row in data.inventory:
        divergence = max(row["wms"], row["erp"], row["physical"]) - min(row["wms"], row["erp"], row["physical"])
        model_score = (inventory_scores or {}).get(row.get("id", row["sku"]), 1.0)
        if divergence >= 25 and model_score >= .5:
            anomaly_id = _id("AN", random.Random(f"{data.seed}:{row['id']}:inventory")); impact = divergence * 4400
            source, plan, line = [f"{anomaly_id}-{key}" for key in ("source", "plan", "line")]
            findings.append(Anomaly(id=anomaly_id, title=f"Inventory truth diverges for {row['sku']}", type="Inventory reconciliation", severity="critical", system="WMS · ERP · Count", zone=row["zone"], sku=row["sku"], detected_at=now - timedelta(minutes=43), time_to_impact="1d 6h", impact=impact, confidence=max(82, int(model_score * 100)), summary=f"WMS has {row['wms']}, ERP has {row['erp']}, and physical count has {row['physical']} units.", root_cause="Receipt and pick movement journals no longer reconcile across operational systems.", evidence=[Evidence(label="WMS available", value=f"{row['wms']} EA", source="WMS"), Evidence(label="ERP available", value=f"{row['erp']} EA", source="ERP"), Evidence(label="Physical count", value=f"{row['physical']} EA", source="Cycle count"), Evidence(label="ML anomaly score", value=f"{model_score * 100:.1f}%", source="Selected detector")], actions=[_make_action(anomaly_id, "Rebuild the failed inventory journal", "Inventory Control", "24 min", 95, "Reconcile scanner movements against the source ledger and post the missing journal entries.", int(impact * .8))], cascade_nodes=[_node(source, "Inventory divergence", "source", "critical", "The system balances disagree with physical truth."), _node(plan, "Replenishment trigger", "process", "risk", "Availability logic will inherit an incorrect balance."), _node(line, "Production line feed", "outcome", "risk", "A replenishment gap is forecast before the next receipt.", impact, "1d 6h")], cascade_edges=[_edge(source, plan, "skews availability", 91), _edge(plan, line, "misses replenishment", 68)]))

    for document in data.documents:
        if not document["ppap_attached"]:
            anomaly_id = _id("AN", random.Random(f"{data.seed}:{document['id']}:ppap")); impact = random.Random(data.seed).randint(105000, 158000)
            source, quality, station = [f"{anomaly_id}-{key}" for key in ("source", "quality", "station")]
            findings.append(Anomaly(id=anomaly_id, title=f"PPAP approval is missing for batch {document['batch']}", type="Document intelligence", severity="high", system="QMS · WMS", zone="Quarantine", sku=document["sku"], detected_at=now - timedelta(hours=1, minutes=8), time_to_impact="18h", impact=impact, confidence=91, summary="The batch is scheduled for release but its supplier packet does not include the required PPAP approval.", root_cause="The inbound document bundle was accepted without the release-critical approval attachment.", evidence=[Evidence(label="Batch", value=document["batch"], source="Inbound ASN"), Evidence(label="PPAP status", value="Not attached", source="Document agent"), Evidence(label="Release gate", value="Blocked", source="QMS")], actions=[_make_action(anomaly_id, "Request signed PPAP and pre-review it", "Supplier Quality", "45 min", 87, "Send the missing-evidence request and reserve a reviewer slot before the shift handover.", int(impact * .8))], cascade_nodes=[_node(source, "PPAP evidence missing", "source", "critical", "No signed PPAP is attached to the supplier packet."), _node(quality, "Quality release", "process", "risk", "The batch remains in quarantine."), _node(station, "Assembly station supply", "outcome", "risk", "The next shift consumes this batch.", impact, "18h")], cascade_edges=[_edge(source, quality, "blocks release", 100), _edge(quality, station, "withholds supply", 72)]))

    for supplier in data.suppliers:
        if supplier["actual_lead"] - supplier["configured_lead"] >= 3:
            anomaly_id = _id("AN", random.Random(f"{data.seed}:{supplier['id']}:lead")); drift = supplier["actual_lead"] - supplier["configured_lead"]; impact = int(drift * 23600)
            findings.append(Anomaly(id=anomaly_id, title=f"{supplier['name']} lead time is stale by {drift:.1f} days", type="Supplier reliability", severity="high", system="ERP · Supplier", zone="Inbound", sku=next((sku["id"] for sku in data.skus if sku["supplier"] == supplier["id"]), supplier["id"]), detected_at=now - timedelta(hours=2), time_to_impact="3d 8h", impact=impact, confidence=88, summary=f"Planning assumes {supplier['configured_lead']} days; the latest receipts average {supplier['actual_lead']} days.", root_cause="Supplier lead-time master was not revised after transport-lane performance changed.", evidence=[Evidence(label="Configured lead time", value=f"{supplier['configured_lead']} days", source="ERP"), Evidence(label="Actual average", value=f"{supplier['actual_lead']} days", source="Receipts"), Evidence(label="Reliability", value=f"{supplier['reliability'] * 100:.0f}%", source="Supplier score")], actions=[_make_action(anomaly_id, "Update lead time and release an expedite", "Supply Planning", "32 min", 90, "Refresh the plan with observed lead time and create a temporary safeguard PO.", int(impact * .83))], cascade_nodes=[], cascade_edges=[]))

    for dispatch in data.dispatches:
        if dispatch["label_success"] < dispatch["total_labels"]:
            anomaly_id = _id("AN", random.Random(f"{data.seed}:{dispatch['id']}:labels")); failed = dispatch["total_labels"] - dispatch["label_success"]; impact = failed * 25400
            findings.append(Anomaly(id=anomaly_id, title=f"{dispatch['dock']} has {failed} unverified VDA labels", type="Dispatch readiness", severity="high", system="TMS · Print service", zone=dispatch["dock"], sku="Mixed JIT load", detected_at=now - timedelta(hours=2, minutes=21), time_to_impact="2h 40m", impact=impact, confidence=85, summary=f"{dispatch['label_success']} of {dispatch['total_labels']} labels passed verification before the JIT cutoff.", root_cause="The dispatch print service has intermittent verification failures.", evidence=[Evidence(label="Verified labels", value=f"{dispatch['label_success']} / {dispatch['total_labels']}", source="Print service"), Evidence(label="Departure", value=dispatch["departure"].strftime("%H:%M UTC"), source="TMS"), Evidence(label="Fallback dock", value="Dock 3 available", source="Dock planner")], actions=[_make_action(anomaly_id, "Redirect the active load to Dock 3", "Dispatch", "8 min", 93, "Use the verified fallback printer and notify the material handler.", int(impact * .81))], cascade_nodes=[], cascade_edges=[]))

    for dispatch in data.dispatches:
        overload = dispatch["total_load_kg"] / max(1, dispatch["vehicle_capacity_kg"])
        if overload > 1:
            anomaly_id = _id("AN", random.Random(f"{data.seed}:{dispatch['id']}:overload")); impact = int((overload - 1) * 310_000)
            findings.append(Anomaly(id=anomaly_id, title=f"{dispatch['id']} exceeds vehicle capacity by {(overload - 1) * 100:.0f}%", type="Dispatch readiness", severity="high", system="TMS · Load planner", zone=dispatch["dock"], sku="Mixed outbound load", detected_at=now - timedelta(minutes=36), time_to_impact="4h", impact=impact, confidence=93, summary=f"The planned load is {dispatch['total_load_kg']:,} kg against {dispatch['vehicle_capacity_kg']:,} kg approved capacity.", root_cause="Load planning accepted an aggregate pallet weight without applying the carrier capacity constraint.", evidence=[Evidence(label="Planned load", value=f"{dispatch['total_load_kg']:,} kg", source="TMS"), Evidence(label="Approved capacity", value=f"{dispatch['vehicle_capacity_kg']:,} kg", source="Carrier profile"), Evidence(label="Overload", value=f"{(overload - 1) * 100:.0f}%", source="Dispatch agent")], actions=[_make_action(anomaly_id, "Split the load before carrier check-in", "Dispatch", "18 min", 94, "Move excess pallets to the next approved departure and regenerate the carrier manifest.", int(impact * .82))], cascade_nodes=[], cascade_edges=[]))

    workforce_groups: dict[tuple[str, str], dict[str, list[dict[str, Any]]]] = {}
    seven_day_cutoff = now - timedelta(days=7)
    for record in data.workforce:
        recorded_at = datetime.fromisoformat(record["recorded_at"]) if isinstance(record["recorded_at"], str) else record["recorded_at"]
        group = workforce_groups.setdefault((record["zone"], record["task_type"]), {"recent": [], "historical": []})
        group["recent" if recorded_at >= seven_day_cutoff else "historical"].append(record)
    productivity_candidates = []
    for (zone, task), sample in workforce_groups.items():
        if len(sample["recent"]) < 12 or len(sample["historical"]) < 40:
            continue
        recent_rate = sum(item["pick_rate"] for item in sample["recent"]) / len(sample["recent"])
        historical_rate = sum(item["pick_rate"] for item in sample["historical"]) / len(sample["historical"])
        recent_overtime = sum(item["overtime_hours"] for item in sample["recent"]) / len(sample["recent"])
        historical_overtime = sum(item["overtime_hours"] for item in sample["historical"]) / len(sample["historical"])
        if recent_rate < historical_rate * .7 and recent_overtime > max(2.0, historical_overtime * 2.5):
            productivity_candidates.append((recent_rate / historical_rate, zone, task, recent_rate, historical_rate, recent_overtime, historical_overtime))
    if productivity_candidates:
        _, zone, task, recent_rate, historical_rate, recent_overtime, historical_overtime = min(productivity_candidates)
        anomaly_id = _id("AN", random.Random(f"{data.seed}:{zone}:{task}:workforce")); impact = int((historical_rate - recent_rate) * 1_850)
        findings.append(Anomaly(id=anomaly_id, title=f"{zone} {task} productivity dropped below its operating baseline", type="Workforce performance", severity="high", system="Workforce · WMS", zone=zone, sku="Zone workload", detected_at=now - timedelta(minutes=52), time_to_impact="1 shift", impact=impact, confidence=89, summary=f"The recent rate is {recent_rate:.0f} units/hour versus a {historical_rate:.0f} units/hour historical baseline while overtime averages {recent_overtime:.1f}h.", root_cause="The zone has a sustained productivity decline paired with exceptional overtime, indicating a workflow or staffing constraint.", evidence=[Evidence(label="Recent rate", value=f"{recent_rate:.0f} units/h", source="Workforce log"), Evidence(label="Historical baseline", value=f"{historical_rate:.0f} units/h", source="60-day baseline"), Evidence(label="Recent overtime", value=f"{recent_overtime:.1f}h", source="Shift record")], actions=[_make_action(anomaly_id, "Rebalance the affected zone and inspect work instructions", "Shift Manager", "25 min", 85, "Move a trained operator to the constrained task and verify the active scan and pick instructions.", int(impact * .78))], cascade_nodes=[], cascade_edges=[]))

    upcoming_orders = []
    for order in data.outbound_orders:
        promised_at = datetime.fromisoformat(order["promised_at"]) if isinstance(order["promised_at"], str) else order["promised_at"]
        if now <= promised_at <= now + timedelta(hours=12) and order["picked_qty"] < order["ordered_qty"] and order["priority"] <= 2:
            upcoming_orders.append((promised_at, order))
    if upcoming_orders:
        promised_at, order = min(upcoming_orders, key=lambda item: (item[0], item[1]["priority"], -item[1]["ordered_qty"]))
        minutes = max(15, int((promised_at - now).total_seconds() / 60)); shortfall = order["ordered_qty"] - order["picked_qty"]; impact = shortfall * 1_950
        anomaly_id = _id("AN", random.Random(f"{data.seed}:{order['id']}:sla")); source, pick, outcome = [f"{anomaly_id}-{key}" for key in ("source", "pick", "outcome")]
        findings.append(Anomaly(id=anomaly_id, title=f"Priority order {order['id']} is at risk of missing its plant SLA", type="SLA escalation", severity="critical" if minutes < 240 else "high", system="OMS · WMS", zone=order["warehouse"], sku=order["sku"], detected_at=now - timedelta(minutes=14), time_to_impact=f"{minutes // 60}h {minutes % 60}m", impact=impact, confidence=92, summary=f"{shortfall} of {order['ordered_qty']} units remain unpicked for {order['customer']} before its committed departure.", root_cause="Priority demand entered the release window without a completed pick or a protected inventory allocation.", evidence=[Evidence(label="Promised departure", value=promised_at.strftime("%H:%M UTC"), source="OMS"), Evidence(label="Open quantity", value=f"{shortfall} EA", source="WMS"), Evidence(label="Priority", value=str(order["priority"]), source="Order master")], actions=[_make_action(anomaly_id, "Expedite the priority pick and reserve a dock slot", "Outbound Control", "12 min", 91, "Release a priority task, assign a verified picker and hold the appropriate outbound dock capacity.", int(impact * .81))], cascade_nodes=[_node(source, "Unpicked priority order", "source", "critical", "A priority plant order remains short inside its commitment window."), _node(pick, "Priority pick release", "process", "risk", "The fulfillment queue has not protected the required quantity."), _node(outcome, "Plant delivery SLA", "outcome", "critical", "The plant can receive a short or late JIT shipment.", impact, f"{minutes // 60}h {minutes % 60}m")], cascade_edges=[_edge(source, pick, "misses release window", 89), _edge(pick, outcome, "causes late JIT delivery", 74)]))

    for sku in data.skus:
        if sku["storage_class"] == "hazmat" and not sku["hazmat"]:
            anomaly_id = _id("AN", random.Random(f"{data.seed}:{sku['id']}:hazmat")); impact = random.Random(data.seed + 14).randint(32000, 52000)
            findings.append(Anomaly(id=anomaly_id, title=f"Hazmat handling flag conflicts for {sku['id']}", type="Compliance", severity="medium", system="ERP · WMS", zone="HZ-02", sku=sku["id"], detected_at=now - timedelta(hours=3), time_to_impact="2d", impact=impact, confidence=97, summary="Hazmat storage is set but outbound handling is disabled in the master record.", root_cause="A catalog import applied a default handling value over the safety master.", evidence=[Evidence(label="Storage class", value="Hazmat", source="WMS"), Evidence(label="Outbound flag", value="False", source="ERP"), Evidence(label="Safety control", value="Required", source="Compliance master")], actions=[_make_action(anomaly_id, "Restore hazmat handling control", "Compliance", "10 min", 99, "Apply the safety-master flag and rescreen all open loads.", int(impact * .92))], cascade_nodes=[], cascade_edges=[]))

    # Replenishment coverage: total on-hand at/below reorder point with no open
    # inbound PO means planning has silently lost its safety margin.
    stock_by_sku: dict[str, int] = {}
    for row in data.inventory:
        stock_by_sku[row["sku"]] = stock_by_sku.get(row["sku"], 0) + row["wms"]
    covered_skus = {order["sku"] for order in data.inbound_orders if order["expected_date"] >= now.date().isoformat()}
    replenish_candidates = []
    for sku in data.skus:
        total = stock_by_sku.get(sku["id"])
        if total is None or sku["id"] in covered_skus:
            continue
        if total <= sku["reorder_point"]:
            replenish_candidates.append((total / max(1, sku["reorder_point"]), total, sku))
    if replenish_candidates:
        ratio, total, sku = min(replenish_candidates)
        anomaly_id = _id("AN", random.Random(f"{data.seed}:{sku['id']}:replenish"))
        shortfall = sku["reorder_point"] - total; impact = shortfall * 2_150 + 38_000
        source, plan, line = [f"{anomaly_id}-{key}" for key in ("source", "plan", "line")]
        findings.append(Anomaly(id=anomaly_id, title=f"{sku['id']} is below reorder point with no inbound PO", type="Replenishment risk", severity="high" if ratio < .3 else "medium", system="ERP · Planning", zone=sku["bin"].rsplit("-", 1)[0], sku=sku["id"], detected_at=now - timedelta(minutes=33), time_to_impact="2d 4h", impact=impact, confidence=90, summary=f"On-hand is {total} EA against a reorder point of {sku['reorder_point']} EA ({sku['safety_stock']} EA safety stock), and no open purchase order covers this part.", root_cause="Consumption crossed the reorder trigger but no replenishment order was generated — the planning signal was lost between systems.", evidence=[Evidence(label="On-hand total", value=f"{total} EA", source="WMS"), Evidence(label="Reorder point", value=f"{sku['reorder_point']} EA", source="ERP planning master"), Evidence(label="Open inbound POs", value="None", source="Purchasing")], actions=[_make_action(anomaly_id, "Raise an expedited replenishment PO", "Supply Planning", "25 min", 92, "Create a covering PO at the supplier's expedite lane and flag the part for allocation protection until receipt.", int(impact * .84))], cascade_nodes=[_node(source, "Lost replenishment trigger", "source", "critical", f"Stock crossed the reorder point with no PO raised for {sku['id']}."), _node(plan, "Availability planning", "process", "risk", "Planning still assumes coverage that does not exist."), _node(line, "Production line supply", "outcome", "risk", "A stockout is forecast before any normal-lead-time receipt can arrive.", impact, "2d 4h")], cascade_edges=[_edge(source, plan, "masks the shortage", 90), _edge(plan, line, "starves the line feed", 71)]))

    overdue = [item for item in data.containers if item["overdue_hours"] > 24]
    if overdue:
        anomaly_id = _id("AN", random.Random(f"{data.seed}:{overdue[0]['id']}:containers")); impact = len(overdue) * 720
        findings.append(Anomaly(id=anomaly_id, title=f"{len(overdue)} KLT containers are overdue for return scan", type="Container tracking", severity="medium", system="KLT tracker", zone="Supplier lane", sku=overdue[0]["id"], detected_at=now - timedelta(hours=4), time_to_impact="5d", impact=impact, confidence=82, summary="Reusable containers have not sent a carrier return scan inside the expected window.", root_cause="The return-leg scan feed has not synchronized with the container ledger.", evidence=[Evidence(label="Missing scans", value=f"{len(overdue)} KLT", source="Container ledger"), Evidence(label="Oldest delay", value=f"{max(item['overdue_hours'] for item in overdue)}h", source="Carrier gateway"), Evidence(label="Pool reserve", value=f"{max(5, 28 - len(overdue) // 2)}%", source="Container planner")], actions=[_make_action(anomaly_id, "Reconcile carrier scans and reserve KLTs", "Packaging", "1h", 78, "Request the offline scan export and rebalance nearby empty-container stock.", int(impact * .75))], cascade_nodes=[], cascade_edges=[]))

    for sku in data.skus:
        if not sku["bin_active"]:
            anomaly_id = _id("AN", random.Random(f"{data.seed}:{sku['id']}:bin")); impact = random.Random(data.seed + 35).randint(6800, 11800)
            findings.append(Anomaly(id=anomaly_id, title=f"Pick path points to a retired bin for {sku['id']}", type="Warehouse execution", severity="low", system="WMS", zone=sku["bin"].rsplit("-", 1)[0], sku=sku["id"], detected_at=now - timedelta(hours=5), time_to_impact="4d", impact=impact, confidence=84, summary="The active pick rule targets a bin retired during the latest slotting update.", root_cause="The location publish job completed before the pick-rule rebuild.", evidence=[Evidence(label="Configured bin", value=sku["bin"], source="Pick rule"), Evidence(label="Bin status", value="Retired", source="Location master"), Evidence(label="Open picks", value=str(random.Random(data.seed + 27).randint(8, 24)), source="WMS")], actions=[_make_action(anomaly_id, "Publish current slotting rule", "Warehouse Systems", "15 min", 96, "Rebuild the pick path from the active location master.", int(impact * .8))], cascade_nodes=[], cascade_edges=[]))

    return sorted(findings, key=lambda item: item.impact, reverse=True)


def build_reconciliation_rows(data: SyntheticDataset) -> list[dict[str, object]]:
    rows = []
    sku_lookup = {sku["id"]: sku for sku in data.skus}
    for record in sorted(data.inventory, key=lambda item: max(item["wms"], item["erp"], item.get("tms", item["erp"]), item["physical"]) - min(item["wms"], item["erp"], item.get("tms", item["erp"]), item["physical"]), reverse=True)[:8]:
        variance = record["wms"] - record["physical"]
        spread = max(record["wms"], record["erp"], record.get("tms", record["erp"]), record["physical"]) - min(record["wms"], record["erp"], record.get("tms", record["erp"]), record["physical"])
        rows.append({"id": record["id"], "sku": record["sku"], "description": sku_lookup[record["sku"]]["description"], "warehouse": record["warehouse"], "bin": record["bin"], "wms": record["wms"], "erp": record["erp"], "tms": record.get("tms", record["erp"]), "physical": record["physical"], "variance": variance, "root": "Movement journals require reconciliation" if spread else "Balances agree across all sources", "risk": "critical" if spread >= 25 else "watch" if spread else "healthy"})
    return rows
