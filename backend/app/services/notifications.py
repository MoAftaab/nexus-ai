"""Persistent, site-scoped notifications for governed change requests."""
from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import Any

from sqlalchemy import select

from app.db import NotificationModel, Repository, UserModel


def _in_scope(user: UserModel, site_id: str) -> bool:
    scopes = list(user.site_scopes or [])
    return "*" in scopes or site_id in scopes


def users_for_role(repo: Repository, role: str, site_id: str) -> list[UserModel]:
    with repo.session() as session:
        users = session.scalars(select(UserModel).where(UserModel.role == role, UserModel.is_active.is_(True))).all()
        return [user for user in users if _in_scope(user, site_id)]


def create_notification(repo: Repository, user_id: str, site_id: str, notification_type: str, title: str, message: str, request_id: str | None = None, payload: dict[str, Any] | None = None) -> None:
    with repo.session() as session:
        session.add(NotificationModel(notification_id=f"NT-{uuid.uuid4().hex[:12].upper()}", user_id=user_id, site_id=site_id, request_id=request_id, notification_type=notification_type, title=title, message=message, payload=payload or {}))


def notify_users(repo: Repository, user_ids: set[str], site_id: str, notification_type: str, title: str, message: str, request_id: str | None = None, payload: dict[str, Any] | None = None) -> None:
    for user_id in sorted(user_ids):
        create_notification(repo, user_id, site_id, notification_type, title, message, request_id, payload)


def notify_request(repo: Repository, request, event: str, actor: str | None = None, detail: str = "") -> None:
    """Notify the requester, prior approvers, and current approver group."""
    recipients = {request.requested_by}
    with repo.session() as session:
        steps = session.execute(select(UserModel).where(UserModel.is_active.is_(True))).scalars().all()
        users = {user.user_id: user for user in steps}
        from app.db import ApprovalStepModel
        request_steps = session.scalars(select(ApprovalStepModel).where(ApprovalStepModel.request_id == request.request_id)).all()
        for step in request_steps:
            if step.decided_by:
                recipients.add(step.decided_by)
            if step.status == "active":
                if step.assigned_to and step.assigned_to in users:
                    recipients.add(step.assigned_to)
    if actor:
        recipients.discard(actor)
    current = str(request.status).replace("awaiting_", "").replace("_", " ")
    titles = {
        "submitted": "Approval required",
        "approved": "Request approved and moved forward",
        "rejected": "Request rejected",
        "returned": "Request returned for changes",
        "verified": "Approved change verified",
        "rolled_back": "Approved change rolled back",
    }
    title = titles.get(event, "Change request updated")
    message = detail or f"{request.request_id} is now {current}."
    notify_users(repo, recipients, request.site_id, event, title, message, request.request_id, {"status": request.status, "actor": actor})


def notify_assignment_failure(repo: Repository, request, required_role: str) -> None:
    """Route an unassigned stage to one configured governance owner, never a role-wide pool."""
    recipients: set[str] = set()
    with repo.session() as session:
        users = session.scalars(select(UserModel)).all()
        by_id = {candidate.user_id: candidate for candidate in users}
        cursor = by_id.get(request.requested_by)
        visited: set[str] = set()
        while cursor and cursor.user_id not in visited:
            visited.add(cursor.user_id)
            next_id = cursor.escalation_owner_user_id or cursor.manager_user_id
            cursor = by_id.get(next_id or "")
            if cursor and cursor.is_active and _in_scope(cursor, request.site_id):
                recipients.add(cursor.user_id)
                break
        if not recipients:
            administrator = next((candidate for candidate in users if candidate.role == "admin" and candidate.is_active), None)
            if administrator:
                recipients.add(administrator.user_id)
    notify_users(repo, recipients, request.site_id, "stage_unassigned", "Approval stage needs an owner", f"{request.request_id} requires an active {required_role.replace('_', ' ')} assignee. The stage was not bypassed.", request.request_id, {"status": request.status, "required_role": required_role, "assignment_problem": True})


def list_notifications(repo: Repository, user: dict[str, Any], unread_only: bool = False) -> list[dict[str, Any]]:
    with repo.session() as session:
        query = select(NotificationModel).where(NotificationModel.user_id == user.get("user_id"))
        if unread_only:
            query = query.where(NotificationModel.read_at.is_(None))
        rows = session.scalars(query.order_by(NotificationModel.created_at.desc()).limit(100)).all()
        return [{"notification_id": row.notification_id, "site_id": row.site_id, "request_id": row.request_id, "type": row.notification_type, "title": row.title, "message": row.message, "payload": row.payload, "read": row.read_at is not None, "created_at": row.created_at.isoformat()} for row in rows]


def mark_notification_read(repo: Repository, notification_id: str, user: dict[str, Any]) -> bool:
    with repo.session() as session:
        row = session.scalar(select(NotificationModel).where(NotificationModel.notification_id == notification_id, NotificationModel.user_id == user.get("user_id")))
        if not row:
            return False
        row.read_at = datetime.now(timezone.utc)
        return True
