"""Deterministic, governed commands for the WALT assistant.

The language model is never allowed to mutate workflow state. This module
recognises a deliberately small set of operational intents, resolves them
against server-side identity and request data, and uses the existing
preview/confirm workflow controls for consequential actions.
"""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select

from app.db import SiteModel, UserModel
from app.services.change_control import list_requests, workflow_summary
from app.services.workflow_coordination import prepare_workflow_action


ROLE_SCOPE = {
    "operator": {
        "label": "Operations Operator",
        "can": "create and submit requests, inspect evidence, and remind or escalate eligible approvals on requests you created",
        "cannot": "approve your own request or view another operator's requests",
    },
    "lead": {
        "label": "Operations Lead",
        "can": "review and decide stages assigned specifically to your account, request details, delegate safely, and escalate",
        "cannot": "decide a stage assigned to another lead or operate outside your site scope",
    },
    "manager": {
        "label": "Operations Manager",
        "can": "review and decide manager stages assigned specifically to your account and escalate to the configured executive owner",
        "cannot": "approve a request merely because you have the manager role",
    },
    "quality_compliance": {
        "label": "Quality & Compliance",
        "can": "decide regulated quality stages assigned specifically to your account and request supporting evidence",
        "cannot": "approve operational or executive stages outside the quality route",
    },
    "director": {
        "label": "Supply Chain Director",
        "can": "decide assigned final approvals across configured sites and request safeguarded rollback where permitted",
        "cannot": "bypass earlier approval stages or separation of duties",
    },
    "auditor": {
        "label": "Auditor",
        "can": "review immutable decision history, names, timestamps, comments, and export the audit workbook",
        "cannot": "approve, reject, remind, escalate, or modify operational requests",
    },
    "admin": {
        "label": "System Administrator",
        "can": "manage identities, reporting relationships, site scopes, and versioned workflow policy",
        "cannot": "impersonate an approver or make operational decisions",
    },
}


def _identity_context(repo, principal: dict[str, Any]) -> dict[str, Any]:
    with repo.session() as session:
        user = session.scalar(select(UserModel).where(UserModel.user_id == principal.get("user_id")))
        manager = session.scalar(select(UserModel).where(UserModel.user_id == user.manager_user_id)) if user and user.manager_user_id else None
        escalation_owner = session.scalar(select(UserModel).where(UserModel.user_id == user.escalation_owner_user_id)) if user and user.escalation_owner_user_id else None
        sites = session.scalars(select(SiteModel).order_by(SiteModel.name)).all()
        scopes = list(principal.get("site_scopes") or [])
        visible_sites = [
            {"site_id": site.site_id, "name": site.name, "plant_code": site.plant_code}
            for site in sites if "*" in scopes or site.site_id in scopes
        ]

    def person(row: UserModel | None) -> dict[str, Any] | None:
        if not row or not row.is_active:
            return None
        return {"user_id": row.user_id, "display_name": row.display_name, "email": row.email, "role": row.role}

    role = str(principal.get("role") or "")
    return {
        "user": {
            "user_id": principal.get("user_id"),
            "display_name": principal.get("display_name"),
            "email": principal.get("email"),
            "role": role,
            "role_label": ROLE_SCOPE.get(role, {}).get("label", role.replace("_", " ").title()),
        },
        "manager": person(manager),
        "escalation_owner": person(escalation_owner),
        "site_scopes": scopes,
        "sites": visible_sites,
        "scope_rule": ROLE_SCOPE.get(role, {"can": "view authorized records", "cannot": "act outside assigned permissions"}),
    }


