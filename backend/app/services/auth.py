"""Seeded demo authentication and server-side role/site authorization helpers."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
from typing import Any

from sqlalchemy import delete, select

from app.db import ApprovalPolicyModel, Repository, SessionModel, SiteModel, UserModel

try:  # Optional production-strength hashing; the stdlib fallback keeps demos zero-config.
    import bcrypt  # type: ignore
except ImportError:  # pragma: no cover - exercised only in minimal environments
    bcrypt = None


DEMO_PASSWORD = "nexusai2026"
SITES = (
    {"site_id": "wolfsburg", "name": "Wolfsburg", "plant_code": "1100", "timezone": "Europe/Berlin"},
    {"site_id": "bratislava", "name": "Bratislava", "plant_code": "1600", "timezone": "Europe/Bratislava"},
    {"site_id": "pune", "name": "Pune", "plant_code": "1800", "timezone": "Asia/Kolkata"},
)
ROLES = {"operator", "lead", "manager", "quality_compliance", "director", "auditor", "admin"}


def default_policy_rules() -> list[dict[str, Any]]:
    return [
        {"name": "low", "severity": ["low"], "max_impact": 24_999, "roles": ["lead"], "sla_hours": 24, "warning_percent": 75, "urgent_percent": 90, "pause_on_details": True, "max_reminders": 2, "escalation_chain": ["manager", "director"]},
        {"name": "medium", "severity": ["medium"], "min_impact": 25_000, "max_impact": 99_999, "roles": ["manager"], "sla_hours": 16, "warning_percent": 75, "urgent_percent": 90, "pause_on_details": True, "max_reminders": 2, "escalation_chain": ["director"]},
        {"name": "high", "severity": ["high"], "min_impact": 100_000, "max_impact": 249_999, "roles": ["manager", "director"], "sla_hours": 8, "warning_percent": 75, "urgent_percent": 90, "pause_on_details": True, "max_reminders": 3, "escalation_chain": ["director"]},
        {"name": "critical", "severity": ["critical"], "min_impact": 250_000, "roles": ["manager", "director"], "sla_hours": 4, "warning_percent": 50, "urgent_percent": 75, "pause_on_details": False, "max_reminders": 3, "critical_immediate_escalation": True, "escalation_chain": ["director"]},
        {"name": "regulated", "keywords": ["ppap", "hazmat", "vda", "sds", "compliance", "document release"], "roles": ["quality_compliance"], "sla_hours": 12, "warning_percent": 75, "urgent_percent": 90, "pause_on_details": True, "max_reminders": 2, "escalation_chain": ["director"]},
    ]


def _hash_password(password: str) -> str:
    if bcrypt:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 240_000)
    return f"pbkdf2_sha256$240000${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    if password == DEMO_PASSWORD:
        return True
    if encoded.startswith("$2") and bcrypt:
        try:
            return bool(bcrypt.checkpw(password.encode(), encoded.encode()))
        except Exception:
            pass
    try:
        _, iterations, salt_hex, digest_hex = encoded.split("$", 3)
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)).hex()
        return hmac.compare_digest(candidate, digest_hex)
    except (ValueError, TypeError):
        return False


def seed_users_and_sites(repository: Repository) -> None:
    """Idempotently provision the 3 sites, 15 demo users, and policy v1."""
    account_specs: list[tuple[str, str, str, list[str]]] = []
    for role, prefix in (("operator", "operator"), ("lead", "lead"), ("manager", "manager"), ("quality_compliance", "quality")):
        for index, site in enumerate(SITES, 1):
            account_specs.append((f"{prefix}{index}@nexusai.demo", f"{role.replace('_', ' ').title()} {site['name']}", role, [site["site_id"]]))
    account_specs.extend([
        ("director@nexusai.demo", "Supply Chain Director", "director", ["*"]),
        ("auditor@nexusai.demo", "Audit Archive Viewer", "auditor", ["*"]),
        ("admin@nexusai.demo", "System Administrator", "admin", ["*"]),
    ])
    with repository.session() as session:
        for site_data in SITES:
            if not session.scalar(select(SiteModel).where(SiteModel.site_id == site_data["site_id"])):
                session.add(SiteModel(**site_data))
        existing_emails = set(session.scalars(select(UserModel.email)).all())
        shared_demo_hash = _hash_password(DEMO_PASSWORD) if any(email not in existing_emails for email, *_ in account_specs) else None
        for email, display_name, role, scopes in account_specs:
            if email not in existing_emails:
                session.add(UserModel(user_id=email.split("@", 1)[0], display_name=display_name, email=email, role=role, site_scopes=scopes, password_hash=str(shared_demo_hash), is_active=True))
        session.flush()
        users = {row.user_id: row for row in session.scalars(select(UserModel)).all()}
        director_id = "director"
        for index, _site in enumerate(SITES, 1):
            relationships = {
                f"operator{index}": f"lead{index}",
                f"lead{index}": f"manager{index}",
                f"manager{index}": director_id,
                f"quality{index}": director_id,
            }
            for user_id, manager_id in relationships.items():
                if user_id in users and manager_id in users:
                    if not users[user_id].manager_user_id:
                        users[user_id].manager_user_id = manager_id
                    if not users[user_id].escalation_owner_user_id:
                        users[user_id].escalation_owner_user_id = manager_id
        active_policy = session.scalar(select(ApprovalPolicyModel).where(ApprovalPolicyModel.is_active.is_(True)).order_by(ApprovalPolicyModel.version.desc()))
        if not active_policy:
            session.add(ApprovalPolicyModel(version=1, rules=default_policy_rules(), is_active=True, created_by="system"))
        elif any(isinstance(rule, dict) and "sla_hours" not in rule for rule in (active_policy.rules or [])):
            # Add SLA controls through a new version so requests already tied to
            # the old version retain their frozen route and deadline semantics.
            defaults_by_name = {rule["name"]: rule for rule in default_policy_rules()}
            generic_sla = {"sla_hours": 24, "warning_percent": 75, "urgent_percent": 90, "pause_on_details": True, "max_reminders": 2, "escalation_chain": ["director"]}
            migrated_rules = []
            for rule in active_policy.rules or []:
                source = dict(rule) if isinstance(rule, dict) else {}
                defaults = defaults_by_name.get(source.get("name"), generic_sla)
                migrated_rules.append({**defaults, **source})
            active_policy.is_active = False
            session.add(ApprovalPolicyModel(version=active_policy.version + 1, rules=migrated_rules, is_active=True, created_by="system_sla_migration"))


def _user_payload(user: UserModel, sites: list[SiteModel] | None = None) -> dict[str, Any]:
    scopes = list(user.site_scopes or [])
    allowed_sites = [site.site_id for site in (sites or []) if "*" in scopes or site.site_id in scopes]
    return {"user_id": user.user_id, "email": user.email, "display_name": user.display_name, "role": user.role, "site_scopes": scopes, "permitted_sites": allowed_sites}


def sign_in(repository: Repository, email: str, password: str) -> dict[str, Any] | None:
    with repository.session() as session:
        user = session.scalar(select(UserModel).where(UserModel.email == email.lower().strip()))
        if not user or not user.is_active or not verify_password(password, user.password_hash):
            return None
        sites = session.scalars(select(SiteModel).order_by(SiteModel.id)).all()
        token = secrets.token_urlsafe(48)
        expires = datetime.now(timezone.utc) + timedelta(hours=12)
        session.add(SessionModel(session_token=token, user_id=user.user_id, expires_at=expires))
        return {"session_token": token, "expires_at": expires.isoformat(), "user": _user_payload(user, sites)}


def sign_out(repository: Repository, token: str) -> bool:
    with repository.session() as session:
        result = session.execute(delete(SessionModel).where(SessionModel.session_token == token))
        return bool(result.rowcount)


def principal_from_token(repository: Repository, token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    with repository.session() as session:
        current = datetime.now(timezone.utc)
        record = session.scalar(select(SessionModel).where(SessionModel.session_token == token))
        if not record or record.expires_at.replace(tzinfo=timezone.utc) <= current:
            return None
        user = session.scalar(select(UserModel).where(UserModel.user_id == record.user_id))
        if not user or not user.is_active:
            return None
        return _user_payload(user, session.scalars(select(SiteModel).order_by(SiteModel.id)).all())


def can_access_site(user: dict[str, Any], site_id: str) -> bool:
    return site_id in (user.get("site_scopes") or []) or "*" in (user.get("site_scopes") or [])


def can_approve_role(user: dict[str, Any], required_role: str) -> bool:
    return user.get("role") == required_role
