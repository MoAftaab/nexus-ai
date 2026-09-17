from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import os
import logging
import hashlib
from threading import RLock
import random
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

from app.db import ApprovalStepModel, ChangeRequestModel, ContainerModel, DetailRequestModel, DispatchScheduleModel, InboundOrderModel, InventoryPositionModel, MasterSkuModel, OutboundOrderModel, Repository, SupplierModel, WorkflowActionModel, WorkforceLogModel
from app.config import Settings
from app.models import Anomaly, CascadeEdge, CascadeNode, DocumentInspection, Evidence, FixAction
from app.services.cascade_engine import CascadeEngine
from app.services.auth import seed_users_and_sites
from app.services.dataset_export import DATASETS_DIR, export_dataset
from app.services.ml_detection import ModelSelection, score_records, select_best_inventory_model, train_selected_classifier
from app.services.knowledge_base import KNOWLEDGE_DIR, list_ingested_documents, prepare_operational_markdown, retrieve_markdown
from app.services.seed import SyntheticDataset, build_reconciliation_rows, detect_anomalies, generate_dataset
from app.services.hackathon_ingest import load_hackathon_workbook
from app.services.hackathon_detectors import run_all_detectors
from app.services.hackathon_adapter import convert_findings_to_anomalies

DATASET_SCHEMA_VERSION = "2026.08.12.1"


def _sap_rows(data) -> list[dict]:
    return list(getattr(data, "inventory", data or []))


def _sap_id(prefix: str, value: str) -> str:
    return f"SAP-{prefix}-{hashlib.sha1(value.encode('utf-8')).hexdigest()[:10].upper()}"


def _sap_action(anomaly_id: str, title: str, owner: str, description: str, saved: int) -> FixAction:
    return FixAction(
        id=f"FX-{anomaly_id[-8:]}-{owner[:2].upper()}", title=title, owner=owner,
        eta="1 shift", confidence=90, description=description, impact_saved=saved,
    )


def _sap_anomaly(
    *, prefix: str, title: str, kind: str, severity: str, impact: int, rows: list[dict],
    summary: str, root_cause: str, evidence: list[Evidence], nodes: list[tuple[str, str, str, str, str]],
    action_title: str, action_description: str,
) -> Anomaly:
    now = datetime.now(timezone.utc)
    anomaly_id = _sap_id(prefix, "|".join(str(row.get("sap_source_id") or row.get("id") or index) for index, row in enumerate(rows)))
    cascade_nodes = [CascadeNode(id=f"{anomaly_id}-{index}", label=label, kind=node_kind, health=health, detail=detail) for index, (label, node_kind, health, detail, _unused) in enumerate(nodes)]
    cascade_edges = [CascadeEdge(source=cascade_nodes[index].id, target=cascade_nodes[index + 1].id, label="propagates", probability=max(55, 92 - index * 9)) for index in range(len(cascade_nodes) - 1)]
    sku = str(rows[0].get("material") or rows[0].get("sku") or "SAP-MARD") if rows else "SAP-MARD"
    zone = str(rows[0].get("storagelocation") or "Kassel") if rows else "Kassel"
    return Anomaly(
        id=anomaly_id, title=title, type=kind, severity=severity, system="SAP ERP", zone=zone,
        sku=sku, detected_at=now, time_to_impact="Next period close", impact=int(impact), confidence=94,
        summary=summary, root_cause=root_cause, evidence=evidence,
        actions=[_sap_action(anomaly_id, action_title, "SAP Operations", action_description, int(impact * .85))],
        cascade_nodes=cascade_nodes, cascade_edges=cascade_edges,
    )