def _intent(message: str, history: list[Any] | None = None) -> str | None:
    text = " ".join(message.lower().split()).strip()
    recent = " ".join(str(turn.get("content", "") if isinstance(turn, dict) else getattr(turn, "content", "")) for turn in (history or [])).lower()

    # Keep lightweight conversation in the governed resolver. This prevents a
    # greeting or a capabilities question from being misread as an anomaly
    # search, while the live-data answers below remain authorization-bound.
    if re.fullmatch(r"(?:hi|hello|hey|hiya|good morning|good afternoon|good evening|how are you|how's it going)(?:\s+walt)?[!.? ]*", text):
        return "greeting"
    if re.fullmatch(r"(?:thanks|thank you|thx|cheers|got it|perfect|that helps)[!.? ]*", text):
        return "thanks"
    if any(term in text for term in ("what can you do", "what do you do", "how can you help", "help me", "help with", "capabilities")):
        return "help"
    if re.search(r"\b(?:send|forward|write)\s+(?:an?\s+)?email\b", text) or (re.match(r"^(?:email|mail)\s+(?:my\s+)?(?:manager|supervisor|boss)\b", text) and not re.search(r"\b(?:address|email|e-mail|mail|contact|details)\b", text)):
        return "email_unavailable"
    if "escalat" in text:
        return "escalation"
    if re.search(r"\b(?:remind|notify|ping|nudge|alert)\b", text):
        return "reminder"
    if any(term in text for term in ("i don't understand", "i do not understand", "that answer is wrong", "not helpful", "wrong answer", "try again")):
        return "correction"

    manager_words = r"(?:manager|supervisor|boss|line manager|reporting manager)"
    manager_question = (
        re.search(rf"\bwho(?:'s| is)\s+(?:my\s+)?(?:direct\s+)?{manager_words}\b", text)
        or re.search(r"\bwho\s+do\s+i\s+report\s+to\b", text)
        or re.search(rf"\b(?:my|direct|line|reporting)\s+{manager_words}\b", text)
        or re.search(rf"\b{manager_words}(?:'s|s)?\s+(?:name|email|e-mail|mail|address|contact|details)\b", text)
        or re.search(rf"\b(?:name|email|e-mail|mail|address|contact|details)\s+(?:of|for)\s+(?:my\s+)?{manager_words}\b", text)
        or text in {"manager", "my manager", "supervisor", "my supervisor", "boss", "my boss"}
    )
    contact_followup = bool(re.search(r"\b(?:email|e-mail|mail|address|contact|phone|number|details)\b", text))
    if contact_followup and re.search(r"\b(?:him|her|them|their|that person)\b", text) and re.search(r"\bescalation owner\b", recent):
        return "escalation_owner"
    if manager_question or (contact_followup and re.search(r"\b(?:him|her|them|their|that person)\b", text) and re.search(rf"\b{manager_words}\b|\breport\b|\bescalation owner\b", recent)):
        return "manager"
    if re.search(r"\bwho am i\b|\bwhat(?:'s| is) my (?:name|email|account|user id)\b|\bmy account details\b", text):
        return "identity"
    if re.search(r"\b(?:who is|what is) my escalation owner\b|\bmy escalation owner(?:'s|s)?\s+(?:name|email|e-mail|mail|contact|details)\b", text):
        return "escalation_owner"
    if any(term in text for term in ("my scope", "what is my scope", "my permission", "what can i do", "what am i allowed", "my role")):
        return "scope"
    if any(term in text for term in ("my approval queue", "what needs my approval", "assigned to me", "my decisions")):
        return "queue"
    if any(term in text for term in ("next approver", "who approves", "approval status", "who owns", "approval necessary", "needs approval")):
        return "approval_status"
    if re.search(r"\b(approve|reject|return|cancel|delegate|apply)\b", text):
        return "restricted_decision"
    return None


def _mentions_manager(message: str) -> bool:
    return bool(re.search(r"\b(?:my|the|to my|him|her|their)\s+(?:manager|supervisor|boss|line manager|reporting manager)\b|\bwho do i report to\b", message.lower()))


def _manager_summary(identity: dict[str, Any]) -> str:
    manager = identity.get("manager")
    if not manager:
        return "No active reporting manager is configured for your account."
    return f"Your reporting manager is **{manager['display_name']}** ({_role_label(manager['role'])}) at **{manager['email']}**."


def _request_choices(requests: list[dict[str, Any]], action: str | None = None) -> list[dict[str, str]]:
    candidates = requests
    if action:
        candidates = [item for item in candidates if action in (item.get("allowed_actions") or [])]
    return [{
        "request_id": item["request_id"],
        "label": f"{item['request_id']} · {item.get('title') or 'Change request'}",
        "status": str(item.get("status") or "").replace("_", " "),
    } for item in candidates[:6]]


def _select_request(message: str, request_id: str | None, requests: list[dict[str, Any]], action: str | None = None) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    candidates = requests if not action else [item for item in requests if action in (item.get("allowed_actions") or [])]
    visible = {item["request_id"].upper(): item for item in requests}
    mentioned = re.search(r"\bCR-[A-Z0-9]+\b", message.upper())
    selected_id = mentioned.group(0) if mentioned else (request_id or "").upper()
    if selected_id:
        selected = visible.get(selected_id)
        if selected and (not action or action in (selected.get("allowed_actions") or [])):
            return selected, []
        return None, _request_choices(candidates)
    if len(candidates) == 1:
        return candidates[0], []
    return None, _request_choices(candidates)


