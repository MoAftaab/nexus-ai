"""SQLAlchemy persistence for the NexusAI operational twin.

SQLite keeps local onboarding zero-config; Docker uses PostgreSQL. Domain services only
depend on Repository so the generation, agents, and API work against either backend.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, create_engine, delete, func, inspect, select, text, update
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import JSON

from app.config import Settings


class Base(DeclarativeBase):
    pass


class DatasetRunModel(Base):
    __tablename__ = "dataset_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    seed: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    site_id: Mapped[str | None] = mapped_column(String(32), nullable=True, default="wolfsburg", index=True)


class PayloadRecord(Base):
    """Base for source-system records; payload stays flexible as the demo schema evolves."""
    __abstract__ = True
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("dataset_runs.id", ondelete="CASCADE"), index=True)
    source_key: Mapped[str] = mapped_column(String(96), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class MasterSkuModel(PayloadRecord): __tablename__ = "master_skus"
class SupplierModel(PayloadRecord): __tablename__ = "suppliers"
class InventoryPositionModel(PayloadRecord): __tablename__ = "inventory_positions"
class InboundOrderModel(PayloadRecord): __tablename__ = "inbound_orders"
class OutboundOrderModel(PayloadRecord): __tablename__ = "outbound_orders"
class DispatchScheduleModel(PayloadRecord): __tablename__ = "dispatch_schedule"
class WorkforceLogModel(PayloadRecord): __tablename__ = "workforce_logs"
class ContainerModel(PayloadRecord): __tablename__ = "containers"


class DocumentModel(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("dataset_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    document_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    filename: Mapped[str] = mapped_column(String(255))
    document_type: Mapped[str] = mapped_column(String(40))
    storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    markdown_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="indexed")
    extracted_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    cross_check_results: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    site_id: Mapped[str | None] = mapped_column(String(32), nullable=True, default="wolfsburg", index=True)


class AnomalyModel(Base):
    __tablename__ = "anomalies"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("dataset_runs.id", ondelete="CASCADE"), index=True)
    anomaly_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    severity: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    impact: Mapped[int] = mapped_column(Integer, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    site_id: Mapped[str | None] = mapped_column(String(32), nullable=True, default="wolfsburg", index=True)


class FixActionModel(Base):
    __tablename__ = "fix_actions"
    id: Mapped[int] = mapped_column(primary_key=True)
    anomaly_id: Mapped[str] = mapped_column(String(64), index=True)
    action_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="recommended", index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    site_id: Mapped[str | None] = mapped_column(String(32), nullable=True, default="wolfsburg", index=True)


class AuditLogModel(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    actor: Mapped[str] = mapped_column(String(128))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)


class OutcomeModel(Base):
    """Value ledger: every applied control and ingested document with its measurable effect."""
    __tablename__ = "outcomes"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), index=True)  # "fix" | "document"
    title: Mapped[str] = mapped_column(String(255))
    detail: Mapped[str] = mapped_column(String(500), default="")
    saved: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)


class SiteModel(Base):
    __tablename__ = "sites"
    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    plant_code: Mapped[str] = mapped_column(String(16))
    timezone: Mapped[str] = mapped_column(String(64))


class UserModel(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    role: Mapped[str] = mapped_column(String(48), index=True)
    site_scopes: Mapped[list[str]] = mapped_column(JSON, default=list)
    password_hash: Mapped[str] = mapped_column(String(256))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    manager_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    escalation_owner_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class SessionModel(Base):
    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_token: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ApprovalPolicyModel(Base):
    __tablename__ = "approval_policies"
    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    rules: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    created_by: Mapped[str] = mapped_column(String(64))


class ChangeRequestModel(Base):
    __tablename__ = "change_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    anomaly_id: Mapped[str] = mapped_column(String(64), index=True)
    action_id: Mapped[str] = mapped_column(String(64), index=True)
    site_id: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    severity: Mapped[str] = mapped_column(String(16))
    impact_euros: Mapped[int] = mapped_column(Integer)
    is_regulated: Mapped[bool] = mapped_column(Boolean, default=False)
    requested_by: Mapped[str] = mapped_column(String(64))
    policy_version: Mapped[int] = mapped_column(Integer)
    before_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    proposed_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    after_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    source_hash: Mapped[str] = mapped_column(String(128))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ApprovalStepModel(Base):
    __tablename__ = "approval_steps"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    stage: Mapped[str] = mapped_column(String(48))
    required_role: Mapped[str] = mapped_column(String(48))
    assigned_to: Mapped[str | None] = mapped_column(String(64), nullable=True)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    assignment_reason: Mapped[str | None] = mapped_column(String(160), nullable=True)
    site_id: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(24), default="waiting")
    sla_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decision: Mapped[str | None] = mapped_column(String(24), nullable=True)
    comment: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)


class DetailRequestModel(Base):
    __tablename__ = "workflow_detail_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    detail_request_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    approval_step_id: Mapped[int] = mapped_column(Integer, index=True)
    requested_by: Mapped[str] = mapped_column(String(64))
    requested_from: Mapped[str] = mapped_column(String(64), index=True)
    requested_fields: Mapped[list[str]] = mapped_column(JSON, default=list)
    question: Mapped[str] = mapped_column(String(1000), default="")
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    response: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    evidence_attachments: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WorkflowActionModel(Base):
    """A confirmable, idempotent workflow preview or automatic SLA action."""
    __tablename__ = "workflow_actions"
    id: Mapped[int] = mapped_column(primary_key=True)
    action_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    action_type: Mapped[str] = mapped_column(String(48), index=True)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    approval_step_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    actor_user_id: Mapped[str] = mapped_column(String(64), index=True)
    recipient_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="previewed", index=True)
    reason: Mapped[str] = mapped_column(String(1000), default="")
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NotificationModel(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    notification_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    site_id: Mapped[str] = mapped_column(String(32), index=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    notification_type: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(String(500))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)


class Repository:
    def __init__(self, settings: Settings):
        connect_args = {"check_same_thread": False, "timeout": 30.0} if settings.database_url.startswith("sqlite") else {}
        engine_options = {"poolclass": StaticPool} if settings.database_url in {"sqlite://", "sqlite:///:memory:"} else {}
        self.engine = create_engine(settings.database_url, future=True, pool_pre_ping=True, connect_args=connect_args, **engine_options)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False, class_=Session)

    def initialize(self) -> None:
        if self.engine.url.drivername.startswith("sqlite"):
            with self.engine.begin() as conn:
                conn.execute(text("PRAGMA journal_mode=WAL;"))
                conn.execute(text("PRAGMA busy_timeout=30000;"))
        Base.metadata.create_all(self.engine)
        # Existing demo databases predate the governance columns. They are
        # additive nullable fields, so add them in place without touching any
        # payload records or rebuilding a table.
        inspector = inspect(self.engine)
        for table in ("dataset_runs", "documents", "anomalies", "fix_actions"):
            if table not in inspector.get_table_names():
                continue
            columns = {column["name"] for column in inspector.get_columns(table)}
            if "site_id" not in columns:
                with self.engine.begin() as connection:
                    connection.execute(text(f'ALTER TABLE "{table}" ADD COLUMN site_id VARCHAR(32)'))
        additive_columns = {
            "users": {
                "manager_user_id": "VARCHAR(64)",
                "escalation_owner_user_id": "VARCHAR(64)",
            },
            "approval_steps": {
                "assigned_at": "DATETIME",
                "assignment_reason": "VARCHAR(160)",
            },
        }
        inspector = inspect(self.engine)
        for table, expected in additive_columns.items():
            if table not in inspector.get_table_names():
                continue
            existing = {column["name"] for column in inspector.get_columns(table)}
            with self.engine.begin() as connection:
                for column, sql_type in expected.items():
                    if column not in existing:
                        connection.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {sql_type}'))

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self.sessions()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def latest_run(self) -> DatasetRunModel | None:
        with self.session() as session:
            return session.scalar(select(DatasetRunModel).where(DatasetRunModel.is_active.is_(True)).order_by(DatasetRunModel.id.desc()))

    def save_run(self, data, anomalies, ml_metadata: dict[str, Any]) -> int:
        source_groups = (
            (MasterSkuModel, data.skus, "id"), (SupplierModel, data.suppliers, "id"),
            (InventoryPositionModel, data.inventory, "sku"), (InboundOrderModel, getattr(data, "inbound_orders", []), "id"),
            (OutboundOrderModel, getattr(data, "outbound_orders", []), "id"),
            (DispatchScheduleModel, data.dispatches, "id"), (WorkforceLogModel, getattr(data, "workforce", []), "id"),
            (ContainerModel, data.containers, "id"),
        )
        with self.session() as session:
            # Dataset runs use deterministic IDs to keep the synthetic evidence
            # reproducible. Clear only the previous generated twin before replacing
            # it, while preserving uploaded records as detached audit artifacts.
            previous_runs = session.scalars(select(DatasetRunModel.id).where(DatasetRunModel.is_active.is_(True))).all()
            for previous_run_id in previous_runs:
                previous_anomalies = session.scalars(select(AnomalyModel.anomaly_id).where(AnomalyModel.run_id == previous_run_id)).all()
                if previous_anomalies:
                    session.execute(delete(FixActionModel).where(FixActionModel.anomaly_id.in_(previous_anomalies)))
                for model, _, _ in source_groups:
                    session.execute(delete(model).where(model.run_id == previous_run_id))
                session.execute(delete(AnomalyModel).where(AnomalyModel.run_id == previous_run_id))
                session.execute(delete(DocumentModel).where(DocumentModel.run_id == previous_run_id, DocumentModel.status == "source"))
                session.execute(update(DocumentModel).where(DocumentModel.run_id == previous_run_id).values(run_id=None))
                session.execute(delete(DatasetRunModel).where(DatasetRunModel.id == previous_run_id))
            run = DatasetRunModel(seed=data.seed, generated_at=data.generated_at, metadata_json=ml_metadata, is_active=True, site_id="wolfsburg")
            session.add(run); session.flush()
            for model, records, key_field in source_groups:
                session.bulk_save_objects([model(run_id=run.id, source_key=str(record.get(key_field, index)), payload=_jsonable(record)) for index, record in enumerate(records)])
            for document in data.documents:
                session.add(DocumentModel(run_id=run.id, document_id=document["id"], filename=f"{document['id']}.json", document_type=document.get("type", "Source control"), status="source", extracted_data=_jsonable(document), cross_check_results=[]))
            for anomaly in anomalies:
                payload = anomaly.model_dump(mode="json")
                session.add(AnomalyModel(run_id=run.id, anomaly_id=anomaly.id, severity=anomaly.severity, status=anomaly.status, impact=anomaly.impact, payload=payload, site_id="wolfsburg"))
                for action in anomaly.actions:
                    session.add(FixActionModel(anomaly_id=anomaly.id, action_id=action.id, status=action.status, payload=action.model_dump(mode="json"), site_id="wolfsburg"))
            return run.id

    def load_run(self):
        """Load the active operational twin as serializable record groups."""
        run = self.latest_run()
        if not run:
            return None
        table_map = {"skus": MasterSkuModel, "suppliers": SupplierModel, "inventory": InventoryPositionModel, "inbound_orders": InboundOrderModel, "outbound_orders": OutboundOrderModel, "dispatches": DispatchScheduleModel, "workforce": WorkforceLogModel, "containers": ContainerModel}
        with self.session() as session:
            groups = {name: [record.payload for record in session.scalars(select(model).where(model.run_id == run.id)).all()] for name, model in table_map.items()}
            anomalies = [record.payload for record in session.scalars(select(AnomalyModel).where(AnomalyModel.run_id == run.id)).all()]
            groups["documents"] = [row.extracted_data for row in session.scalars(select(DocumentModel).where(DocumentModel.run_id == run.id, DocumentModel.status == "source")).all()]
            return {"run": run, "groups": groups, "anomalies": anomalies}

    def update_run_metadata(self, run_id: int, updates: dict[str, Any]) -> None:
        """Merge keys into a run's metadata JSON (used to backfill persisted ML scores)."""
        with self.session() as session:
            run = session.get(DatasetRunModel, run_id)
            if run:
                run.metadata_json = {**run.metadata_json, **_jsonable(updates)}

    def persist_anomalies(self, run_id: int, anomalies) -> None:
        with self.session() as session:
            for anomaly in anomalies:
                row = session.scalar(select(AnomalyModel).where(AnomalyModel.anomaly_id == anomaly.id))
                payload = anomaly.model_dump(mode="json")
                if row:
                    row.payload = payload; row.status = anomaly.status; row.severity = anomaly.severity; row.impact = anomaly.impact
                else:
                    # Findings born after boot (live injections) must survive restarts.
                    session.add(AnomalyModel(run_id=run_id, anomaly_id=anomaly.id, severity=anomaly.severity, status=anomaly.status, impact=anomaly.impact, payload=payload, site_id="wolfsburg"))
                for action in anomaly.actions:
                    action_row = session.scalar(select(FixActionModel).where(FixActionModel.action_id == action.id))
                    if action_row:
                        action_row.status = action.status; action_row.payload = action.model_dump(mode="json")
                    else:
                        session.add(FixActionModel(anomaly_id=anomaly.id, action_id=action.id, status=action.status, payload=action.model_dump(mode="json"), site_id="wolfsburg"))

    def add_audit(self, event_id: str, event_type: str, actor: str, payload: dict[str, Any]) -> None:
        with self.session() as session:
            session.add(AuditLogModel(event_id=event_id, event_type=event_type, actor=actor, payload=_jsonable(payload)))

    def add_outcome(self, kind: str, title: str, detail: str, saved: int, payload: dict[str, Any]) -> None:
        with self.session() as session:
            session.add(OutcomeModel(kind=kind, title=title, detail=detail, saved=saved, payload=_jsonable(payload)))

    def clear_outcomes(self) -> None:
        """Reset the value ledger. Called when a fresh twin replaces the old one —
        outcome rows describe findings that no longer exist on the new board."""
        with self.session() as session:
            session.execute(delete(OutcomeModel))

    def clear_audit(self) -> None:
        """Reset the audit log alongside the twin: with a fixed seed, regenerated
        findings reuse their deterministic IDs, so stale audit rows would bleed
        last session's history into fresh incident reports."""
        with self.session() as session:
            session.execute(delete(AuditLogModel))

    def outcomes(self, limit: int = 200) -> list[dict[str, Any]]:
        with self.session() as session:
            rows = session.scalars(select(OutcomeModel).order_by(OutcomeModel.created_at.desc()).limit(limit)).all()
            return [{"id": row.id, "kind": row.kind, "title": row.title, "detail": row.detail, "saved": row.saved, "at": row.created_at.isoformat(), **row.payload} for row in rows]

    def update_source_records(self, run_id: int, model, updates: dict[str, dict[str, Any]]) -> None:
        """Apply field corrections to source-twin records, matched by their payload 'id'."""
        if not updates:
            return
        with self.session() as session:
            for row in session.scalars(select(model).where(model.run_id == run_id)).all():
                key = row.payload.get("id")
                if key in updates:
                    row.payload = {**row.payload, **_jsonable(updates[key])}

    def update_source_document(self, document_id: str, updates: dict[str, Any]) -> None:
        with self.session() as session:
            row = session.scalar(select(DocumentModel).where(DocumentModel.document_id == document_id))
            if row:
                row.extracted_data = {**row.extracted_data, **_jsonable(updates)}

    def append_source_record(self, run_id: int, model, record: dict[str, Any]) -> None:
        """Add a new source-twin record (e.g. a remediation-raised PO)."""
        with self.session() as session:
            session.add(model(run_id=run_id, source_key=str(record.get("id", "")), payload=_jsonable(record)))

    def audit(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.session() as session:
            rows = session.scalars(select(AuditLogModel).order_by(AuditLogModel.created_at.desc()).limit(limit)).all()
            return [{"id": row.event_id, "event": row.event_type, "actor": row.actor, "at": row.created_at.isoformat(), **row.payload} for row in rows]

    def add_document(self, run_id: int | None, document_id: str, filename: str, document_type: str, storage_path: str | None, markdown_path: str | None, status: str, extracted_data: dict[str, Any], cross_check_results: list[dict[str, Any]]) -> None:
        with self.session() as session:
            session.add(DocumentModel(run_id=run_id, document_id=document_id, filename=filename, document_type=document_type, storage_path=storage_path, markdown_path=markdown_path, status=status, extracted_data=_jsonable(extracted_data), cross_check_results=_jsonable(cross_check_results)))

    def documents(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.session() as session:
            rows = session.scalars(select(DocumentModel).order_by(DocumentModel.created_at.desc()).limit(limit)).all()
            return [{"id": row.document_id, "filename": row.filename, "type": row.document_type, "status": row.status, "created_at": row.created_at.isoformat(), "storage_path": row.storage_path, "markdown_path": row.markdown_path, "fields": row.extracted_data, "mismatches": row.cross_check_results} for row in rows]

    def document(self, document_id: str) -> dict[str, Any] | None:
        with self.session() as session:
            row = session.scalar(select(DocumentModel).where(DocumentModel.document_id == document_id))
            if not row:
                return None
            return {"id": row.document_id, "filename": row.filename, "type": row.document_type, "status": row.status, "created_at": row.created_at.isoformat(), "storage_path": row.storage_path, "markdown_path": row.markdown_path, "fields": row.extracted_data, "mismatches": row.cross_check_results}

    def browse(self, model, page: int = 1, page_size: int = 50) -> dict[str, Any]:
        page = max(1, page); page_size = min(max(1, page_size), 200)
        with self.session() as session:
            active_run_id = session.scalar(select(DatasetRunModel.id).where(DatasetRunModel.is_active.is_(True)).order_by(DatasetRunModel.id.desc()))
            if active_run_id is None:
                return {"page": page, "page_size": page_size, "total": 0, "items": []}
            statement = select(model).where(model.run_id == active_run_id)
            total = session.scalar(select(func.count()).select_from(model).where(model.run_id == active_run_id)) or 0
            rows = session.scalars(statement.offset((page - 1) * page_size).limit(page_size)).all()
            return {"page": page, "page_size": page_size, "total": total, "items": [row.payload for row in rows]}


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value