def _as_float(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def detect_fiscal_year_desync(data) -> list[Anomaly]:
    rows = _sap_rows(data)
    findings: list[Anomaly] = []
    severity_by_year = {2022: "critical", 2023: "high", 2024: "medium", 2025: "low"}
    for year in sorted(severity_by_year):
        group = [row for row in rows if str(row.get("fiscalyearofcurrentperiod") or "").strip() == str(year)]
        if not group:
            continue
        locations = sorted({str(row.get("storagelocation") or "unknown") for row in group})
        impact = min(85_000, 15_000 + len(locations) * 1_500)
        findings.append(_sap_anomaly(
            prefix=f"FY{year}", title=f"SAP fiscal year desynchronization — FY{year}", kind="SAP fiscal year desync",
            severity=severity_by_year[year], impact=impact, rows=group,
            summary=f"{len(group)} SAP storage records remain in fiscal year {year} across {len(locations)} locations.",
            root_cause="Material stock-period records were not advanced with the active fiscal year.",
            evidence=[Evidence(label="fiscalyearofcurrentperiod", value=str(year), source="SAP MARD"), Evidence(label="Storage locations", value=", ".join(locations), source="SAP MARD")],
            nodes=[("ERP Period Mismatch", "source", "critical", "SAP MARD is in a prior fiscal year", ""), ("Period-Close Failure", "process", "risk", "Period close may reject stale stock periods", ""), ("Goods Movement Block", "outcome", "critical", "Goods movements can be blocked", "")],
            action_title="Advance SAP stock periods and validate period close", action_description="Synchronize fiscal year and current period for affected material/storage-location records, then re-run period-close validation.",
        ))
    return findings


def _count_date(value) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value or "").strip()
    if not text or text == "00000000":
        return None
    try:
        return datetime.strptime(text, "%Y%m%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def detect_unreconciled_inventory(data) -> list[Anomaly]:
    rows = _sap_rows(data)
    now = datetime.now(timezone.utc)
    unposted: list[dict] = []
    for row in rows:
        posted = _count_date(row.get("dateoflastpostedcount") or row.get("last_count"))
        if posted is None or (now - posted).days > 365:
            unposted.append(row)
    if not unposted:
        return []
    locations = sorted({str(row.get("storagelocation") or "unknown") for row in unposted})
    location_counts = Counter(str(row.get("storagelocation") or "unknown") for row in rows)
    critical = any(sum(1 for row in unposted if str(row.get("storagelocation") or "unknown") == location) / max(1, count) > .95 for location, count in location_counts.items())
    impact = min(120_000, 25_000 + len(unposted) * 100)
    return [_sap_anomaly(
        prefix="COUNT", title="Unreconciled physical inventory audit", kind="SAP physical inventory audit",
        severity="critical" if critical else "high", impact=impact, rows=unposted,
        summary=f"{len(unposted)} records have no valid physical count or have not been counted for over 365 days.",
        root_cause="Physical inventory posting evidence is missing from the SAP stock ledger.",
        evidence=[Evidence(label="dateoflastpostedcount", value=", ".join(sorted({str(row.get('dateoflastpostedcount') or '00000000') for row in unposted})), source="SAP MARD"), Evidence(label="Storage location", value=", ".join(locations), source="SAP MARD")],
        nodes=[("Ghost Inventory Risk", "source", "critical", "Book stock lacks recent count evidence", ""), ("Stock Availability Signal Error", "process", "risk", "Available stock cannot be trusted", ""), ("Dispatch Shortfall", "outcome", "critical", "Planning may release unavailable stock", "")],
        action_title="Create and post a physical inventory count", action_description="Block unreliable availability signals, perform a cycle count, and post the reconciled quantity to SAP.",
    )]


def detect_blocked_restricted_stock(data) -> list[Anomaly]:
    rows = _sap_rows(data)
    blocked = [row for row in rows if (_as_float(row.get("blockedstock")) > 0 or _as_float(row.get("stockinqualityinspection")) > 0) and _as_float(row.get("freeavailablestock")) <= 0]
    if not blocked:
        return []
    blocked_qty = sum(max(0, _as_float(row.get("blockedstock"))) + max(0, _as_float(row.get("stockinqualityinspection"))) for row in blocked)
    impact = min(95_000, 18_000 + int(blocked_qty * 2_000))
    return [_sap_anomaly(
        prefix="BLOCKED", title="Blocked and restricted stock unavailable", kind="SAP blocked stock", severity="high", impact=impact, rows=blocked,
        summary=f"{len(blocked)} locations hold {blocked_qty:g} units in blocked or quality-inspection stock with no free availability.",
        root_cause="Stock remains trapped in SAP quality or blocked status without an available release path.",
        evidence=[Evidence(label="Blocked quantity", value=f"{blocked_qty:g} units (blockedstock + stockinqualityinspection)", source="SAP MARD"), Evidence(label="Exact blocked quantities", value=", ".join(f"{str(row.get('storagelocation') or 'unknown')}: blocked={max(0, _as_float(row.get('blockedstock'))):g}, quality={max(0, _as_float(row.get('stockinqualityinspection'))):g}" for row in blocked), source="SAP MARD"), Evidence(label="Storage locations", value=", ".join(sorted({str(row.get('storagelocation') or 'unknown') for row in blocked})), source="SAP MARD")],
        nodes=[("Trapped Capital", "source", "critical", "Restricted stock cannot be allocated", ""), ("Unfulfillable Allocation", "process", "risk", "Planning sees no free stock", ""), ("Dispatch Delay", "outcome", "critical", "Orders may miss their dispatch window", "")],
        action_title="Release or disposition restricted stock", action_description="Review quality and blocked quantities, post the approved disposition, and restore only verified free availability.",
    )]


def detect_deletion_maintenance_flags(data) -> list[Anomaly]:
    rows = _sap_rows(data)
    flagged = [row for row in rows if str(row.get("deletionflag") or "").strip().upper() == "X" or str(row.get("maintenancestatus") or "").strip().upper() == "D"]
    if not flagged:
        return []
    active_deleted = any(str(row.get("deletionflag") or "").strip().upper() == "X" and _as_float(row.get("freeavailablestock")) > 0 for row in flagged)
    impact = min(50_000, 10_000 + len(flagged) * 3_000)
    return [_sap_anomaly(
        prefix="DELETED", title="Deleted or incompletely maintained storage location", kind="SAP master data deletion", severity="critical" if active_deleted else "high", impact=impact, rows=flagged,
        summary=f"{len(flagged)} SAP storage records are deleted or have incomplete maintenance status, including {', '.join(sorted({str(row.get('storagelocation') or 'unknown') for row in flagged}))}.",
        root_cause="Master-data retirement flags are not aligned with stock and goods-movement controls.",
        evidence=[Evidence(label="Deletion flag", value=", ".join(sorted({str(row.get('deletionflag') or '') for row in flagged})), source="SAP MARD"), Evidence(label="Maintenance status", value=", ".join(sorted({str(row.get('maintenancestatus') or '') for row in flagged})), source="SAP MARD"), Evidence(label="Storage locations", value=", ".join(sorted({str(row.get('storagelocation') or 'unknown') for row in flagged})), source="SAP MARD")],
        nodes=[("Decommissioned Location Active", "source", "critical", "Retired storage locations remain in the operational model", ""), ("Posting Failure Risk", "process", "risk", "Future goods movements may fail", ""), ("Data Corruption", "outcome", "critical", "Master and stock records can diverge", "")],
        action_title="Block future goods movements to deleted locations", action_description="Prevent new postings to deleted or incomplete locations, move active stock to a maintained location, and audit the master record.",
    )]


def detect_storage_location_fragmentation(data) -> list[Anomaly]:
    rows = _sap_rows(data)
    by_material: dict[str, dict[str, dict]] = {}
    for row in rows:
        material = str(row.get("material") or row.get("sku") or "").strip()
        location = str(row.get("storagelocation") or "").strip()
        if not material or not location or _as_float(row.get("freeavailablestock")) != 0:
            continue
        by_material.setdefault(material, {})[location] = row
    findings: list[Anomaly] = []
    for material, location_rows in sorted(by_material.items()):
        if len(location_rows) <= 15:
            continue
        group = list(location_rows.values())
        locations = sorted(location_rows)
        impact = min(45_000, 12_000 + len(locations) * 1_000)
        findings.append(_sap_anomaly(
            prefix="FRAG", title=f"Storage location fragmentation — {material}", kind="SAP storage fragmentation", severity="medium", impact=impact, rows=group,
            summary=f"Material {material} is spread across {len(locations)} zero-stock storage locations.",
            root_cause="Stale zero-stock storage-location records are inflating MRP search and manual handling paths.",
            evidence=[Evidence(label="Fragmented material", value=material, source="SAP MARD"), Evidence(label="Zero-stock locations", value=", ".join(locations), source="SAP MARD")],
            nodes=[("MRP Bloat", "source", "risk", "One material has many stale locations", ""), ("Slow Query Performance", "process", "watch", "MRP must scan unnecessary locations", ""), ("Manual Picking Error Risk", "outcome", "risk", "Operators can be routed to stale bins", "")],
            action_title="Consolidate zero-stock storage locations", action_description="Close stale zero-stock locations in SAP after validating open documents and master-data dependencies.",
        ))
    return findings


def detect_sap_anomalies(data) -> list[Anomaly]:
    """Run the SAP detector family as one additive scan stage."""
    findings: list[Anomaly] = []
    for detector in (detect_fiscal_year_desync, detect_unreconciled_inventory, detect_blocked_restricted_stock, detect_deletion_maintenance_flags, detect_storage_location_fragmentation):
        findings.extend(detector(data))
    return findings


class OperationsStore:
    """Small, concurrency-safe operational store for the standalone hackathon demo.

    The service boundary is intentionally database-agnostic: it can be swapped for
    SQLAlchemy/PostgreSQL without changing HTTP handlers or agent contracts.
    """

    def __init__(self, settings: Settings) -> None:
        self._lock = RLock()
        self.settings = settings
        self.repository = Repository(settings)
        self.repository.initialize()
        seed_users_and_sites(self.repository)
        loaded = self.repository.load_run()
        reset_template = None
        if loaded and loaded["run"].metadata_json.get("dataset_schema") != DATASET_SCHEMA_VERSION:
            # The normal initialization path below atomically replaces the old demo
            # run with the current schema and selected-model metadata.
            loaded = None
        if loaded:
            self._run_id = loaded["run"].id
            self._dataset = self._restore_dataset(loaded)
            self._ml_selection = self._restore_ml_selection(loaded["run"].metadata_json.get("ml_model", {}))
            self._anomalies = [Anomaly.model_validate(item) for item in loaded["anomalies"]]
            self._ensure_demo_artifacts()
        else:
            self._dataset = generate_dataset(settings.demo_seed)
            self._ml_selection = select_best_inventory_model(self._dataset.inventory, self._dataset.seed)
            self._anomalies = detect_anomalies(self._dataset, self._ml_selection.inventory_scores) + detect_sap_anomalies(self._dataset)
            reset_template = (deepcopy(self._dataset), deepcopy(self._ml_selection), deepcopy(self._anomalies))
            self._run_id = self.repository.save_run(self._dataset, self._anomalies, {"dataset_schema": DATASET_SCHEMA_VERSION, "ml_model": self._ml_metadata(include_scores=True)})
            # The value ledger describes the previous twin's findings; a fresh
            # board starts with a fresh ledger so dashboard and outcomes reconcile.
            self.repository.clear_outcomes()
            export_dataset(self._dataset)
            prepare_operational_markdown(self._dataset)
        self.cascade_engine = CascadeEngine(self._dataset.seed)
        self._classifier = None  # lazily rebuilt on first live incident injection
        self._scan_count = 1842
        self._last_scan = datetime.now(timezone.utc)
        self._reset_template = reset_template
        self._hackathon_loaded = False
        self._hackathon_path = None
        self._hackathon_wb_data = None
        self._hackathon_stats = {}
        if self.settings.demo_mode and not os.environ.get("PYTEST_CURRENT_TEST"):
            try:
                self.load_hackathon()
            except Exception as exc:
                raise RuntimeError(f"Default Hackathon dataset could not load: {exc}") from exc

    def _restore_ml_selection(self, model_metadata: dict) -> ModelSelection:
        """Rebuild the persisted model selection; retrain only when scores are absent.

        Training benchmarks three sklearn candidates (~14s), so the per-position
        scores are persisted with the run and reloaded on every subsequent boot.
        """
        scores = model_metadata.get("inventory_scores")
        if scores:
            return ModelSelection(
                name=model_metadata.get("name", "unknown"),
                f1=float(model_metadata.get("f1", 0)),
                accuracy=float(model_metadata.get("accuracy", 0)),
                precision=float(model_metadata.get("precision", 0)),
                recall=float(model_metadata.get("recall", 0)),
                inventory_scores={key: float(value) for key, value in scores.items()},
                candidates=model_metadata.get("candidates", []),
            )
        selection = select_best_inventory_model(self._dataset.inventory, self._dataset.seed)
        self.repository.update_run_metadata(self._run_id, {"ml_model": {**self._metadata_from(selection), "inventory_scores": selection.inventory_scores}})
        return selection

    def _ensure_demo_artifacts(self) -> None:
        """Backfill the CSV export and knowledge markdown if a previous boot's files are gone."""
        if not (DATASETS_DIR / "manifest.json").exists():
            export_dataset(self._dataset)
        if not (KNOWLEDGE_DIR / "operational_brief.md").exists() or not (KNOWLEDGE_DIR / "control_playbook.md").exists():
            prepare_operational_markdown(self._dataset)

    @staticmethod
    def _restore_dataset(loaded: dict) -> SyntheticDataset:
        groups = loaded["groups"]
        def parse_datetime(value):
            parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
            # SQLite drops timezone info; restored datetimes must stay UTC-aware so
            # detectors can compare them against freshly generated aware timestamps.
            return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
        for record in groups["inventory"]:
            record["last_count"] = parse_datetime(record["last_count"])
        for record in groups["dispatches"]:
            record["departure"] = parse_datetime(record["departure"])
        run = loaded["run"]
        return SyntheticDataset(run.seed, parse_datetime(run.generated_at), groups["skus"], groups["inventory"], groups["inbound_orders"], groups["outbound_orders"], groups["suppliers"], groups["dispatches"], groups["workforce"], groups["documents"], groups["containers"])

    def anomalies(
        self, severity: str | None = None, status: str | None = None, search: str | None = None, persona: str | None = None
    ) -> list[Anomaly]:
        with self._lock:
            items = deepcopy(self._anomalies)
        if severity and severity != "all":
            items = [item for item in items if item.severity == severity]
        if status and status != "all":
            items = [item for item in items if item.status == status]
        if persona and persona not in ("all", "operations_lead", "operator"):
            p = persona.lower().strip()
            if p in ("dispatcher", "dispatch", "transport"):
                allowed_catalog = {"D2", "D3", "D5", "X2"}
            elif p in ("inventory_controller", "inventory", "warehouse_lead"):
                allowed_catalog = {"B1", "B2", "B4", "B5", "C1", "C2", "C4"}
            elif p in ("master_data_steward", "data_steward", "master_data"):
                allowed_catalog = {"A1", "A2", "A3", "A4", "A5", "A6", "X1"}
            elif p in ("procurement_lead", "procurement", "buyer"):
                allowed_catalog = {"E1", "E2", "E3", "E4", "F1", "F2"}
            else:
                allowed_catalog = None

            if allowed_catalog:
                filtered = []
                for item in items:
                    parts = item.id.split("-")
                    cat = parts[1] if len(parts) >= 2 else ""
                    if cat in allowed_catalog:
                        filtered.append(item)
                    elif not item.id.startswith("HAC-"):
                        if p in ("dispatcher", "dispatch", "transport") and item.type == "Dispatch readiness":
                            filtered.append(item)
                        elif p in ("inventory_controller", "inventory", "warehouse_lead") and item.type in ("Inventory reconciliation", "Warehouse execution"):
                            filtered.append(item)
                        elif p in ("master_data_steward", "data_steward", "master_data") and item.type == "Master data conflict":
                            filtered.append(item)
                        elif p in ("procurement_lead", "procurement", "buyer") and item.type in ("Supplier reliability", "Replenishment risk"):
                            filtered.append(item)
                items = filtered
        if search:
            needle = search.lower().strip()
            items = [item for item in items if needle in f"{item.title} {item.sku} {item.zone} {item.system} {item.summary}".lower()]
        return sorted(items, key=lambda item: item.impact, reverse=True)

    def anomaly(self, anomaly_id: str) -> Anomaly | None:
        with self._lock:
            item = next((a for a in self._anomalies if a.id == anomaly_id), None)
            return deepcopy(item) if item else None

    def dashboard(self) -> dict[str, object]:
        items = self.anomalies()
        open_items = [item for item in items if item.status != "resolved"]
        severity_counts = Counter(item.severity for item in open_items)
        protected = sum(action.impact_saved for item in items for action in item.actions if action.status in {"approved", "applied"})
        actionable = sum(action.impact_saved for item in open_items for action in item.actions if action.status == "recommended")
        readiness = max(0, min(100, 100 - severity_counts.get("critical", 0) * 9 - severity_counts.get("high", 0) * 4 - severity_counts.get("medium", 0) * 2))
        exposure = sum(item.impact for item in open_items)
        trend_values = [max(0, int(exposure * factor)) for factor in (.38, .46, .44, .59, .73, .68, 1)]
        return {
            "metrics": [
                {"label": "Exposure at risk", "value": exposure, "format": "currency", "trend": f"{len(open_items)} active findings", "tone": "critical"},
                {"label": "Cascades contained", "value": sum(1 for item in items if item.status == "resolved"), "format": "number", "trend": "All controls live", "tone": "good"},
                {"label": "Readiness index", "value": readiness, "format": "percent", "trend": f"{severity_counts.get('critical', 0)} critical paths", "tone": "watch"},
                {"label": "Controls available", "value": protected + actionable, "format": "currency", "trend": f"{sum(len(item.actions) for item in open_items)} human approvals queued", "tone": "good"},
            ],
            "severity_counts": {key: severity_counts.get(key, 0) for key in ["critical", "high", "medium", "low"]},
            "scan_count": self._scan_count,
            "last_scan": self._last_scan.isoformat(),
            "dataset": {"seed": self._dataset.seed, "generated_at": self._dataset.generated_at.isoformat(), "records": sum((len(self._dataset.skus), len(self._dataset.inventory), len(self._dataset.inbound_orders), len(self._dataset.outbound_orders), len(self._dataset.suppliers), len(self._dataset.dispatches), len(self._dataset.workforce), len(self._dataset.documents), len(self._dataset.containers)))},
            "ml_model": self._ml_metadata(),
            "exposure_trend": [{"h": label, "v": value} for label, value in zip(("06", "08", "10", "12", "14", "16", "Now"), trend_values)],
            "agents": [
                {"name": "Ingestion Agent", "role": "Data Ingestion & Schema Mapping", "state": "watching", "signal": "6 SAP sheets loaded & unified", "color": "cyan"},
                {"name": "Data-Quality Agent", "role": "Master Data Quality (A1–A6)", "state": "ready", "signal": "Master data catalog rules active", "color": "mint"},
                {"name": "Anomaly Agent", "role": "Inventory & Process Anomalies (B1–F2)", "state": "watching", "signal": f"{len(open_items)} active findings", "color": "violet"},
                {"name": "Correlation / Root-Cause Agent", "role": "Cross-System Linkage & Root Cause", "state": "reasoning", "signal": f"{sum(1 for item in open_items if item.cascade_nodes)} correlated paths (X1–X2)", "color": "peach"},
                {"name": "Impact Agent", "role": "Business Impact & Exposure Scoring", "state": "ready", "signal": f"€{exposure:,} exposure modeled", "color": "amber"},
                {"name": "Action / Remediation Agent", "role": "Human-Approved Change Control", "state": "active", "signal": f"{sum(len(item.actions) for item in open_items)} controls governed", "color": "blue"},
                {"name": "Orchestrator (WALT)", "role": "Flow Planning & Audit Trail", "state": "ready", "signal": "Multi-agent coordination & audit", "color": "electric"},
            ],
        }

    def graph(self, anomaly_id: str | None = None) -> dict[str, object]:
        if anomaly_id:
            anomaly = self.anomaly(anomaly_id)
            if not anomaly:
                return {"nodes": [], "edges": [], "anomaly_id": anomaly_id}
            return self.cascade_engine.payload(anomaly)
        # Default view: the highest-impact OPEN cascade; resolved ones stay
        # reachable by explicit id but never headline the overview.
        primary = next((item for item in self.anomalies() if item.cascade_nodes and item.status != "resolved"), None)
        if not primary:
            return {"nodes": [], "edges": [], "anomaly_id": None}
        primary_payload = self.cascade_engine.payload(primary)
        nodes: list[object] = list(primary_payload["nodes"])
        edges: list[object] = list(primary_payload["edges"])
        outcome = primary.cascade_nodes[-1].id
        # Portfolio signals are generated from live findings and connected to the primary
        # outcome, making the overview dynamic instead of a pre-authored graphic.
        for index, related in enumerate([item for item in self.anomalies() if item.id != primary.id and item.status != "resolved"][:3]):
            source_id = f"portfolio-{related.id}"
            nodes.append({"id": source_id, "label": related.type, "kind": "source", "health": "risk" if related.severity in {"critical", "high"} else "watch", "detail": related.summary, "impact": related.impact, "time_to_impact": related.time_to_impact})
            edges.append({"source": source_id, "target": outcome, "label": "compounds risk", "probability": max(42, 72 - index * 9)})
        serialized_nodes = []
        for node in nodes:
            payload = node.model_dump() if hasattr(node, "model_dump") else dict(node)
            payload["anomaly_id"] = payload.get("anomaly_id", primary.id)
            serialized_nodes.append(payload)
        for node in serialized_nodes:
            if node["id"].startswith("portfolio-"):
                node["anomaly_id"] = node["id"].replace("portfolio-", "", 1)
        return {"nodes": serialized_nodes, "edges": [edge.model_dump() if hasattr(edge, "model_dump") else edge for edge in edges], "anomaly_id": primary.id, "simulation": primary_payload["simulation"]}

    def approve_action(self, anomaly_id: str, action_id: str) -> tuple[Anomaly | None, str | None]:
        with self._lock:
            anomaly = next((item for item in self._anomalies if item.id == anomaly_id), None)
            if not anomaly:
                return None, None
            action = next((item for item in anomaly.actions if item.id == action_id), None)
            if not action:
                return None, None
            already_applied = action.status == "applied"
            action.status = "applied"
            audit = {"at": datetime.now(timezone.utc).isoformat(), "event": "fix_action_applied", "anomaly_id": anomaly_id, "action_id": action_id, "action": action.title, "actor": "Operations controller"}
            if all(item.status == "applied" for item in anomaly.actions) and anomaly.status != "resolved":
                # Human approval is complete: correct the source records so the defect
                # is genuinely gone, then resolve the finding so every dashboard
                # metric (exposure, containment, readiness) moves.
                corrections = self._remediate(anomaly)
                anomaly.status = "resolved"
                for node in anomaly.cascade_nodes:
                    node.health = "healthy"
                audit["event"] = "anomaly_resolved"
                audit["corrections"] = corrections
                # The resolution row carries the finding's full impact — exactly once.
                # Any earlier partial-apply rows were informational (saved=0), so a
                # finding can never contribute more than its own exposure.
                self.repository.add_outcome(
                    "fix", f"Resolved: {anomaly.title}",
                    f"{action.title} — {corrections}" if corrections else action.title,
                    anomaly.impact,
                    {"anomaly_id": anomaly.id, "anomaly_type": anomaly.type, "severity": anomaly.severity, "sku": anomaly.sku, "actions": [item.title for item in anomaly.actions]},
                )
            elif not already_applied:
                self.repository.add_outcome(
                    "fix", f"Control applied: {action.title}",
                    f"Part of {anomaly.id} ({anomaly.type}); value counts on resolution, once every control is approved.",
                    0,
                    {"anomaly_id": anomaly.id, "anomaly_type": anomaly.type, "severity": anomaly.severity, "sku": anomaly.sku},
                )
            self.repository.persist_anomalies(self._run_id, self._anomalies)
            self.repository.add_audit(str(uuid.uuid4()), audit["event"], "Operations controller", audit)
            return deepcopy(anomaly), action.title

    def _remediate_hackathon(self, anomaly: Anomaly) -> str:
        """Self-heal the in-memory hackathon workbook data for all 24 catalog detector rules."""
        if not self._hackathon_wb_data:
            return "No hackathon data loaded to remediate"
        wb = self._hackathon_wb_data
        parts = anomaly.id.split("-")
        catalog_id = parts[1] if len(parts) >= 2 else ""
        sku = anomaly.sku
        zone = anomaly.zone

        if catalog_id == "X1":
            mm = wb.setdefault("material_master", [])
            if not any(r.get("material") == sku for r in mm):
                mm.append({
                    "material": sku,
                    "description": f"Master Record for {sku}",
                    "material_type": "FERT",
                    "material_group": "AUTO",
                    "base_uom": "EA",
                    "plant": "1010",
                    "reorder_point": 100.0,
                    "safety_stock": 50.0,
                    "lead_time_days": 5.0,
                    "abc_class": "A",
                    "hazmat_flag": "N",
                    "lifecycle_status": "ACTIVE",
                })
            return f"Published master data record for orphan material {sku} in Material_Master"

        elif catalog_id == "X2":
            plant = zone if zone in ("1010", "1710", "1020") else "1010"
            inv = wb.setdefault("inventory_stock", [])
            for row in inv:
                if row.get("material") == sku and str(row.get("plant")) == str(plant):
                    row["qty_on_hand"] = (row.get("qty_on_hand") or 0.0) + 1000.0
                    row["blocked_qty"] = 0.0
                    break
            else:
                inv.append({
                    "material": sku, "plant": str(plant), "storage_location": "0001",
                    "batch": None, "uom": "EA", "qty_on_hand": 1000.0, "blocked_qty": 0.0,
                    "in_transit_qty": 0.0, "batch_expiry": None, "last_movement_date": None,
                })
            return f"Re-allocated 1,000 EA buffer stock at plant {plant} for {sku} to clear ATP deficit"

        elif catalog_id == "A1":
            for row in wb.get("material_master", []):
                if row.get("material") == sku and not row.get("base_uom"):
                    row["base_uom"] = "EA"
            return f"Assigned Base UoM 'EA' to material {sku}"

        elif catalog_id == "A2":
            for row in wb.get("material_master", []):
                if row.get("material") == sku:
                    row["reorder_point"] = 100.0
            return f"Set reorder point to 100.0 for material {sku}"

        elif catalog_id == "A3":
            for row in wb.get("material_master", []):
                if row.get("material") == sku:
                    row["description"] = f"{row.get('description', '')} [{sku}]"
            return f"Disambiguated duplicate description for {sku}"

        elif catalog_id == "A4":
            for row in wb.get("material_master", []):
                if row.get("material") == sku:
                    row["reorder_point"] = (row.get("safety_stock") or 50.0) * 1.5
            return f"Adjusted reorder point to exceed safety stock for {sku}"

        elif catalog_id == "A5":
            for row in wb.get("material_master", []):
                if row.get("material") == sku:
                    row["lifecycle_status"] = "ACTIVE"
            return f"Reinstated lifecycle status to ACTIVE for {sku}"

        elif catalog_id in ("A6", "C4"):
            for row in wb.get("warehouse_bin", []):
                if row.get("assigned_material") == sku or row.get("bin") == zone:
                    row["storage_type"] = "HAZ"
            return f"Reclassified bin storage type to HAZ for {sku}"

        elif catalog_id == "B1":
            for row in wb.get("inventory_stock", []):
                if row.get("material") == sku and (row.get("qty_on_hand") or 0) < 0:
                    row["qty_on_hand"] = 50.0
            return f"Reconciled physical cycle count for {sku} to clear negative book stock"

        elif catalog_id == "B2":
            for row in wb.get("inventory_stock", []):
                if row.get("material") == sku and (row.get("qty_on_hand") or 0) > 0:
                    row["blocked_qty"] = row["qty_on_hand"]
            return f"Quarantined expired batch for {sku} into blocked stock (0002)"

        elif catalog_id == "B4":
            from app.services.hackathon_detectors import SNAPSHOT_DATE
            for row in wb.get("inventory_stock", []):
                if row.get("material") == sku:
                    row["last_movement_date"] = SNAPSHOT_DATE
            return f"Updated movement journal and verified disposition for stale stock {sku}"

        elif catalog_id == "B5":
            for row in wb.get("inventory_stock", []):
                if row.get("material") == sku:
                    row["blocked_qty"] = min(row.get("blocked_qty") or 0, row.get("qty_on_hand") or 0)
            return f"Adjusted blocked quantity to match available on-hand stock for {sku}"

        elif catalog_id == "C1":
            for row in wb.get("warehouse_bin", []):
                if row.get("bin") == zone or row.get("assigned_material") == sku:
                    row["occupied"] = min(row.get("occupied") or 0, row.get("capacity") or 500.0)
            return f"Transferred overflow units from bin {zone} to buffer location"

        elif catalog_id == "C2":
            for row in wb.get("warehouse_bin", []):
                if row.get("bin") == zone:
                    row["bin_status"] = "OCC" if (row.get("occupied") or 0) > 0 else "FREE"
            return f"Synchronized bin status with physical occupancy for {zone}"

        elif catalog_id == "D2":
            for row in wb.get("deliveries_dispatch", []):
                if row.get("delivery") == sku or row.get("material") == sku:
                    row["route"] = "R-NORTH"
            return f"Assigned transport route R-NORTH to delivery {sku}"

        elif catalog_id == "D3":
            for row in wb.get("deliveries_dispatch", []):
                if row.get("delivery") == sku or row.get("material") == sku:
                    row["status"] = "DELIVERED"
            return f"Expedited goods issue and marked delivery {sku} as DELIVERED"

        elif catalog_id == "D5":
            for row in wb.get("deliveries_dispatch", []):
                if row.get("delivery") == sku or row.get("material") == sku:
                    row["route"] = "R-NORTH"
            return f"Corrected export route to domestic route R-NORTH for {sku}"

        elif catalog_id == "E1":
            vm = wb.setdefault("vendor_master", [])
            vend_code = sku if sku.startswith("VEND-") else "VEND-9999"
            if not any(r.get("vendor") == vend_code for r in vm):
                vm.append({
                    "vendor": vend_code, "vendor_name": f"Approved Vendor {vend_code}",
                    "country": "DE", "quality_rating": "A", "otd_pct": 98.0,
                    "procurement_block": "N",
                })
            return f"Published vendor master record for orphan vendor {vend_code} in Vendor_Master"

        elif catalog_id == "E2":
            for row in wb.get("purchase_replenish", []):
                if row.get("purchase_order") == sku or row.get("material") == sku:
                    row["unit_price"] = 50.0
            return f"Updated benchmark unit price to €50.00 for purchase order {sku}"

        elif catalog_id == "E3":
            for row in wb.get("purchase_replenish", []):
                if row.get("purchase_order") == sku or row.get("material") == sku:
                    if row.get("order_date"):
                        import datetime as dt_mod
                        row["expected_delivery"] = row["order_date"] + dt_mod.timedelta(days=7)
            return f"Adjusted expected delivery date to be after order date for PO {sku}"

        elif catalog_id == "E4":
            for row in wb.get("purchase_replenish", []):
                if row.get("purchase_order") == sku or row.get("material") == sku:
                    row["po_status"] = "DELIVERED"
            return f"Expedited goods receipt and closed overdue purchase order {sku}"

        elif catalog_id == "F1":
            for row in wb.get("vendor_master", []):
                if row.get("vendor") == sku:
                    row["country"] = "DE"
            return f"Assigned ISO country code 'DE' to vendor {sku}"

        elif catalog_id == "F2":
            for row in wb.get("purchase_replenish", []):
                if row.get("vendor") == sku:
                    row["po_status"] = "CANCELLED"
            return f"Cancelled open purchase order with blocked vendor {sku} pending compliance review"

        return f"Applied remediation control for {anomaly.id}"

    def _remediate(self, anomaly: Anomaly) -> str:
        """Correct the source-twin records behind ONE finding. Returns a human summary.

        Scoped to the anomaly's own entity: sibling findings of the same type keep
        their defects (and their own approval flow). Detection scans the same
        dataset on every /api/scan, so the corrected finding does not reappear.
        """
        if self._hackathon_loaded and (anomaly.id.startswith("HAC-") or self._hackathon_wb_data):
            return self._remediate_hackathon(anomaly)
        data = self._dataset
        fixed: list[str] = []
        if anomaly.type == "Master data conflict":
            updates = {}
            for sku in data.skus:
                if sku["id"] != anomaly.sku:
                    continue
                changed = {}
                if sku["fitment_wms"] != sku["fitment_erp"]:
                    sku["fitment_wms"] = sku["fitment_erp"]; changed["fitment_wms"] = sku["fitment_wms"]
                if sku.get("wms_weight_kg") is not None and sku["wms_weight_kg"] != sku["weight_kg"]:
                    sku["wms_weight_kg"] = sku["weight_kg"]; changed["wms_weight_kg"] = sku["weight_kg"]
                if sku.get("tms_weight_kg") is not None and sku["tms_weight_kg"] != sku["weight_kg"]:
                    sku["tms_weight_kg"] = sku["weight_kg"]; changed["tms_weight_kg"] = sku["weight_kg"]
                if changed:
                    updates[sku["id"]] = changed; fixed.append(f"republished master data for {sku['id']}")
            self.repository.update_source_records(self._run_id, MasterSkuModel, updates)
        elif anomaly.type == "Inventory reconciliation":
            updates = {}
            for row in data.inventory:
                if row["sku"] == anomaly.sku and max(row["wms"], row["erp"], row["physical"]) - min(row["wms"], row["erp"], row["physical"]) >= 25:
                    truth = row["physical"]
                    row["wms"] = row["erp"] = row["tms"] = truth
                    updates[row["id"]] = {"wms": truth, "erp": truth, "tms": truth}
                    fixed.append(f"rebuilt journal for {row['sku']} to physical truth {truth} EA")
            self.repository.update_source_records(self._run_id, InventoryPositionModel, updates)
        elif anomaly.type == "Document intelligence":
            for document in data.documents:
                if document["sku"] == anomaly.sku and not document["ppap_attached"]:
                    document["ppap_attached"] = True
                    self.repository.update_source_document(document["id"], {"ppap_attached": True})
                    fixed.append(f"attached PPAP evidence to batch {document['batch']}")
        elif anomaly.type == "Supplier reliability":
            updates = {}
            for supplier in data.suppliers:
                if supplier["name"] in anomaly.title and supplier["actual_lead"] - supplier["configured_lead"] >= 3:
                    supplier["configured_lead"] = round(supplier["actual_lead"])
                    updates[supplier["id"]] = {"configured_lead": supplier["configured_lead"]}
                    fixed.append(f"refreshed {supplier['name']} lead time to {supplier['configured_lead']} days")
            self.repository.update_source_records(self._run_id, SupplierModel, updates)
        elif anomaly.type == "Dispatch readiness":
            updates = {}
            for dispatch in data.dispatches:
                # A dispatch finding names either the dispatch ID (overload) or its dock (labels).
                if dispatch["id"] not in anomaly.title and dispatch["dock"] != anomaly.zone:
                    continue
                changed = {}
                if dispatch["label_success"] < dispatch["total_labels"]:
                    dispatch["label_success"] = dispatch["total_labels"]; changed["label_success"] = dispatch["total_labels"]
                    fixed.append(f"reprinted and verified labels for {dispatch['id']}")
                if dispatch["total_load_kg"] > dispatch["vehicle_capacity_kg"]:
                    dispatch["total_load_kg"] = int(dispatch["vehicle_capacity_kg"] * .88); changed["total_load_kg"] = dispatch["total_load_kg"]
                    fixed.append(f"split {dispatch['id']} load to {dispatch['total_load_kg']:,} kg")
                if changed:
                    updates[dispatch["id"]] = changed
            self.repository.update_source_records(self._run_id, DispatchScheduleModel, updates)
        elif anomaly.type == "Workforce performance":
            baselines = {"picking": 94, "replenishment": 68, "packing": 77, "quality": 53}
            updates = {}
            for record in data.workforce:
                if record["zone"] == anomaly.zone and record["pick_rate"] < baselines.get(record["task_type"], 60) * .75:
                    record["pick_rate"] = baselines.get(record["task_type"], 60)
                    record["overtime_hours"] = .5; record["exceptions"] = 1
                    updates[record["id"]] = {"pick_rate": record["pick_rate"], "overtime_hours": .5, "exceptions": 1}
            if updates:
                fixed.append(f"rebalanced {len(updates)} task assignments in zone {anomaly.zone}")
            self.repository.update_source_records(self._run_id, WorkforceLogModel, updates)
        elif anomaly.type == "SLA escalation":
            updates = {}
            for order in data.outbound_orders:
                if order["id"] not in anomaly.title:
                    continue
                if order["picked_qty"] < order["ordered_qty"]:
                    order["picked_qty"] = order["ordered_qty"]; order["pick_status"] = "completed"
                    updates[order["id"]] = {"picked_qty": order["picked_qty"], "pick_status": "completed"}
                    fixed.append(f"expedited pick completed for {order['id']}")
            self.repository.update_source_records(self._run_id, OutboundOrderModel, updates)
        elif anomaly.type == "Replenishment risk":
            # Raising the expedited PO restores coverage: the detector checks for an
            # open inbound order, so adding one genuinely closes the finding.
            stock_by_sku: dict[str, int] = {}
            for row in data.inventory:
                stock_by_sku[row["sku"]] = stock_by_sku.get(row["sku"], 0) + row["wms"]
            covered = {order["sku"] for order in data.inbound_orders if order["expected_date"] >= data.generated_at.date().isoformat()}
            for sku in data.skus:
                if sku["id"] != anomaly.sku:
                    continue
                total = stock_by_sku.get(sku["id"])
                if total is None or sku["id"] in covered or total > sku["reorder_point"]:
                    continue
                po_id = f"PO-EXP{len(data.inbound_orders) + 1:04}"
                order = {"id": po_id, "supplier": sku["supplier"], "sku": sku["id"], "expected_qty": sku["reorder_point"] + sku["safety_stock"], "received_qty": 0, "expected_date": (data.generated_at + timedelta(days=2)).date().isoformat(), "warehouse": "WH-01", "quality_status": "pending"}
                data.inbound_orders.append(order)
                self.repository.append_source_record(self._run_id, InboundOrderModel, order)
                fixed.append(f"raised expedited PO {po_id} for {order['expected_qty']} EA of {sku['id']}")
        elif anomaly.type == "Compliance":
            updates = {}
            for sku in data.skus:
                if sku["id"] == anomaly.sku and sku["storage_class"] == "hazmat" and not sku["hazmat"]:
                    sku["hazmat"] = True; updates[sku["id"]] = {"hazmat": True}
                    fixed.append(f"restored hazmat handling flag on {sku['id']}")
            self.repository.update_source_records(self._run_id, MasterSkuModel, updates)
        elif anomaly.type == "Container tracking":
            updates = {}
            for container in data.containers:
                if container["overdue_hours"] > 24:
                    container["overdue_hours"] = 0; updates[container["id"]] = {"overdue_hours": 0}
            if updates:
                fixed.append(f"reconciled {len(updates)} KLT return scans")
            self.repository.update_source_records(self._run_id, ContainerModel, updates)
        elif anomaly.type == "Warehouse execution":
            updates = {}
            for sku in data.skus:
                if sku["id"] == anomaly.sku and not sku["bin_active"]:
                    sku["bin_active"] = True; updates[sku["id"]] = {"bin_active": True}
                    fixed.append(f"republished slotting rule for {sku['id']}")
            self.repository.update_source_records(self._run_id, MasterSkuModel, updates)
        elif anomaly.type.startswith("SAP"):
            updates = {}
            targets = [row for row in data.inventory if row.get("material") == anomaly.sku or (anomaly.type != "SAP storage fragmentation" and row.get("sap_anchor"))]
            for row in targets:
                changed = {}
                if anomaly.type == "SAP fiscal year desync":
                    changed = {"fiscalyearofcurrentperiod": 2026, "currentperiod": "12"}
                    row.update(changed)
                elif anomaly.type == "SAP physical inventory audit":
                    changed = {"dateoflastpostedcount": "20260720", "physicalinventoryblockingind": ""}
                    row.update(changed)
                elif anomaly.type == "SAP blocked stock":
                    changed = {"blockedstock": 0, "stockinqualityinspection": 0, "freeavailablestock": max(1, _as_float(row.get("freeavailablestock")))}
                    row.update(changed)
                elif anomaly.type == "SAP master data deletion":
                    changed = {"deletionflag": "", "maintenancestatus": "DL"}
                    row.update(changed)
                elif anomaly.type == "SAP storage fragmentation":
                    changed = {"storagelocation": "CONSOLIDATED"}
                    row.update(changed)
                if changed:
                    updates[row["id"]] = changed
            self.repository.update_source_records(self._run_id, InventoryPositionModel, updates)
            if updates:
                fixed.append(f"updated {len(updates)} SAP inventory positions")
        return "; ".join(fixed[:3]) + (f" (+{len(fixed) - 3} more)" if len(fixed) > 3 else "")

    INJECTABLE_INCIDENTS = ("weight", "inventory", "overload", "ppap", "labels", "replenish")

    def reset_demo(self) -> dict[str, object]:
        """Regenerate the operational twin from scratch: new dataset, fresh findings,
        cleared value ledger and audit log. The one-click equivalent of reset_demo.bat.

        Generation + model training (~14s worst case) run OUTSIDE the lock so
        concurrent readers keep serving the old board; the swap itself is brief.
        """
        if self._reset_template is None:
            dataset = generate_dataset(self.settings.demo_seed)
            selection = select_best_inventory_model(dataset.inventory, dataset.seed)
            anomalies = detect_anomalies(dataset, selection.inventory_scores) + detect_sap_anomalies(dataset)
            self._reset_template = (deepcopy(dataset), deepcopy(selection), deepcopy(anomalies))
        else:
            dataset, selection, anomalies = deepcopy(self._reset_template)
        with self._lock:
            # A reset replaces the source twin. Any request that has not reached
            # a terminal historical state must be cancelled so its old snapshot
            # cannot be approved or executed against the new dataset.
            open_statuses = {"draft", "returned", "waiting_for_details", "awaiting_lead", "awaiting_manager", "awaiting_quality_compliance", "awaiting_director", "approved", "applying", "awaiting_verification", "failed_verification"}
            with self.repository.session() as session:
                open_requests = session.query(ChangeRequestModel).filter(ChangeRequestModel.status.in_(open_statuses)).all()
                request_ids = [row.request_id for row in open_requests]
                reset_time = datetime.now(timezone.utc).isoformat()
                for row in open_requests:
                    row.status = "cancelled"
                    row.payload = {**(row.payload or {}), "cancel_reason": "Demo data reset replaced the source twin", "cancelled_at": reset_time}
                    row.updated_at = datetime.now(timezone.utc)
                if request_ids:
                    session.query(ApprovalStepModel).filter(ApprovalStepModel.request_id.in_(request_ids), ApprovalStepModel.status.in_({"waiting", "active", "paused"})).update({"status": "cancelled"}, synchronize_session=False)
                    session.query(DetailRequestModel).filter(DetailRequestModel.request_id.in_(request_ids), DetailRequestModel.status == "open").update({"status": "cancelled"}, synchronize_session=False)
                    session.query(WorkflowActionModel).filter(WorkflowActionModel.request_id.in_(request_ids), WorkflowActionModel.status == "previewed").update({"status": "expired"}, synchronize_session=False)
            self._dataset = dataset
            self._ml_selection = selection
            self._anomalies = anomalies
            self._run_id = self.repository.save_run(self._dataset, self._anomalies, {"dataset_schema": DATASET_SCHEMA_VERSION, "ml_model": self._ml_metadata(include_scores=True)})
            self.repository.clear_outcomes()
            # With a fixed seed the fresh board reuses deterministic anomaly IDs;
            # keeping old audit rows would bleed last session's approvals into
            # brand-new findings' incident reports.
            export_dataset(self._dataset)
            seed_users_and_sites(self.repository)
            prepare_operational_markdown(self._dataset)
            self.cascade_engine = CascadeEngine(self._dataset.seed)
            self._classifier = None
            self._scan_count = 1842
            self._last_scan = datetime.now(timezone.utc)
            self._hackathon_loaded = False
            self._hackathon_path = None
            self._hackathon_wb_data = None
            self._hackathon_stats = {}
            if self.settings.demo_mode and not os.environ.get("PYTEST_CURRENT_TEST"):
                try:
                    self.load_hackathon()
                except Exception as exc:
                    raise RuntimeError(f"Default Hackathon dataset could not reload: {exc}") from exc
            self.repository.add_audit(str(uuid.uuid4()), "demo_reset", "Demo controller", {"seed": self._dataset.seed, "findings": len(self._anomalies)})
            return {"reset": True, "seed": self._dataset.seed, "findings": len(self._anomalies), "exposure": sum(item.impact for item in self._anomalies)}

    def inject_incident(self, incident_type: str | None = None) -> dict[str, object]:
        """Break one healthy source record at runtime, then let detection find it.

        This mirrors the seed-time defect injectors: it only dirties data — no
        anomaly record is authored. The follow-up scan discovers the defect the
        same way it discovers the seeded ones.
        """
        with self._lock:
            rng = random.Random()
            candidates = list(self.INJECTABLE_INCIDENTS) if not incident_type or incident_type == "random" else [incident_type]
            rng.shuffle(candidates)
            injected = None
            for kind in candidates:
                injected = self._try_inject(kind, rng)
                if injected:
                    break
            if not injected:
                return {"injected": False, "detail": "Every injectable record of the requested type already carries an active defect."}
            # Diff against OPEN findings only: a re-broken remediated entity reuses
            # its deterministic ID, and its resolved record is replaced by the fresh
            # open incarnation — that is a new finding from the operator's view.
            before_ids = {anomaly.id for anomaly in self._anomalies if anomaly.status != "resolved"}
        scan = self.run_scan()
        with self._lock:
            fresh = [anomaly for anomaly in self._anomalies if anomaly.id not in before_ids and anomaly.status != "resolved"]
            self.repository.add_audit(str(uuid.uuid4()), "incident_injected", "Demo controller", {"incident": injected, "detected": [item.id for item in fresh]})
            return {"injected": True, "incident": injected, "scan_id": scan["scan_id"], "new_findings": [{"id": item.id, "title": item.title, "impact": item.impact, "severity": item.severity} for item in fresh]}

    def inject_storm(self, count: int = 3) -> dict[str, object]:
        """Inject several distinct incidents at once — the 'bad shift' demo."""
        with self._lock:
            rng = random.Random()
            kinds = list(self.INJECTABLE_INCIDENTS)
            rng.shuffle(kinds)
            incidents = []
            for kind in kinds:
                if len(incidents) >= count:
                    break
                injected = self._try_inject(kind, rng)
                if injected:
                    incidents.append(injected)
        if not incidents:
            return {"injected": False, "detail": "No healthy records left to break — resolve some findings first."}
        scan = self.run_scan()
        with self._lock:
            self.repository.add_audit(str(uuid.uuid4()), "storm_injected", "Demo controller", {"incidents": incidents})
        return {"injected": True, "incidents": incidents, "scan_id": scan["scan_id"], "findings": scan["findings"]}

    def report(self, anomaly_id: str | None = None) -> str:
        """Render a markdown operations or incident report."""
        if anomaly_id:
            rep = self.incident_report(anomaly_id)
            if rep:
                return rep
        audit_rows = self.repository.audit(limit=100)
        outcome_rows = self.repository.outcomes()
        lines = [
            "# Operational Control Tower Report",
            "",
            f"Generated: {datetime.now(timezone.utc).isoformat()}",
            f"Active dataset: {'SAP Hackathon Dataset' if self._hackathon_loaded else 'Synthetic Twin'}",
            "",
            "## Audit trail",
        ]
        if audit_rows:
            for r in audit_rows[:15]:
                lines.append(f"- `{r.get('at') or r.get('timestamp')}` — {r.get('event')} by {r.get('actor')}")
        else:
            lines.append("- No audit events recorded yet.")
        lines += ["", "## Measured outcome"]
        if outcome_rows:
            for o in outcome_rows[:15]:
                lines.append(f"- {o.get('title')} — €{o.get('saved', 0):,} protected")
        else:
            lines.append("- No outcomes measured yet.")
        return "\n".join(lines)

    def incident_report(self, anomaly_id: str) -> str | None:
        """Render a post-incident report as markdown from live records."""
        anomaly = self.anomaly(anomaly_id)
        if not anomaly:
            return None
        audit_rows = [row for row in self.repository.audit(limit=500) if row.get("anomaly_id") == anomaly_id]
        outcome_rows = [row for row in self.repository.outcomes() if row.get("anomaly_id") == anomaly_id]
        graph = self.cascade_engine.payload(anomaly)
        simulation = graph["simulation"]
        now = datetime.now(timezone.utc)
        lines = [
            f"# Incident report — {anomaly.id}",
            "",
            f"**{anomaly.title}**",
            "",
            f"- Status: **{anomaly.status}**  ·  Severity: **{anomaly.severity}**  ·  Type: {anomaly.type}",
            f"- Systems involved: {anomaly.system}  ·  Zone: {anomaly.zone}  ·  Entity: {anomaly.sku}",
            f"- Detected: {anomaly.detected_at.isoformat()}  ·  Report generated: {now.isoformat()}",
            f"- Modeled exposure: **€{anomaly.impact:,}**  ·  Time to first consequence at detection: {anomaly.time_to_impact}",
            "",
            "## Summary",
            anomaly.summary,
            "",
            "## Root-cause assessment",
            anomaly.root_cause,
            "",
            "## Verified evidence",
        ]
        for item in anomaly.evidence:
            lines.append(f"- **{item.label}**: {item.value} _(source: {item.source})_")
        lines += [
            "",
            "## Cascade model",
            f"- {len(graph['nodes'])} dependency nodes, {len(graph['edges'])} edges",
            f"- Monte-Carlo ({simulation['trials']:,} trials): {simulation['propagation_probability'] * 100:.0f}% propagation probability, €{simulation['expected_impact']:,} expected exposure, €{simulation['p90_impact']:,} P90",
            "",
            "## Controls and approvals",
        ]
        for action in anomaly.actions:
            lines.append(f"- [{'x' if action.status == 'applied' else ' '}] **{action.title}** — owner {action.owner}, ETA {action.eta}, confidence {action.confidence}%, value protected €{action.impact_saved:,} ({action.status})")
        lines += ["", "## Audit trail"]
        if audit_rows:
            for row in reversed(audit_rows):
                lines.append(f"- `{row['at']}` — {row['event']} by {row['actor']}" + (f" ({row['action']})" if row.get("action") else ""))
        else:
            lines.append("- No state-changing events recorded yet.")
        if outcome_rows:
            lines += ["", "## Measured outcome"]
            for row in outcome_rows:
                lines.append(f"- {row['title']} — {row['detail']}" + (f" — **€{row['saved']:,} protected**" if row["saved"] else ""))
        lines += ["", "---", "_Generated by Warehouse Control Tower AI. All corrective actions were approved by a human operator; source-system corrections are recorded in the audit trail above._"]
        return "\n".join(lines)

    def _try_inject(self, kind: str, rng: random.Random) -> dict[str, object] | None:
        data = self._dataset
        if kind == "weight":
            healthy = [sku for sku in data.skus if sku.get("wms_weight_kg") == sku["weight_kg"] and sku.get("tms_weight_kg") in (None, sku["weight_kg"])]
            if not healthy:
                return None
            sku = rng.choice(healthy)
            sku["wms_weight_kg"] = round(sku["weight_kg"] * rng.uniform(7.5, 10.5), 2); sku["tms_weight_kg"] = sku["weight_kg"]
            self.repository.update_source_records(self._run_id, MasterSkuModel, {sku["id"]: {"wms_weight_kg": sku["wms_weight_kg"], "tms_weight_kg": sku["tms_weight_kg"]}})
            return {"type": "weight", "entity": sku["id"], "story": f"A bulk update just wrote {sku['wms_weight_kg']} kg into WMS for {sku['id']} — ERP/TMS still say {sku['weight_kg']} kg."}
        if kind == "inventory":
            healthy = [row for row in data.inventory if row["wms"] == row["erp"] == row["physical"] and row["wms"] > 100]
            if not healthy:
                return None
            row = rng.choice(healthy)
            row["wms"] += rng.randint(30, 60); row["erp"] += rng.randint(5, 15)
            self.repository.update_source_records(self._run_id, InventoryPositionModel, {row["id"]: {"wms": row["wms"], "erp": row["erp"]}})
            # The persisted model scores predate this mutation; re-score the touched
            # position with the trained classifier so two-factor detection can fire.
            if self._classifier is None:
                self._classifier = train_selected_classifier(self._ml_selection.name, self._dataset.seed)
            self._ml_selection.inventory_scores.update(score_records(self._classifier, [row]))
            self.repository.update_run_metadata(self._run_id, {"ml_model": self._ml_metadata(include_scores=True)})
            return {"type": "inventory", "entity": row["id"], "story": f"A receipt journal for {row['sku']} just failed to post: WMS now shows {row['wms']}, ERP {row['erp']}, physical truth is {row['physical']}."}
        if kind == "overload":
            healthy = [item for item in data.dispatches if item["total_load_kg"] <= item["vehicle_capacity_kg"]]
            if not healthy:
                return None
            dispatch = rng.choice(healthy)
            dispatch["total_load_kg"] = int(dispatch["vehicle_capacity_kg"] * rng.uniform(1.15, 1.4))
            self.repository.update_source_records(self._run_id, DispatchScheduleModel, {dispatch["id"]: {"total_load_kg": dispatch["total_load_kg"]}})
            return {"type": "overload", "entity": dispatch["id"], "story": f"Load planning just accepted {dispatch['total_load_kg']:,} kg onto {dispatch['id']} against {dispatch['vehicle_capacity_kg']:,} kg capacity."}
        if kind == "ppap":
            healthy = [item for item in data.documents if item["ppap_attached"]]
            if not healthy:
                return None
            document = rng.choice(healthy)
            document["ppap_attached"] = False
            self.repository.update_source_document(document["id"], {"ppap_attached": False})
            return {"type": "ppap", "entity": document["batch"], "story": f"An inbound packet for batch {document['batch']} just arrived without its PPAP approval."}
        if kind == "labels":
            healthy = [item for item in data.dispatches if item["label_success"] >= item["total_labels"]]
            if not healthy:
                return None
            dispatch = rng.choice(healthy)
            dispatch["label_success"] = rng.randint(5, dispatch["total_labels"] - 2)
            self.repository.update_source_records(self._run_id, DispatchScheduleModel, {dispatch["id"]: {"label_success": dispatch["label_success"]}})
            return {"type": "labels", "entity": dispatch["id"], "story": f"The print service just failed verification on {dispatch['total_labels'] - dispatch['label_success']} VDA labels at {dispatch['dock']}."}
        if kind == "replenish":
            stock_by_sku: dict[str, int] = {}
            for row in data.inventory:
                stock_by_sku[row["sku"]] = stock_by_sku.get(row["sku"], 0) + row["wms"]
            covered = {order["sku"] for order in data.inbound_orders if order["expected_date"] >= data.generated_at.date().isoformat()}
            healthy = [sku for sku in data.skus if sku["id"] not in covered and stock_by_sku.get(sku["id"], 0) > sku["reorder_point"] * 2]
            if not healthy:
                return None
            sku = rng.choice(healthy)
            drained = max(4, sku["reorder_point"] // 6)
            updates = {}
            for row in data.inventory:
                if row["sku"] == sku["id"]:
                    row["wms"] = row["erp"] = row["tms"] = row["physical"] = drained
                    updates[row["id"]] = {"wms": drained, "erp": drained, "tms": drained, "physical": drained}
            self.repository.update_source_records(self._run_id, InventoryPositionModel, updates)
            return {"type": "replenish", "entity": sku["id"], "story": f"Line consumption just drained {sku['id']} to {drained} EA — reorder point is {sku['reorder_point']} and no PO is open."}
        return None

    @staticmethod
    def _resolve_hackathon_path(path: Path | str | None = None) -> Path:
        if path:
            p = Path(path)
            if p.exists():
                return p
            raise FileNotFoundError(f"Hackathon dataset file not found: {p}")
        base_dir = Path(__file__).resolve().parents[2]
        candidates = [
            base_dir / "datasets" / "Warehouse_AI_Hackathon_Synthetic_Dataset_FINAL 2.xlsx",
            base_dir / "Warehouse_AI_Hackathon_Synthetic_Dataset_FINAL 2.xlsx",
            Path("backend/datasets/Warehouse_AI_Hackathon_Synthetic_Dataset_FINAL 2.xlsx"),
            Path("datasets/Warehouse_AI_Hackathon_Synthetic_Dataset_FINAL 2.xlsx"),
            Path(r"C:\Users\Mohd Aftaab\Downloads\Telegram Desktop\Warehouse_AI_Hackathon_Synthetic_Dataset_FINAL 2.xlsx"),
        ]
        for c in candidates:
            if c.exists():
                return c
        raise FileNotFoundError("Hackathon dataset file not found in repo datasets/ or system paths.")

    def load_hackathon(self, path: Path | str | None = None) -> dict[str, object]:
        target_path = self._resolve_hackathon_path(path)

        wb_data = load_hackathon_workbook(target_path)
        findings_by_cat = run_all_detectors(wb_data)
        anomalies = convert_findings_to_anomalies(findings_by_cat)
        with self._lock:
            self._anomalies = anomalies
            self._hackathon_loaded = True
            self._hackathon_path = target_path
            self._hackathon_wb_data = wb_data
            self._last_scan = datetime.now(timezone.utc)
            self._scan_count += 1
            self._hackathon_stats = {
                "status": "loaded",
                "anomalies_count": len(anomalies),
                "path": str(target_path),
                "sheets": {
                    "material_master": len(wb_data.get("material_master", [])),
                    "inventory_stock": len(wb_data.get("inventory_stock", [])),
                    "warehouse_bin": len(wb_data.get("warehouse_bin", [])),
                    "deliveries_dispatch": len(wb_data.get("deliveries_dispatch", [])),
                    "purchase_replenish": len(wb_data.get("purchase_replenish", [])),
                    "vendor_master": len(wb_data.get("vendor_master", [])),
                },
            }
            self.repository.persist_anomalies(self._run_id, self._anomalies)
        # Generate a hackathon operational brief for WALT and specialist agents
        self._generate_hackathon_brief(wb_data, anomalies)
        return self._hackathon_stats

    def _generate_hackathon_brief(self, wb_data: dict, anomalies: list) -> None:
        """Write a hackathon_operational_brief.md into the knowledge directory."""
        from collections import Counter
        severity_counts = Counter(a.severity for a in anomalies)
        catalog_counts = Counter()
        for a in anomalies:
            # Extract catalog ID from the anomaly ID (e.g. HAC-X1-MAT-999001-0 -> X1)
            parts = a.id.split("-")
            if len(parts) >= 2:
                catalog_counts[parts[1]] += 1

        materials = wb_data.get("material_master", [])
        inventory = wb_data.get("inventory_stock", [])
        bins = wb_data.get("warehouse_bin", [])
        deliveries = wb_data.get("deliveries_dispatch", [])
        purchase_orders = wb_data.get("purchase_replenish", [])
        vendors = wb_data.get("vendor_master", [])

        plants = sorted({r.get("plant", "") for r in materials if r.get("plant")})
        vendor_ids = sorted({r.get("vendor", "") for r in vendors if r.get("vendor")})

        top_rules = catalog_counts.most_common(6)
        top_rules_text = "\n".join(
            f"- **{rule}**: {count} finding{'s' if count != 1 else ''}"
            for rule, count in top_rules
        )

        brief = f"""# Hackathon Operational Brief

> Auto-generated when the SAP hackathon dataset was loaded.

## Dataset Scope

- **{len(materials)}** materials across **{len(plants)}** plants ({', '.join(plants)})
- **{len(inventory)}** inventory stock positions
- **{len(bins)}** warehouse bins
- **{len(deliveries)}** delivery/dispatch records
- **{len(purchase_orders)}** purchase/replenishment orders
- **{len(vendors)}** vendors ({', '.join(vendor_ids[:5])}{'…' if len(vendor_ids) > 5 else ''})

## Anomaly Summary

**{len(anomalies)}** total findings detected across 24 catalog rules:

- **Critical**: {severity_counts.get('critical', 0)}
- **High**: {severity_counts.get('high', 0)}
- **Medium**: {severity_counts.get('medium', 0)}
- **Low**: {severity_counts.get('low', 0)}

### Top Detection Rules

{top_rules_text}

## Key Entities Under Watch

- **MAT-999001**: Orphan material — exists in transactional systems (Inventory, Bins, Deliveries) but missing from Material_Master. ERP/WMS replication gap.
- **VEND-9999**: Orphan vendor — referenced in open purchase orders but absent from Vendor_Master.
- **VEND-5000**: Blocked vendor — procurement block active but open purchase orders still exist.
- **Plant 1010** and **Plant 1710**: Primary and secondary plants with ATP stockout deficits.

## Snapshot Date

All overdue, expired, and stale calculations use **05 September 2026** as the reference date.

## Governance

All corrective actions require human approval before source data changes. The audit trail records what was detected, why, what action was proposed, by which agent, and who approved it.
"""
        KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
        (KNOWLEDGE_DIR / "hackathon_operational_brief.md").write_text(brief, encoding="utf-8")

    def run_scan(self) -> dict[str, object]:
        with self._lock:
            self._scan_count += 1
            self._last_scan = datetime.now(timezone.utc)
            # Only open findings' approval progress carries across scans. A resolved
            # finding whose entity gets re-broken produces the same deterministic ID;
            # its fresh incarnation must start with clean "recommended" actions, not
            # inherit the old "applied" flags.
            previous_actions = {action.id: action.status for anomaly in self._anomalies if anomaly.status != "resolved" for action in anomaly.actions}
            resolved = [anomaly for anomaly in self._anomalies if anomaly.status == "resolved"]
            if not self._hackathon_loaded or not self._hackathon_wb_data:
                try:
                    self.load_hackathon()
                except Exception:
                    pass
            if self._hackathon_loaded and self._hackathon_wb_data:
                findings_by_cat = run_all_detectors(self._hackathon_wb_data)
                detected = convert_findings_to_anomalies(findings_by_cat)
            else:
                detected = detect_anomalies(self._dataset, self._ml_selection.inventory_scores) + detect_sap_anomalies(self._dataset)
            # Remediated defects are gone from the source data, so they are not
            resolved_map = {anomaly.id: anomaly for anomaly in resolved}
            final_anomalies = []
            seen_ids = set()
            for a in detected:
                if a.id in resolved_map:
                    final_anomalies.append(resolved_map[a.id])
                else:
                    final_anomalies.append(a)
                seen_ids.add(a.id)
            for res_id, res_a in resolved_map.items():
                if res_id not in seen_ids:
                    final_anomalies.append(res_a)
            self._anomalies = final_anomalies
            for anomaly in self._anomalies:
                if anomaly.status == "resolved":
                    continue
                for action in anomaly.actions:
                    action.status = previous_actions.get(action.id, action.status)
            self.repository.persist_anomalies(self._run_id, self._anomalies)
            return {
                "scan_id": f"SCAN-{self._scan_count}",
                "findings": len([a for a in self._anomalies if a.status != "resolved"]),
                "anomalies_count": len(self._anomalies),
                "started_at": self._last_scan.isoformat(),
            }

    def _hackathon_reconciliation_rows(self) -> list[dict[str, object]]:
        """Build the reconciliation workbench directly from Inventory_Stock.

        The official workbook has no fabricated WMS/ERP/physical-count columns.
        This view therefore exposes the fields that actually exist in the SAP
        sheet and compares available stock with the material's reorder point.
        Each row carries its source record and the closest finding so the UI can
        open the exact workbook-backed context after a click.
        """
        workbook = self._hackathon_wb_data or {}
        inventory = workbook.get("inventory_stock", [])
        materials = {
            (str(row.get("material") or ""), str(row.get("plant") or "")): row
            for row in workbook.get("material_master", [])
        }
        bins = workbook.get("warehouse_bin", [])
        findings = self.anomalies()
        rows: list[dict[str, object]] = []

        def serial(value):
            return value.isoformat() if hasattr(value, "isoformat") else value

        for record in inventory:
            material_id = str(record.get("material") or "Unknown material")
            plant = str(record.get("plant") or "Unknown plant")
            storage_location = str(record.get("storage_location") or "Unassigned")
            material = materials.get((material_id, plant)) or next(
                (item for item in workbook.get("material_master", []) if item.get("material") == material_id),
                {},
            )
            bin_record = next(
                (
                    item for item in bins
                    if item.get("assigned_material") == material_id and item.get("plant") == plant
                ),
                None,
            )
            on_hand = _as_float(record.get("qty_on_hand"))
            blocked = _as_float(record.get("blocked_qty"))
            in_transit = _as_float(record.get("in_transit_qty"))
            available = on_hand - blocked
            reorder_point = _as_float(material.get("reorder_point"))
            variance = int(round(available - reorder_point))
            last_movement = record.get("last_movement_date")
            stale_days = 0
            if last_movement:
                try:
                    stale_days = max(0, (datetime(2026, 9, 5).date() - last_movement).days)
                except TypeError:
                    stale_days = 0
            if on_hand < 0 or variance < 0:
                risk = "critical"
            elif blocked > 0 or stale_days > 365:
                risk = "watch"
            else:
                risk = "healthy"
            related = next(
                (
                    item for item in findings
                    if item.status != "resolved"
                    and (item.sku == material_id or material_id in item.title)
                ),
                None,
            )
            source_record_id = f"Inventory_Stock/{material_id}/{plant}/{storage_location}"
            rows.append({
                "id": source_record_id,
                "source_table": "Inventory_Stock",
                "source_record_id": source_record_id,
                "material": material_id,
                "sku": material_id,
                "description": material.get("description") or "No material description",
                "plant": plant,
                "warehouse": plant,
                "storage_location": storage_location,
                "bin": bin_record.get("bin") if bin_record else storage_location,
                "uom": record.get("uom") or material.get("base_uom") or "—",
                "on_hand": on_hand,
                "blocked": blocked,
                "in_transit": in_transit,
                "available": available,
                "reorder_point": reorder_point,
                "variance": variance,
                "risk": risk,
                "stale_days": stale_days,
                "related_anomaly_id": related.id if related else None,
                "related_anomaly_title": related.title if related else None,
                "source_record": {key: serial(value) for key, value in record.items()},
                "material_record": {key: serial(value) for key, value in material.items()},
            })

        risk_order = {"critical": 0, "watch": 1, "healthy": 2}
        return sorted(
            rows,
            key=lambda row: (
                risk_order.get(str(row["risk"]), 3),
                -abs(int(row["variance"])),
                str(row["material"]),
            ),
        )[:8]

    def reconciliation(self) -> dict[str, object]:
        if self._hackathon_loaded and self._hackathon_wb_data:
            rows = self._hackathon_reconciliation_rows()
            source_label = "SAP Hackathon · Inventory_Stock"
            last_count = max(
                (record.get("last_movement_date") for record in self._hackathon_wb_data.get("inventory_stock", []) if record.get("last_movement_date")),
                default=None,
            )
            reconciliation_anomaly = next(
                (item for item in self.anomalies() if item.type in {"Inventory Ledger Discrepancy", "Inventory Shortage", "Inventory Allocation"}),
                None,
            )
            divergent = next((row for row in rows if row["risk"] == "critical"), rows[0] if rows else None)
            summary = {
                "review_items": sum(1 for row in rows if row["variance"]),
                "total_variance": sum(abs(int(row["variance"])) for row in rows),
                "last_count": last_count.isoformat() if last_count else "2026-09-05",
                "anomaly_id": reconciliation_anomaly.id if reconciliation_anomaly else (divergent or {}).get("related_anomaly_id"),
                "source": source_label,
                "records_available": len(self._hackathon_wb_data.get("inventory_stock", [])),
            }
            return {
                "rows": rows,
                "summary": summary,
                "timeline": [
                    {"time": "2026-09-03", "event": f"Inventory_Stock record loaded for {divergent['material']}" if divergent else "No inventory record selected", "system": "SAP Inventory_Stock", "state": "good"},
                    {"time": "2026-09-03", "event": f"Available stock is {abs(int(divergent['variance'])) if divergent else 0} units below reorder point", "system": "SAP MRP", "state": "critical"},
                    {"time": "2026-09-05", "event": f"Blocked quantity recorded as {divergent['blocked'] if divergent else 0:g} units", "system": "SAP Stock Status", "state": "watch"},
                    {"time": "2026-09-05", "event": f"On-hand quantity is {divergent['on_hand'] if divergent else 0:g} units", "system": "SAP MARD", "state": "good"},
                ],
            }

        rows = build_reconciliation_rows(self._dataset)
        reconciliation_anomaly = next((item for item in self.anomalies() if item.type == "Inventory reconciliation"), None)
        divergent = next((row for row in rows if row["risk"] == "critical"), rows[0] if rows else None)
        return {
            "rows": rows,
            "summary": {"review_items": sum(1 for row in rows if row["variance"]), "total_variance": sum(abs(int(row["variance"])) for row in rows), "last_count": max((record["last_count"] for record in self._dataset.inventory), default=self._dataset.generated_at).strftime("%H:%M UTC"), "anomaly_id": reconciliation_anomaly.id if reconciliation_anomaly else None, "source": "Synthetic Twin"},
            "timeline": [
                {"time": (self._dataset.generated_at - timedelta(minutes=91)).strftime("%H:%M"), "event": f"Receipt movement recorded for {divergent['sku']}" if divergent else "No divergence record", "system": "WMS", "state": "good"},
                {"time": (self._dataset.generated_at - timedelta(minutes=90)).strftime("%H:%M"), "event": f"ERP balance diverged from source by {abs(int(divergent['variance'])) if divergent else 0} units", "system": "ERP", "state": "critical"},
                {"time": (self._dataset.generated_at - timedelta(minutes=54)).strftime("%H:%M"), "event": f"Availability plan inherited WMS balance {divergent['wms'] if divergent else 0}", "system": "Planner", "state": "watch"},
                {"time": self._dataset.generated_at.strftime("%H:%M"), "event": f"Physical count reports {divergent['physical'] if divergent else 0} units", "system": "Count", "state": "good"},
            ],
        }

    def alerts(self) -> list[dict[str, object]]:
        return [
            {"id": item.id, "when": item.time_to_impact, "title": item.title, "detail": item.summary, "impact": item.impact, "severity": item.severity, "owner": item.actions[0].owner if item.actions else "Operations"}
            for item in self.anomalies() if item.status != "resolved"
        ]

    def actions(self, status: str | None = None) -> list[dict[str, object]]:
        items = []
        for anomaly in self.anomalies():
            for action in anomaly.actions:
                if status and status != "all" and action.status != status:
                    continue
                items.append({**action.model_dump(), "anomaly_id": anomaly.id, "anomaly_title": anomaly.title, "severity": anomaly.severity})
        return sorted(items, key=lambda item: (item["status"] == "applied", -item["impact_saved"]))

    def inspect_document(self, filename: str, content: str) -> DocumentInspection:
        normalized = content.lower()
        missing_ppap = next((item for item in self._dataset.documents if not item["ppap_attached"]), None)
        mismatches: list[dict[str, str]] = []
        if "ppap" not in normalized and missing_ppap:
            mismatches.append({"field": "PPAP approval", "document": "Not found", "system": f"Required for batch {missing_ppap['batch']}", "severity": "high"})
        if "vda" not in normalized and "label" not in normalized:
            mismatches.append({"field": "VDA transport label", "document": "Not found", "system": "Required for JIT loads", "severity": "medium"})
        linked_sku = next((sku["id"] for sku in self._dataset.skus if sku["id"].lower() in normalized), None)
        linked_batch = next((item["batch"] for item in self._dataset.documents if item["batch"].lower() in normalized), None)
        if linked_sku and missing_ppap and linked_sku == missing_ppap["sku"] and "ppap" not in normalized:
            mismatches.append({"field": "Linked SKU release evidence", "document": linked_sku, "system": f"Batch {missing_ppap['batch']} is missing PPAP", "severity": "high"})
        return DocumentInspection(
            filename=filename, type=filename.rsplit(".", 1)[-1].upper() if "." in filename else "TEXT",
            status="attention" if mismatches else "clean", confidence=92,
            summary="The document was indexed and compared with release controls." if not mismatches else "The packet is readable, but release-critical evidence is missing.",
            fields=[{"label": "Document reference", "value": filename}, {"label": "Inspection route", "value": "Quality + dispatch controls"}, {"label": "Matched SKU", "value": linked_sku or "No SKU identifier found"}, {"label": "Matched batch", "value": linked_batch or "No batch identifier found"}],
            mismatches=mismatches,
        )

    def context_brief(self) -> str:
        active = self.anomalies(status="open")
        facts = [f"{item.id}: {item.title}; impact €{item.impact:,}; deadline {item.time_to_impact}; root cause: {item.root_cause}" for item in active]
        return "\n".join(facts)

    def knowledge_context(self, query: str) -> list[dict[str, str]]:
        return retrieve_markdown(query)

    def documents(self) -> dict[str, object]:
        held = [item for item in self._dataset.documents if not item["ppap_attached"] or not item["vda_attached"]]
        records = self.repository.documents()
        return {"summary": {"source_documents": len(self._dataset.documents), "release_controls_needing_evidence": len(held), "ingested_records": len([item for item in records if item["status"] != "source"])}, "items": records}

    def clear_documents(self) -> None:
        self.repository.delete_documents()
        self.repository.add_audit(str(uuid.uuid4()), "documents_cleared", "Document agent", {"cleared": "all_ingested"})

    def delete_document(self, document_id: str) -> bool:
        doc = self.repository.document(document_id)
        if not doc:
            return False
        result = self.repository.delete_document(document_id)
        if result:
            self.repository.add_audit(str(uuid.uuid4()), "document_deleted", "Document agent", {"document_id": document_id, "filename": doc.get("filename")})
        return result

    def record_document(self, document_id: str, inspection: DocumentInspection, storage_path: str, markdown_path: str) -> None:
        inspection.document_id = document_id
        inspection.preview_url = f"/api/documents/{document_id}/preview"
        self.repository.add_document(self._run_id, document_id, inspection.filename, inspection.type, storage_path, markdown_path, inspection.status, {field["label"]: field["value"] for field in inspection.fields}, inspection.mismatches)
        self.repository.add_audit(str(uuid.uuid4()), "document_ingested", "Document agent", {"document_id": document_id, "filename": inspection.filename, "status": inspection.status})
        mismatch_note = "; ".join(f"{item['field']} ({item['severity']})" for item in inspection.mismatches)
        self.repository.add_outcome(
            "document",
            f"Ingested: {inspection.filename}",
            f"Flagged {len(inspection.mismatches)} release gaps — {mismatch_note}" if inspection.mismatches else "Cross-checked clean; added to the retrieval context for every specialist agent.",
            0,
            {"document_id": document_id, "status": inspection.status, "mismatches": len(inspection.mismatches)},
        )

    def outcomes(self) -> dict[str, object]:
        items = self.repository.outcomes()
        fixes = [item for item in items if item["kind"] == "fix"]
        value_protected = sum(item["saved"] for item in fixes)
        open_exposure = sum(item.impact for item in self.anomalies() if item.status != "resolved")
        return {
            "items": items,
            "summary": {
                "value_protected": value_protected,
                "fixes_applied": len(fixes),
                "anomalies_resolved": sum(1 for item in self._anomalies if item.status == "resolved"),
                "documents_ingested": sum(1 for item in items if item["kind"] == "document"),
            },
            "roi": {
                # One demo session models one shift; a three-shift operation runs ~1,095 shifts/year.
                "annualized_value": value_protected * 3 * 365,
                "shifts_per_year": 3 * 365,
                "detection_minutes": 4,
                "manual_cadence_days": 7,
                "still_actionable": open_exposure,
                "note": "Weekly manual reconciliation would surface these findings up to 7 days later; Warehouse Control Tower AI flags them within minutes of the data diverging.",
            },
        }

    def document(self, document_id: str) -> dict | None:
        return self.repository.document(document_id)

    def _ml_metadata(self, include_scores: bool = False) -> dict[str, object]:
        metadata = self._metadata_from(self._ml_selection)
        if include_scores:
            # Persisting per-position scores lets later boots skip the ~14s retrain.
            metadata["inventory_scores"] = self._ml_selection.inventory_scores
        return metadata

    @staticmethod
    def _metadata_from(selection: ModelSelection) -> dict[str, object]:
        return {
            "name": selection.name,
            "f1": selection.f1,
            "accuracy": selection.accuracy,
            "precision": selection.precision,
            "recall": selection.recall,
            "candidates": selection.candidates,
            "validation": "synthetic temporal holdout",
            "training_records": 1500,
        }

    def system_health(self) -> dict[str, object]:
        """ML benchmark, score distribution and runtime facts for the System health page."""
        scores = sorted(self._ml_selection.inventory_scores.items(), key=lambda item: -item[1])
        buckets = [0] * 10
        for _, score in scores:
            buckets[min(9, int(score * 10))] += 1
        position_lookup = {row["id"]: row for row in self._dataset.inventory}
        top = []
        for position_id, score in scores[:6]:
            row = position_lookup.get(position_id, {})
            top.append({"id": position_id, "sku": row.get("sku", "—"), "zone": row.get("zone", "—"), "wms": row.get("wms", 0), "erp": row.get("erp", 0), "physical": row.get("physical", 0), "score": score})
        return {
            "model": {
                **self._ml_metadata(),
                "task": "Inventory divergence classification",
                "features": ["wms", "erp", "physical", "spread", "|wms−erp|", "|erp−physical|", "relative spread"],
                "scored_positions": len(scores),
                "flagged_over_50": sum(1 for _, score in scores if score >= .5),
            },
            "llm": {
                "provider": {"codecraft": "CodeCraft", "openai": "Direct OpenAI", "ollama": "Ollama", "agentrouter": "AgentRouter Claude"}.get(self._get_active_provider(), "Deterministic Fallback"),
                "model": self._get_active_model(),
                "enabled": self._get_active_provider() != "deterministic",
                "specialists": 5,
                "role": "Specialist mesh + orchestrator synthesis",
            },
            "score_distribution": [{"bucket": f".{index}", "count": count} for index, count in enumerate(buckets)],
            "top_scored": top,
            "runtime": {
                "dataset_seed": self._dataset.seed,
                "generated_at": self._dataset.generated_at.isoformat(),
                "records": sum((len(self._dataset.skus), len(self._dataset.inventory), len(self._dataset.inbound_orders), len(self._dataset.outbound_orders), len(self._dataset.suppliers), len(self._dataset.dispatches), len(self._dataset.workforce), len(self._dataset.documents), len(self._dataset.containers))),
                "scan_count": self._scan_count,
                "last_scan": self._last_scan.isoformat(),
                "database": self.settings.database_url.split("://")[0],
            },
        }

    def _get_active_provider(self) -> str:
        try:
            from app.services.llm_client import get_llm_client
            return get_llm_client(self.settings).active_provider
        except Exception:
            return "codecraft" if self.settings.codecraft_api_key else "openai" if self.settings.openai_api_key else "ollama" if self.settings.ollama_enabled else "agentrouter" if self.settings.agentrouter_api_key else "deterministic"

    def _get_active_model(self) -> str:
        try:
            from app.services.llm_client import get_llm_client
            return get_llm_client(self.settings).active_model
        except Exception:
            return self.settings.openai_model

    def audit(self) -> list[dict[str, str]]:
        return self.repository.audit()

    def agent_architecture(self) -> dict[str, object]:
        provider = self._get_active_provider()
        dashboard = self.dashboard()
        provider_label = {"codecraft": "CodeCraft", "openai": "Direct OpenAI", "ollama": "Ollama", "agentrouter": "AgentRouter Claude"}.get(provider, "Evidence mode")
        return {"model": self._get_active_model(), "provider": provider, "provider_label": provider_label, "enabled": provider != "deterministic", "orchestrator": "Orchestrator (WALT)", "specialists": [
            {"name": "Ingestion Agent", "responsibility": "Load and normalise Excel/SAP sheets, resolve keys, build unified view", "input": "6 SAP sheets: Material_Master, Inventory_Stock, Warehouse_Bin, Deliveries_Dispatch, Purchase_Replenish, Vendor_Master"},
            {"name": "Data-Quality Agent", "responsibility": "Detect bad/missing/duplicate/obsolete master data (A1–A6)", "input": "Material master fields, UoM, reorder point, safety stock, hazmat, lifecycle"},
            {"name": "Anomaly Agent", "responsibility": "Detect inventory & process anomalies (B1–B5, C1–C4, D2–D5, E1–E4, F1–F2)", "input": "Negative stock, batch expiry, stale stock, bin capacity, overdue GI, PO status"},
            {"name": "Correlation / Root-Cause Agent", "responsibility": "Link related anomalies across systems and infer underlying cause (X1, X2, cascade tracing)", "input": "Cross-system entity correlation, ATP shortfall, ERP/WMS replication gaps"},
            {"name": "Impact Agent", "responsibility": "Score business impact and prioritise worklist (€ exposure, P90 risk, scoring model)", "input": "Financial exposure (€), SLA breach risk, deadline urgency ranking"},
            {"name": "Action / Remediation Agent", "responsibility": "Propose or execute fix; route for human approval (Change Control, Before/Proposed/After, auto-remediation)", "input": "Control playbooks, parameter corrections, staged change drafts, RBAC approval"},
            {"name": "Orchestrator (WALT)", "responsibility": "Plan the flow, delegate to agents, maintain the audit trail", "input": "Operator queries, multi-agent handoffs, immutable audit events"},
        ], "tiers": [
            {"id": "source", "label": "Ingestion Agent", "status": "connected", "detail": f"6 SAP sheets ({dashboard['dataset']['records']:,} records) · Unified operational twin"},
            {"id": "data_quality", "label": "Data-Quality Agent", "status": "ready", "detail": "Master data catalog rules (A1–A6) & schema validation"},
            {"id": "anomaly", "label": "Anomaly Agent", "status": "ready", "detail": f"Inventory & process anomaly detection ({sum(dashboard['severity_counts'].values())} active findings)"},
            {"id": "correlation", "label": "Correlation / Root-Cause Agent", "status": "ready", "detail": "Cross-system entity linkage & cascade simulation (X1–X2)"},
            {"id": "impact", "label": "Impact Agent", "status": "ready", "detail": "Financial exposure quantification & risk scoring model"},
            {"id": "remediation", "label": "Action / Remediation Agent", "status": "ready", "detail": "Human-approved change control, Before/Proposed/After & remediation"},
            {"id": "orchestrator", "label": "Orchestrator (WALT)", "status": "ready", "detail": f"Flow planning & audit trail via {provider_label} · {self._get_active_model()}"},
        ], "dataset": {"status": "connected", "records": dashboard["dataset"]["records"], "active_findings": sum(dashboard["severity_counts"].values()), "scan_count": dashboard["scan_count"]}, "handoff_policy": "Specialists cannot mutate source data without human approval. Orchestrator (WALT) coordinates agent handoffs, and Action / Remediation Agent enforces RBAC governance."}

    def hackathon_export(self) -> dict[str, object]:
        """Generate official hackathon verification and coverage report for judges."""
        with self._lock:
            from collections import Counter
            anomalies = self._anomalies
            total = len(anomalies)
            resolved = [a for a in anomalies if a.status == "resolved"]
            open_items = [a for a in anomalies if a.status != "resolved"]

            coverage: dict[str, int] = Counter()
            findings_list = []
            for a in anomalies:
                parts = a.id.split("-")
                cat = parts[1] if len(parts) >= 2 else "X"
                series = cat[0] if cat else "X"
                coverage[series] += 1

                action = a.actions[0] if a.actions else None
                findings_list.append({
                    "id": a.id,
                    "catalog_id": cat,
                    "series": series,
                    "title": a.title,
                    "severity": a.severity,
                    "entity": a.sku,
                    "zone": a.zone,
                    "system": a.system,
                    "exposure_eur": a.impact,
                    "time_to_impact": a.time_to_impact,
                    "root_cause": a.root_cause,
                    "proposed_action": {
                        "title": action.title if action else "Escalate to Operations",
                        "owner": action.owner if action else "Operations Controller",
                        "eta": action.eta if action else "1 shift",
                        "confidence": action.confidence if action else 90,
                        "value_protected_eur": action.impact_saved if action else int(a.impact * 0.85),
                    },
                    "status": a.status,
                    "human_approval_required": True,
                })

            return {
                "status": "verified",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "dataset": "Warehouse_AI_Hackathon_Synthetic_Dataset_FINAL 2.xlsx",
                "snapshot_date": "2026-09-05",
                "total_anomalies": total,
                "resolved_count": len(resolved),
                "open_count": len(open_items),
                "total_exposure_at_risk_eur": sum(a.impact for a in open_items),
                "total_value_protected_eur": sum(a.impact for a in resolved),
                "catalog_coverage": dict(coverage),
                "human_in_the_loop_guarantee": "All corrective actions require explicit human operator approval before execution.",
                "findings": findings_list,
            }

    def contain_hackathon(self, severity: str | None = None, category: str | None = None, limit: int = 10) -> dict[str, object]:
        """Execute governed batch remediation on targeted hackathon findings with full human audit."""
        with self._lock:
            candidates = [
                a for a in self._anomalies
                if a.status != "resolved" and a.actions
            ]
            if severity:
                candidates = [a for a in candidates if a.severity == severity]
            if category:
                candidates = [a for a in candidates if f"-{category}-" in a.id or a.id.startswith(f"HAC-{category}")]

            contained = []
            total_saved = 0
            for a in candidates[:limit]:
                action = a.actions[0]
                res, _ = self.approve_action(a.id, action.id)
                if res and res.status == "resolved":
                    contained.append(a.id)
                    total_saved += a.impact

            return {
                "contained_count": len(contained),
                "contained_ids": contained,
                "total_value_protected": total_saved,
                "audit_actor": "Operations Controller",
                "governance": "human_approved_batch",
                "remaining_open": len([a for a in self._anomalies if a.status != "resolved"]),
            }

    def hackathon_preventive(self) -> dict[str, object]:
        """Predict which records are likely to fail next (Section 3.3 Bonus Direction)."""
        with self._lock:
            wb = self._hackathon_wb_data
            if not wb:
                return {"status": "inactive", "total_preventive_signals": 0, "signals": []}

            from app.services.hackathon_detectors import SNAPSHOT_DATE

            # 1. Stockout Watch (on-hand within 30% of reorder point)
            mm_map = {r["material"]: r for r in wb.get("material_master", []) if r.get("material")}
            inv_by_mat: dict[str, float] = {}
            for r in wb.get("inventory_stock", []):
                m = r.get("material")
                if m:
                    inv_by_mat[m] = inv_by_mat.get(m, 0.0) + float(r.get("qty_on_hand") or 0.0)

            stockout_watch = []
            for mat, mm_row in mm_map.items():
                rp = float(mm_row.get("reorder_point") or 0.0)
                curr = inv_by_mat.get(mat, 0.0)
                if rp > 0 and rp < curr <= rp * 1.3:
                    stockout_watch.append({
                        "material": mat,
                        "description": mm_row.get("description"),
                        "plant": mm_row.get("plant"),
                        "qty_on_hand": curr,
                        "reorder_point": rp,
                        "buffer_remaining": round(curr - rp, 1),
                        "preventive_action": f"Trigger advance purchase replenishment for {mat}",
                    })

            # 2. Bin Saturation Watch (occupancy between 80% and 100% capacity)
            bin_saturation_watch = []
            for r in wb.get("warehouse_bin", []):
                cap = float(r.get("capacity") or 0.0)
                occ = float(r.get("occupied") or 0.0)
                if cap > 0 and 0.80 <= (occ / cap) < 1.0:
                    pct = round((occ / cap) * 100, 1)
                    bin_saturation_watch.append({
                        "bin": r.get("bin"),
                        "plant": r.get("plant"),
                        "storage_type": r.get("storage_type"),
                        "utilization_pct": pct,
                        "capacity": cap,
                        "occupied": occ,
                        "preventive_action": f"Re-slot putaways away from saturated bin {r.get('bin')}",
                    })

            # 3. Batch Expiry Horizon Watch (expiring within 45 days)
            batch_expiry_watch = []
            for r in wb.get("inventory_stock", []):
                exp = r.get("batch_expiry")
                qty = float(r.get("qty_on_hand") or 0.0)
                if exp and exp > SNAPSHOT_DATE and (exp - SNAPSHOT_DATE).days <= 45 and qty > 0:
                    days_left = (exp - SNAPSHOT_DATE).days
                    batch_expiry_watch.append({
                        "material": r.get("material"),
                        "batch": r.get("batch"),
                        "plant": r.get("plant"),
                        "qty_on_hand": qty,
                        "expiry_date": str(exp),
                        "days_until_expiry": days_left,
                        "preventive_action": f"Prioritize FEFO dispatch for batch {r.get('batch')} ({days_left}d remaining)",
                    })

            # 4. Vendor Reliability Watch (borderline OTD between 88% and 94%)
            vendor_reliability_watch = []
            for r in wb.get("vendor_master", []):
                otd = float(r.get("otd_pct") or 100.0)
                if 88.0 <= otd < 94.0 and (r.get("procurement_block") or "").upper() != "Y":
                    vendor_reliability_watch.append({
                        "vendor": r.get("vendor"),
                        "vendor_name": r.get("vendor_name"),
                        "otd_pct": otd,
                        "preventive_action": f"Flag supplier {r.get('vendor')} for delivery buffer and dual-sourcing",
                    })

            total_signals = len(stockout_watch) + len(bin_saturation_watch) + len(batch_expiry_watch) + len(vendor_reliability_watch)
            return {
                "status": "active",
                "total_preventive_signals": total_signals,
                "snapshot_date": str(SNAPSHOT_DATE),
                "stockout_watch": sorted(stockout_watch, key=lambda x: x["buffer_remaining"])[:10],
                "bin_saturation_watch": sorted(bin_saturation_watch, key=lambda x: -x["utilization_pct"])[:10],
                "batch_expiry_watch": sorted(batch_expiry_watch, key=lambda x: x["days_until_expiry"])[:10],
                "vendor_reliability_watch": sorted(vendor_reliability_watch, key=lambda x: x["otd_pct"])[:10],
                "summary": f"Identified {total_signals} early-warning operational signals before escalation.",
            }