def _owner(repo, request: dict[str, Any]) -> dict[str, Any] | None:
    active = request.get("active_step") or {}
    user_id = active.get("assigned_to")
    if not user_id:
        return None
    with repo.session() as session:
        row = session.scalar(select(UserModel).where(UserModel.user_id == user_id))
        if not row or not row.is_active:
            return None
        return {"user_id": row.user_id, "display_name": row.display_name, "role": row.role}


def _clarification(action_label: str, choices: list[dict[str, str]]) -> dict[str, Any]:
    if not choices:
        return {
            "handled": True,
            "type": "denied",
            "answer": f"I cannot {action_label} because no visible request currently permits that action for your exact role, assignment, and site scope.",
        }
    lines = "\n".join(f"- **{item['request_id']}** — {item['label'].split(' · ', 1)[-1]} ({item['status']})" for item in choices)
    return {
        "handled": True,
        "type": "clarification",
        "answer": f"I found more than one eligible request. Choose the exact request before I {action_label}:\n\n{lines}",
        "choices": choices,
    }


def _role_label(role: str) -> str:
    return ROLE_SCOPE.get(role, {}).get("label", role.replace("_", " ").title())


def resolve_walt_command(message: str, request_id: str | None, principal: dict[str, Any], repo, history: list[Any] | None = None) -> dict[str, Any]:
    """Resolve a WALT command without giving the model mutation authority."""
    intent = _intent(message, history)
    if not intent:
        return {"handled": False}

    identity = _identity_context(repo, principal)
    if intent == "email_unavailable":
        return {
            "handled": True,
            "type": "unsupported",
            "answer": f"{_manager_summary(identity)} I can show the address, but outbound email delivery is not connected yet. I can prepare a governed in-app reminder or escalation when you provide a request.",
        }

    if intent == "correction":
        return {
            "handled": True,
            "type": "conversation",
            "answer": "Thanks for flagging that. Tell me what part was wrong, or ask me to re-check the live evidence with the request ID or finding ID.",
        }

    if intent == "greeting":
        return {
            "handled": True,
            "type": "conversation",
            "answer": "Hi — I’m WALT. I can help with live operational risks, your identity and reporting line, approval ownership, request status, and governed reminders or escalations.",
        }

    if intent == "thanks":
        return {
            "handled": True,
            "type": "conversation",
            "answer": "You’re welcome. I’m here whenever you need a live operations check or want me to explain the next governed step.",
        }

    if intent == "help":
        return {
            "handled": True,
            "type": "conversation",
            "answer": "You can ask me things like **“Who is my manager and what is their email?”**, **“What is my role and site scope?”**, **“Who owns CR-123?”**, **“What needs my approval?”**, or **“Remind the current approver”**. I answer identity and workflow questions from live records, and I always ask for confirmation before sending a notification.",
        }

    if intent == "identity":
        user = identity["user"]
        site_names = ", ".join(site["name"] for site in identity["sites"]) or "No active site"
        answer = (
            f"You’re **{user['display_name']}** ({user['email']}). "
            f"Your role is **{user['role_label']}**, and your authorized site scope is **{site_names}**."
        )
        return {"handled": True, "type": "identity", "answer": answer, "identity": identity}

    if intent in {"manager", "escalation_owner"}:
        manager = identity["manager"]
        escalation_owner = identity["escalation_owner"]
        person = escalation_owner if intent == "escalation_owner" else manager
        label = "escalation owner" if intent == "escalation_owner" else "reporting manager"
        if not person:
            answer = f"No active {label} is configured for your account. Ask an administrator to set the relationship before WALT routes a personal escalation."
        else:
            answer = (
                f"Your {label} is **{person['display_name']}** ({_role_label(person['role'])}). "
                f"Their email is **{person['email']}**."
            )
            if intent == "manager" and escalation_owner and escalation_owner["user_id"] != manager["user_id"]:
                answer += f" Your configured escalation owner is **{escalation_owner['display_name']}** ({_role_label(escalation_owner['role'])}) at **{escalation_owner['email']}**."
        return {"handled": True, "type": "identity", "answer": answer, "identity": identity}

    requests = list_requests(repo, principal)

    if intent == "scope":
        rule = identity["scope_rule"]
        site_names = ", ".join(site["name"] for site in identity["sites"]) or "No active site"
        actions = workflow_summary(repo, principal).get("assistant_capabilities", {}).get("permitted_actions", [])
        action_text = ", ".join(item["label"] for item in actions) or "No state-changing workflow action is currently available"
        answer = (
            f"### Your governed scope\n\n"
            f"- **Role:** {identity['user']['role_label']}\n"
            f"- **Sites:** {site_names}\n"
            f"- **You can:** {rule['can']}.\n"
            f"- **You cannot:** {rule['cannot']}.\n"
            f"- **Available right now:** {action_text}.\n\n"
            "Permissions are recalculated from the live request, exact assignee, reporting chain, and site scope before every action."
        )
        return {"handled": True, "type": "scope", "answer": answer, "identity": identity}

    if intent == "queue":
        assigned = [item for item in requests if (item.get("active_step") or {}).get("assigned_to") == principal.get("user_id")]
        if not assigned:
            answer = "Your approval queue is clear. No active stage is assigned to your account right now."
        else:
            lines = "\n".join(f"- **{item['request_id']}** — {item.get('title') or 'Change request'} · €{item.get('impact_euros', 0):,} · {str(item.get('status')).replace('_', ' ')}" for item in assigned[:6])
            answer = f"### Assigned to you\n\n{lines}\n\nOnly these exact assignments can be decided from your account."
        return {"handled": True, "type": "queue", "answer": answer, "choices": _request_choices(assigned)}

    if intent == "restricted_decision":
        selected, choices = _select_request(message, request_id, requests)
        suffix = f" for **{selected['request_id']}**" if selected else ""
        answer = f"I can prepare evidence and show your permission result{suffix}, but I will not approve, reject, apply, cancel, or delegate from a free-text instruction. Open the governed request and use its explicit human decision control."
        if not selected and choices:
            answer += " Select a request first if you want its exact permission explanation."
        return {"handled": True, "type": "guardrail", "answer": answer, "choices": choices}

    if intent == "approval_status":
        selected, choices = _select_request(message, request_id, requests)
        if not selected:
            return _clarification("show its approval owner", choices)
        owner = _owner(repo, selected)
        active = selected.get("active_step") or {}
        if owner:
            owner_text = f"**{owner['display_name']}** ({_role_label(owner['role'])})"
        else:
            owner_text = "no active named approver"
        answer = (
            f"**{selected['request_id']}** is **{str(selected.get('status')).replace('_', ' ')}**. "
            f"The current approval owner is {owner_text}. The stage requires **{str(active.get('required_role') or 'none').replace('_', ' ').title()}**.\n\n"
            f"Your allowed actions: {', '.join(action.replace('_', ' ') for action in selected.get('allowed_actions', [])) or 'read-only access'}."
        )
        return {"handled": True, "type": "workflow_status", "answer": answer, "request": {"request_id": selected["request_id"], "owner": owner, "status": selected.get("status")}}

    kind = "escalation" if intent == "escalation" else "reminder"
    required_action = "prepare_escalation" if kind == "escalation" else "send_reminder"
    selected, choices = _select_request(message, request_id, requests, required_action)
    if not selected:
            result = _clarification("prepare that escalation" if kind == "escalation" else "notify the current approver", choices)
            if _mentions_manager(message): result["answer"] = f"{_manager_summary(identity)}\n\n{result['answer']}"
            return result

    try:
        preview = prepare_workflow_action(selected["request_id"], kind, {"reason": message}, principal, repo)
    except (LookupError, PermissionError, ValueError) as error:
        return {"handled": True, "type": "denied", "answer": str(error)}

    payload = preview.get("payload") or {}
    recipient = payload.get("recipient_name") or preview.get("recipient_user_id")
    stage = str(payload.get("current_stage") or "active approval").replace("_", " ")
    verb = "escalation" if kind == "escalation" else "priority reminder"
    answer = (
        f"I prepared a **{verb}** for **{selected['request_id']}** to **{recipient}**. "
        f"It concerns the **{stage}** stage at **{selected.get('site_id')}**.\n\n"
        "Confirm below to send the in-app notification immediately. This will not approve, reject, or bypass the current stage."
    )
    if _mentions_manager(message): answer = f"{_manager_summary(identity)}\n\n{answer}"
    return {
        "handled": True,
        "type": "action_preview",
        "answer": answer,
        "action": {
            "kind": kind,
            "action_id": preview["action_id"],
            "request_id": selected["request_id"],
            "recipient_user_id": preview["recipient_user_id"],
            "recipient_name": recipient,
            "recipient_role": payload.get("recipient_role"),
            "site_id": selected.get("site_id"),
            "severity": payload.get("severity"),
            "sla": payload.get("sla") or {},
            "requires_confirmation": True,
        },
    }
