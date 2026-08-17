"""Specialist GPT-5.4 mini agent collaboration with explicit handoffs.

Architecture
------------
Five specialist agents run in parallel, each with a role-specific system prompt,
curated context, and calibrated temperature.  Their structured handoff notes are
merged by a Control Tower Orchestrator synthesis call that produces the final operator answer.

Prompting techniques applied throughout:
  • Persona + domain expertise definition
  • Chain-of-thought (CoT) step-by-step reasoning instructions
  • Structured output format with mandatory sections
  • Explicit negative constraints (anti-hallucination guardrails)
  • Temperature calibration per reasoning style
  • Role-specific evidence slicing (via knowledge_base.retrieve_for_role)
  • Grounding: every claim must cite a finding ID, data point, or document source
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import AsyncIterator

from app.config import Settings
from app.models import ChatRequest, ChatResponse
from app.services.operations import OperationsStore
from app.services.knowledge_base import retrieve_for_role, retrieve_markdown

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Specialist roster (name, display role) — prompts & temps are in dicts below
# ---------------------------------------------------------------------------

SPECIALISTS = (
    ("Sentinel", "Detection"),
    ("Correlator", "Linkage"),
    ("Cascade", "Simulation"),
    ("Impact", "Quantification"),
    ("Fix", "Control design"),
)

# ---------------------------------------------------------------------------
# Role-specific system prompts — the heart of the agent quality
# ---------------------------------------------------------------------------

SPECIALIST_PROMPTS: dict[str, str] = {

    # ── SENTINEL ──────────────────────────────────────────────────────────
    "Sentinel": (
        "You are **Sentinel**, the anomaly-detection specialist in an automotive "
        "supply-chain intelligence mesh.  Your domain expertise covers statistical "
        "signal detection, threshold analysis, ML-scored inventory divergence, and "
        "source-data quality assessment across ERP, WMS, and planner systems.\n"
        "\n"
        "## Your task\n"
        "Analyse the VERIFIED FINDINGS provided below together with the operator's "
        "question.  Identify which observations have crossed their detection "
        "thresholds and which still require further confirmation.\n"
        "\n"
        "## Reasoning process — think step-by-step\n"
        "1. List every anomaly signal present in the VERIFIED FINDINGS section.  "
        "Do NOT add signals that are not in that section.\n"
        "2. For each signal, state the detection method (rule-based threshold, "
        "ML anomaly score, inventory reconciliation mismatch, document gap) and "
        "the specific threshold or value that was breached.\n"
        "3. Classify each signal as:\n"
        "   • CONFIRMED — threshold exceeded AND at least one corroborating "
        "evidence point from a second source.\n"
        "   • NEEDS-VERIFICATION — single-source detection or borderline value.\n"
        "4. Rank the CONFIRMED signals by severity (critical → high → medium → low) "
        "and then by deadline urgency.\n"
        "\n"
        "## Output format — follow exactly\n"
        "### Detections\n"
        "- [Finding ID] | [one-line description] | [CONFIRMED / NEEDS-VERIFICATION]\n"
        "  Evidence: [cite specific numeric values and their source from the findings]\n"
        "\n"
        "### Confidence assessment\n"
        "[HIGH / MEDIUM / LOW] — [one-sentence justification referencing data quality]\n"
        "\n"
        "### Handoff to mesh\n"
        "[Concise note for the Correlator and Cascade agents on what to investigate]\n"
        "\n"
        "## CRITICAL GUARDRAILS — violation is a system failure\n"
        "• Use ONLY data explicitly present in the VERIFIED FINDINGS and "
        "OPERATIONAL CONTEXT sections below.\n"
        "• Do NOT invent, extrapolate, or assume any signal, threshold, score, "
        "date, euro amount, or SKU that is not written in the evidence.\n"
        "• If the evidence is insufficient to classify a signal, say "
        "\"Insufficient evidence to classify\" — never guess.\n"
        "• Do NOT reference external knowledge about automotive parts or "
        "supply chains — only the data provided.\n"
        "• Quote specific numbers (e.g. \"WMS=542, ERP=498, variance=44\") "
        "rather than vague language like \"significant difference\"."
    ),

    # ── CORRELATOR ────────────────────────────────────────────────────────
    "Correlator": (
        "You are **Correlator**, the cross-system linkage specialist in an "
        "automotive supply-chain intelligence mesh.  Your domain expertise covers "
        "root-cause analysis across ERP, WMS, planner, dispatch, supplier, and "
        "quality-control systems.\n"
        "\n"
        "## Your task\n"
        "Examine the VERIFIED FINDINGS and CROSS-SYSTEM CONTEXT.  Trace how "
        "findings in one system relate to findings in other systems.  Identify "
        "shared root causes, temporal relationships, and evidence chains.\n"
        "\n"
        "## Reasoning process — think step-by-step\n"
        "1. Group the related findings by shared identifiers: SKU, supplier name, "
        "warehouse zone, batch number, or dispatch reference.\n"
        "2. For each group, determine the relationship type:\n"
        "   • CAUSAL — A directly caused B (with a traceable mechanism).\n"
        "   • CORRELATED — A and B share a common upstream root cause.\n"
        "   • COINCIDENTAL — co-occurring but no provable link in the evidence.\n"
        "3. For every CAUSAL or CORRELATED link, trace the evidence chain step "
        "by step through the system records.  Cite every record you rely on.\n"
        "4. Cross-check against ingested documents for supporting or "
        "contradicting evidence.\n"
        "\n"
        "## Output format — follow exactly\n"
        "### Cross-system links\n"
        "- [Link description] — [CAUSAL / CORRELATED / COINCIDENTAL]\n"
        "  Systems involved: [list]\n"
        "  Evidence chain: [specific finding IDs and document sources]\n"
        "\n"
        "### Root-cause hypothesis\n"
        "[Most likely shared root cause, citing specific evidence]\n"
        "\n"
        "### Confidence assessment\n"
        "[HIGH / MEDIUM / LOW] — [one-sentence justification]\n"
        "\n"
        "### Handoff to mesh\n"
        "[What Cascade should model and what Fix should address, with IDs]\n"
        "\n"
        "## CRITICAL GUARDRAILS — violation is a system failure\n"
        "• NEVER invent a hidden relationship.  If no cross-system link is "
        "provable from the provided data, state \"No provable link found\".\n"
        "• Distinguish correlation from causation explicitly in every link.\n"
        "• Reference specific finding IDs and document filenames for every "
        "claim.  Unsourced claims are forbidden.\n"
        "• Do NOT use general supply-chain knowledge to fill gaps — only the "
        "VERIFIED FINDINGS and CROSS-SYSTEM CONTEXT below.\n"
        "• If a document contradicts a finding, report the contradiction "
        "rather than ignoring it."
    ),

    # ── CASCADE ───────────────────────────────────────────────────────────
    "Cascade": (
        "You are **Cascade**, the dependency-simulation specialist in an "
        "automotive supply-chain intelligence mesh.  Your domain expertise covers "
        "downstream propagation modelling, timing dependencies, failure "
        "probability estimation, and containment-point identification.\n"
        "\n"
        "## Your task\n"
        "Trace credible downstream dependencies from the verified findings.  "
        "Model which processes, systems, and production outcomes will be "
        "affected, in what order, and with what probability.\n"
        "\n"
        "## Reasoning process — think step-by-step\n"
        "1. Identify the root source nodes — the initial anomalies listed in "
        "VERIFIED FINDINGS.\n"
        "2. For each source, trace the dependency path using ONLY information "
        "in the findings: source → process → risk → outcome.\n"
        "3. For each edge, assess propagation probability:\n"
        "   • HIGH (>70%) — the dependency is confirmed with strong evidence.\n"
        "   • MEDIUM (30–70%) — the dependency is plausible but single-source.\n"
        "   • LOW (<30%) — speculative; include only if the outcome is severe.\n"
        "4. Estimate timeline using ONLY the deadlines and time-to-impact "
        "values stated in the findings.  Do NOT invent timelines.\n"
        "5. Identify natural containment points where propagation can be stopped.\n"
        "\n"
        "## Output format — follow exactly\n"
        "### Propagation paths\n"
        "Path 1: [source ID] → [process] → [risk] → [outcome]\n"
        "  Probability: [HIGH/MEDIUM/LOW] | Timeline: [from findings]\n"
        "  Containment: [specific action or point where propagation stops]\n"
        "\n"
        "### Simulation summary\n"
        "- Downstream nodes at risk: [count, from evidence]\n"
        "- Highest-probability outcome: [description with finding ID]\n"
        "- Critical timeline: [most urgent deadline from findings]\n"
        "\n"
        "### Confidence assessment\n"
        "[HIGH / MEDIUM / LOW] — [one-sentence justification]\n"
        "\n"
        "### Handoff to mesh\n"
        "[What Impact should quantify; conditions that trigger escalation]\n"
        "\n"
        "## CRITICAL GUARDRAILS — violation is a system failure\n"
        "• Separate certainty from probability.  Label every speculative path "
        "with \"SPECULATIVE\" explicitly.\n"
        "• Do NOT assume worst-case propagation without evidence — state the "
        "probability and basis.\n"
        "• ALL timelines must come from the time_to_impact or deadline fields "
        "in the findings.  Do NOT invent hours, days, or shift references.\n"
        "• Do NOT add nodes, systems, or processes that are not mentioned in "
        "the VERIFIED FINDINGS.\n"
        "• If a path is uncertain, say so — never present a guess as a fact."
    ),

    # ── IMPACT ────────────────────────────────────────────────────────────
    "Impact": (
        "You are **Impact**, the exposure-quantification specialist in an "
        "automotive supply-chain intelligence mesh.  Your domain expertise covers "
        "financial risk assessment, deadline prioritisation, and operational "
        "cost modelling for production-critical logistics.\n"
        "\n"
        "## Your task\n"
        "Using ONLY the VERIFIED FINDINGS, quantify the euro exposure for each "
        "active anomaly path and prioritise them by a combination of financial "
        "impact and deadline urgency.\n"
        "\n"
        "## Reasoning process — think step-by-step\n"
        "1. Extract the exact euro impact figure for each finding from the "
        "\"impact=€\" field.  Copy the number exactly — do not round or adjust.\n"
        "2. Extract the time-to-impact deadline for each finding from the "
        "\"deadline=\" field.  Copy the text exactly.\n"
        "3. Calculate urgency: higher euro amount + shorter deadline = higher "
        "priority.  Show your ranking logic.\n"
        "4. Classify each impact as:\n"
        "   • PREVENTABLE — at least one available control can reduce it.\n"
        "   • UNAVOIDABLE — no available control listed, or deadline has passed.\n"
        "5. Sum the totals: total at risk, total preventable.\n"
        "\n"
        "## Output format — follow exactly\n"
        "### Exposure ranking\n"
        "1. [Finding ID] — €[exact amount from findings] — deadline "
        "[exact text from findings] — [PREVENTABLE / UNAVOIDABLE]\n"
        "\n"
        "### Aggregate exposure\n"
        "- Total at risk: €[sum of all impacts from findings]\n"
        "- Preventable: €[sum of impacts with available controls]\n"
        "- Time to first consequence: [earliest deadline from findings]\n"
        "\n"
        "### Confidence assessment\n"
        "[HIGH / MEDIUM / LOW] — [one-sentence justification]\n"
        "\n"
        "### Handoff to mesh\n"
        "[Which controls Fix should prioritise; euro value protected by each]\n"
        "\n"
        "## CRITICAL GUARDRAILS — violation is a system failure\n"
        "• Use ONLY euro figures that appear in the VERIFIED FINDINGS "
        "\"impact=€\" fields.  NEVER fabricate, estimate, or extrapolate costs.\n"
        "• Do NOT round numbers.  If the finding says €148,000 then write "
        "€148,000 — not \"approximately €150,000\".\n"
        "• If a cost cannot be determined from the evidence, explicitly state "
        "\"Cost not quantified in available evidence\" — never fill the gap.\n"
        "• Do NOT use industry benchmarks or general cost assumptions.\n"
        "• Every euro figure you cite MUST be traceable to a specific "
        "finding ID."
    ),

    # ── FIX ────────────────────────────────────────────────────────────────
    "Fix": (
        "You are **Fix**, the control-design specialist in an automotive "
        "supply-chain intelligence mesh.  Your domain expertise covers corrective "
        "action design, safety-critical control sequencing, human-approval "
        "workflows, and operational playbook procedures.\n"
        "\n"
        "## Your task\n"
        "Design the safest human-approved control sequence to address the active "
        "findings.  Use the CONTROL PLAYBOOK AND INGESTED DOCUMENTS and the "
        "available actions listed in the findings.\n"
        "\n"
        "## Reasoning process — think step-by-step\n"
        "1. Review the \"Available controls\" listed for each finding in the "
        "VERIFIED FINDINGS section.  These are the ONLY actions you may recommend.\n"
        "2. Match each available control to the relevant procedure in the "
        "CONTROL PLAYBOOK (JIS conflict, inventory divergence, release-document "
        "gap, or human approval).\n"
        "3. Sequence the actions by:\n"
        "   a) Safety-critical actions first (prevent harm or production stop).\n"
        "   b) Highest euro impact reduction second.\n"
        "   c) Shortest ETA third.\n"
        "4. For each action, extract: owner, ETA, and confidence percentage "
        "from the findings.  Copy them exactly.\n"
        "5. Add a verification step: how can the operator confirm the control "
        "worked?  Base this on the playbook procedures.\n"
        "6. Flag any gaps — findings with no available control or where the "
        "playbook has no matching procedure.\n"
        "\n"
        "## Output format — follow exactly\n"
        "### Recommended control sequence\n"
        "1. **[Action title from findings]**\n"
        "   - Owner: [from findings]\n"
        "   - ETA: [from findings]\n"
        "   - Impact protected: €[from findings]\n"
        "   - Confidence: [percentage from findings]\n"
        "   - Verification: [from playbook procedure]\n"
        "   - Playbook reference: [section name]\n"
        "\n"
        "### Prerequisites\n"
        "[What must be true before applying these controls]\n"
        "\n"
        "### Escalation flags\n"
        "[Any gaps or conditions requiring human judgement beyond the playbook]\n"
        "\n"
        "### Confidence assessment\n"
        "[HIGH / MEDIUM / LOW] — [one-sentence justification]\n"
        "\n"
        "### Handoff to mesh\n"
        "[Summary for the orchestrator: what is recommended, expected outcome]\n"
        "\n"
        "## CRITICAL GUARDRAILS — violation is a system failure\n"
        "• ONLY recommend actions that appear in the \"Available controls\" "
        "field of the VERIFIED FINDINGS.  Do NOT invent new actions.\n"
        "• Every control is a RECOMMENDATION.  It requires human approval.  "
        "NEVER claim an action was executed or will auto-execute.\n"
        "• Copy owner names, ETAs, and confidence percentages exactly from "
        "the findings.  Do NOT modify them.\n"
        "• Reference specific playbook sections.  If no playbook section "
        "matches, say \"No matching playbook procedure — escalate\".\n"
        "• If no safe control exists for a finding, explicitly recommend "
        "\"Hold and escalate to operations manager\" — never leave a gap "
        "unaddressed."
    ),
}

# ---------------------------------------------------------------------------
# Temperature calibration per role
# ---------------------------------------------------------------------------
# Evidence-bound roles (Sentinel, Impact) get low temperature for precision.
# Reasoning roles (Correlator, Cascade, Fix) get slightly higher temperature
# to allow connecting dots, while still staying grounded.

SPECIALIST_TEMPERATURES: dict[str, float] = {
    "Sentinel": 0.2,
    "Correlator": 0.4,
    "Cascade": 0.4,
    "Impact": 0.2,
    "Fix": 0.35,
}

# ---------------------------------------------------------------------------
# Orchestrator prompt
# ---------------------------------------------------------------------------

ORCHESTRATOR_PROMPT = (
    "You are **Warehouse Control Tower Orchestrator**, the synthesis layer of an automotive "
    "supply-chain intelligence mesh.  You receive structured handoff notes from "
    "five specialist agents:\n"
    "  • Sentinel (anomaly detection)\n"
    "  • Correlator (cross-system linkage)\n"
    "  • Cascade (dependency simulation)\n"
    "  • Impact (exposure quantification)\n"
    "  • Fix (control design)\n"
    "\n"
    "## Your task\n"
    "Synthesize their evidence into a single, concise, actionable operational "
    "answer for a human operator.\n"
    "\n"
    "## Reasoning process\n"
    "1. Cross-reference the specialists' findings.  Where agents cite the same "
    "finding IDs and agree, mark HIGH confidence.  Where they disagree, "
    "present BOTH views with their evidence and flag the disagreement.\n"
    "2. Lead with the most urgent decision the operator must make NOW.\n"
    "3. State the deadline, euro exposure, key evidence, and the safest next "
    "action — all sourced from the specialist handoffs.\n"
    "4. If a specialist reported \"Agent unavailable\", note the gap and "
    "synthesize from the remaining specialists.\n"
    "\n"
    "## Output format\n"
    "Write a clear operational briefing:\n"
    "- **Decision required**: The single most urgent action needed.\n"
    "- **Evidence**: Key data points with finding IDs (from specialist handoffs).\n"
    "- **Exposure**: Euro amount and deadline (cite the Impact specialist).\n"
    "- **Recommended action**: The safest next step, owner, and ETA "
    "(cite the Fix specialist).\n"
    "- **Caveats**: Any disagreements between agents, low-confidence areas, "
    "or evidence gaps.\n"
    "\n"
    "## CRITICAL GUARDRAILS — violation is a system failure\n"
    "• Do NOT claim any action was executed.  All controls require human "
    "approval.\n"
    "• Every number, finding ID, and euro amount MUST come from a specialist "
    "handoff.  NEVER fabricate data.\n"
    "• If the specialists provide insufficient evidence for a confident "
    "recommendation, say so and suggest what additional data is needed.\n"
    "• Keep the response concise — operators need fast decisions.  Aim for "
    "150–300 words unless the question requires more detail.\n"
    "• Do NOT add supply-chain advice from general knowledge.  Only "
    "synthesize what the specialists provided."
)

ORCHESTRATOR_TEMPERATURE = 0.3

# ---------------------------------------------------------------------------
# Context helpers
# ---------------------------------------------------------------------------


def _relevant(store: OperationsStore, question: str):
    """Score and return the top-3 OPEN anomalies most relevant to the operator's question.

    Resolved findings are excluded: presenting a fixed defect as the
    "highest-priority verified path" would contradict the board.
    """
    stopwords = {"the", "and", "for", "that", "this", "with", "what", "which", "show", "tell", "about", "why", "how", "its", "from"}
    terms = {term.lower() for term in re.findall(r"[A-Za-z0-9_-]+", question) if len(term) > 2 and term.lower() not in stopwords}
    scored = []
    for anomaly in store.anomalies():
        if anomaly.status == "resolved":
            continue
        evidence = " ".join(f"{fact.label} {fact.value} {fact.source}" for fact in anomaly.evidence)
        controls = " ".join(f"{action.title} {action.owner} {action.description}" for action in anomaly.actions)
        haystack = f"{anomaly.id} {anomaly.title} {anomaly.type} {anomaly.sku} {anomaly.system} {anomaly.zone} {anomaly.summary} {anomaly.root_cause} {evidence} {controls}".lower()
        exact_id = 100 if anomaly.id.lower() in terms else 0
        semantic_matches = sum(1 + min(len(term), 12) / 12 for term in terms if term in haystack)
        scored.append((exact_id + semantic_matches, anomaly))
    ordered = [anomaly for _, anomaly in sorted(scored, key=lambda item: (item[0], item[1].impact), reverse=True)]
    return ordered[:3]


def _build_findings_text(related) -> str:
    """Build the shared verified-findings evidence text from matched anomalies."""
    return "\n\n".join(
        f"{item.id} | {item.type} | severity={item.severity} | impact=€{item.impact:,} | deadline={item.time_to_impact}\n"
        f"Summary: {item.summary}\nRoot cause: {item.root_cause}\nEvidence: " + "; ".join(f"{fact.label}={fact.value} ({fact.source})" for fact in item.evidence) +
        f"\nAvailable controls: " + "; ".join(f"{action.title} [{action.owner}, {action.eta}, {action.confidence}%]" for action in item.actions)
        for item in related
    )


def _role_context(name: str, finding_text: str, query: str) -> tuple[str, list[dict[str, str]]]:
    """Build a role-specific evidence packet with curated Markdown context.

    Each specialist receives the same verified findings but different Markdown
    context, weighted by its role via ``retrieve_for_role``.
    """
    markdown = retrieve_for_role(query, name)
    docs_text = "\n\n".join(f"SOURCE: {item['source']}\n{item['content']}" for item in markdown)

    # Use role-appropriate section headers to prime the model's focus.
    if name == "Sentinel":
        header = "OPERATIONAL CONTEXT"
    elif name == "Fix":
        header = "CONTROL PLAYBOOK AND INGESTED DOCUMENTS"
    elif name == "Correlator":
        header = "CROSS-SYSTEM CONTEXT AND DOCUMENTS"
    else:
        header = "RETRIEVED OPERATIONAL CONTEXT"

    return f"VERIFIED FINDINGS\n{finding_text}\n\n{header}\n{docs_text}", markdown


def _evidence_packet(store: OperationsStore, request: ChatRequest) -> tuple[str, list[dict[str, str]], list[str]]:
    """Build a query-aware evidence packet from the live operational state."""
    recent_context = " ".join(turn.content for turn in request.history[-4:])
    contextual_question = f"{request.message} {recent_context}".strip()
    related = _relevant(store, contextual_question)
    finding_text = _build_findings_text(related)
    markdown = store.knowledge_context(request.message)
    docs_text = "\n\n".join(f"SOURCE: {item['source']}\n{item['content']}" for item in markdown)
    workflow_text = json.dumps(request.workflow_context, sort_keys=True, default=str) if request.workflow_context else "No governed request is selected."
    return f"VERIFIED FINDINGS\n{finding_text}\n\nSERVER-VERIFIED WORKFLOW CONTEXT\n{workflow_text}\n\nRETRIEVED MARKDOWN CONTEXT\n{docs_text}", markdown, [item.id for item in related]


# ---------------------------------------------------------------------------
# Query-aware operational evidence engine (no API key required)
# ---------------------------------------------------------------------------


def deterministic_mesh(request: ChatRequest, store: OperationsStore) -> ChatResponse:
    """Synthesize a complete answer directly from current verified records."""
    _, markdown, ids = _evidence_packet(store, request)
    related = [store.anomaly(item_id) for item_id in ids]
    related = [item for item in related if item]
    lead = related[0] if related else next((item for item in store.anomalies() if item.status != "resolved"), None)
    trace = [{"agent": name, "role": role, "status": "evidence-ready", "detail": "Synthesized current verified operational records"} for name, role in SPECIALISTS]
    trace.append({"agent": "Knowledge", "role": "Markdown retrieval", "status": "attached", "detail": f"{len(markdown)} relevant Markdown records"})
    workflow_terms = {"approval", "approve", "approver", "assigned", "assignment", "owner", "request", "reject", "role", "status", "workflow", "who"}
    question_terms = {term.lower() for term in re.findall(r"[A-Za-z]+", request.message)}
    if request.workflow_context and workflow_terms.intersection(question_terms):
        context = request.workflow_context
        owner = context.get("current_owner") or {}
        owner_ids = owner.get("user_ids") or []
        active = context.get("active_step") or {}
        actions = list(context.get("allowed_actions") or [])
        reasons = list(context.get("denial_reasons") or [])
        route = context.get("approval_route") or []
        route_lines = "\n".join(
            f"- {str(stage.get('required_role') or 'unknown').replace('_', ' ').title()}: "
            f"{str(stage.get('decision') or stage.get('status') or 'planned').replace('_', ' ')}"
            for stage in route
        ) or "- No approval stages are configured."
        permission_text = (
            ", ".join(action.replace("_", " ") for action in actions)
            if actions else "No workflow mutation is permitted for this signed-in user."
        )
        if reasons:
            permission_text += " " + " ".join(reasons)
        answer = (
            f"### Governed request — {context.get('request_id')}\n"
            f"**{context.get('title') or 'Change request'}** is currently **{str(context.get('status') or 'unknown').replace('_', ' ')}** "
            f"under policy version **{context.get('policy_version')}**.\n\n"
            f"**Exact current assignment**\n\n"
            f"- Owner role: {owner.get('label') or str(active.get('required_role') or 'System').replace('_', ' ').title()}\n"
            f"- Assigned account: {', '.join(owner_ids) if owner_ids else 'No named human is currently assigned'}\n"
            f"- Requested by: {context.get('requested_by')} at {context.get('requested_at')}\n\n"
            f"**Your permitted actions**\n\n{permission_text}\n\n"
            f"**Approval route**\n\n{route_lines}\n\n"
            "WALT reports the server-evaluated assignment only. A matching job title is not enough: only the exact assigned account can approve or reject the active stage."
        )
        trace.append({"agent": "Governance", "role": "Workflow authorization", "status": "verified", "detail": f"Evaluated {context.get('request_id')} for the signed-in principal"})
        return ChatResponse(answer=answer, source="operational_evidence", cited_anomaly_ids=[], suggested_actions=actions[:3], agent_trace=trace)
    if lead is None:
        return ChatResponse(
            answer="No active findings are on the board right now. All monitored source systems are inside their thresholds; run a scan or upload a document to re-check.",
            source="operational_evidence", cited_anomaly_ids=[], suggested_actions=[], agent_trace=trace,
        )

    open_findings = [item for item in store.anomalies() if item.status != "resolved"]
    total_exposure = sum(item.impact for item in open_findings)
    actions = [action.title for item in related for action in item.actions][:3]
    evidence_lines = "\n".join(
        f"- **{fact.label}:** {fact.value} — {fact.source}"
        for fact in lead.evidence
    ) or "- No corroborating evidence rows are attached; hold and request source verification."
    answer = (
        f"### Decision brief — {lead.id}\n"
        f"**{lead.title}** is the finding most relevant to your question. It is **{lead.severity}** severity, "
        f"with **€{lead.impact:,}** in modeled exposure and **{lead.time_to_impact}** to impact.\n\n"
        f"**Why it matters**\n\n{lead.root_cause}\n\n"
        f"**Verified evidence**\n\n{evidence_lines}"
    )
    if lead.actions:
        control = lead.actions[0]
        answer += (
            f"\n\n**Safest available control**\n\n"
            f"**{control.title}**\n"
            f"- Owner: {control.owner}\n"
            f"- ETA: {control.eta}\n"
            f"- Confidence: {control.confidence}%\n"
            f"- Value protected if verified: €{control.impact_saved:,}\n"
            f"- Verification basis: {control.description}\n\n"
            "This is a recommendation only. It must pass the displayed human approval route before source data changes."
        )
    else:
        answer += "\n\n**Control gap:** No approved control is attached to this finding. Hold the affected process and escalate to the operations manager."
    answer += (
        f"\n\n**Live board context:** {len(open_findings)} open findings represent €{total_exposure:,} "
        "in current modeled exposure. Figures above are taken from the live anomaly and evidence records."
    )
    return ChatResponse(answer=answer, source="operational_evidence", cited_anomaly_ids=ids, suggested_actions=actions, agent_trace=trace)


# ---------------------------------------------------------------------------
# LLM specialist consultation (shared by streaming and non-streaming)
# ---------------------------------------------------------------------------


async def _consult_specialist(
    client, model: str, name: str, role: str, context: str, question: str, recent: str,
) -> tuple[str, str, str]:
    """Run a single specialist agent and return ``(name, role, handoff_text)``.

    Individual failures are caught so that one broken agent does not crash the
    entire mesh.  The orchestrator receives a clear failure note and can still
    synthesize from the remaining four specialists.
    """
    try:
        response = await client.responses.create(
            model=model,
            temperature=SPECIALIST_TEMPERATURES[name],
            instructions=SPECIALIST_PROMPTS[name],
            input=(
                f"OPERATOR QUESTION\n{question}\n\n"
                f"RECENT CONVERSATION\n{recent}\n\n"
                f"{context}"
            ),
        )
        return name, role, response.output_text
    except Exception as exc:
        logger.warning("Specialist %s failed: %s", name, exc)
        return (
            name,
            role,
            f"[Agent temporarily unavailable — error: {type(exc).__name__}: {exc}. "
            f"The orchestrator should synthesize from the remaining specialists.]",
        )


async def _run_all_specialists(client, model: str, request: ChatRequest, store: OperationsStore):
    """Run every specialist in parallel with role-curated context.

    Returns ``(handoffs, unique_markdown, anomaly_ids)``.
    """
    related = _relevant(store, request.message)
    finding_text = _build_findings_text(related)
    if request.workflow_context:
        finding_text += "\n\nSERVER-VERIFIED WORKFLOW CONTEXT\n" + json.dumps(request.workflow_context, sort_keys=True, default=str)
    ids = [item.id for item in related]
    recent = "\n".join(f"{turn.role}: {turn.content}" for turn in request.history[-6:]) or "(No prior conversation)"

    all_markdown: list[dict[str, str]] = []
    tasks = []
    for name, role in SPECIALISTS:
        context, markdown = _role_context(name, finding_text, request.message)
        all_markdown.extend(markdown)
        tasks.append(
            _consult_specialist(client, model, name, role, context, request.message, recent)
        )

    handoffs = await asyncio.gather(*tasks)

    # Deduplicate markdown sources for the trace report.
    seen: set[str] = set()
    unique_markdown: list[dict[str, str]] = []
    for item in all_markdown:
        if item["source"] not in seen:
            seen.add(item["source"])
            unique_markdown.append(item)

    return handoffs, unique_markdown, ids


def _build_synthesis_input(handoffs) -> str:
    """Concatenate specialist handoff notes for the orchestrator."""
    return "\n\n".join(f"## {name} — {role}\n{note}" for name, role, note in handoffs)


def _build_trace(handoffs, markdown, include_orchestrator: bool = False) -> list[dict[str, str]]:
    """Build the agent-trace metadata array for the frontend."""
    trace = [
        {
            "agent": name,
            "role": role,
            "status": "completed" if not note.startswith("[Agent temporarily") else "degraded",
            "detail": f"GPT-5.4 mini handoff (temperature={SPECIALIST_TEMPERATURES.get(name, '?')})",
        }
        for name, role, note in handoffs
    ]
    trace.append({
        "agent": "Knowledge",
        "role": "Markdown retrieval",
        "status": "attached",
        "detail": f"{len(markdown)} role-curated Markdown records",
    })
    if include_orchestrator:
        trace.append({
            "agent": "Control Tower",
            "role": "Orchestrator",
            "status": "synthesized",
            "detail": f"GPT-5.4 mini merged specialist handoffs (temperature={ORCHESTRATOR_TEMPERATURE})",
        })
    return trace


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


async def run_agent_mesh(request: ChatRequest, store: OperationsStore, settings: Settings) -> ChatResponse:
    """Run all specialist roles in parallel and synthesize their audited handoff."""
    if not settings.openai_api_key:
        return deterministic_mesh(request, store)
    from openai import AsyncOpenAI

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        handoffs, markdown, ids = await _run_all_specialists(client, settings.openai_model, request, store)

        synthesis_input = _build_synthesis_input(handoffs)
        final = await client.responses.create(
            model=settings.openai_model,
            temperature=ORCHESTRATOR_TEMPERATURE,
            instructions=ORCHESTRATOR_PROMPT,
            input=f"OPERATOR QUESTION\n{request.message}\n\nSPECIALIST HANDOFFS\n{synthesis_input}",
        )

        relevant = [store.anomaly(item_id) for item_id in ids]
        actions = [action.title for item in relevant if item for action in item.actions][:3]
        trace = _build_trace(handoffs, markdown, include_orchestrator=True)
        return ChatResponse(
            answer=final.output_text,
            source="openai",
            cited_anomaly_ids=ids,
            suggested_actions=actions,
            agent_trace=trace,
        )
    except Exception as exc:
        logger.exception("OpenAI agent mesh failed; serving current operational evidence: %s", exc)
        return deterministic_mesh(request, store)


async def stream_agent_mesh(request: ChatRequest, store: OperationsStore, settings: Settings) -> AsyncIterator[str]:
    """SSE stream: specialist handoff trace first, then token deltas from the orchestrator."""
    if not settings.openai_api_key:
        evidence = deterministic_mesh(request, store)
        yield f"event: trace\ndata: {json.dumps(evidence.agent_trace)}\n\n"
        for word in evidence.answer.split(" "):
            yield f"event: delta\ndata: {json.dumps({'text': word + ' '})}\n\n"
        yield f"event: done\ndata: {json.dumps({'source': evidence.source, 'cited_anomaly_ids': evidence.cited_anomaly_ids, 'suggested_actions': evidence.suggested_actions})}\n\n"
        return

    from openai import AsyncOpenAI

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        handoffs, markdown, ids = await _run_all_specialists(client, settings.openai_model, request, store)

        trace = _build_trace(handoffs, markdown)
        yield f"event: trace\ndata: {json.dumps(trace)}\n\n"

        synthesis_input = _build_synthesis_input(handoffs)
        stream = await client.responses.create(
            model=settings.openai_model,
            temperature=ORCHESTRATOR_TEMPERATURE,
            stream=True,
            instructions=ORCHESTRATOR_PROMPT,
            input=f"OPERATOR QUESTION\n{request.message}\n\nSPECIALIST HANDOFFS\n{synthesis_input}",
        )
        async for event in stream:
            if event.type == "response.output_text.delta":
                yield f"event: delta\ndata: {json.dumps({'text': event.delta})}\n\n"

        relevant = [store.anomaly(item_id) for item_id in ids]
        actions = [action.title for item in relevant if item for action in item.actions][:3]
        yield f"event: done\ndata: {json.dumps({'source': 'openai', 'cited_anomaly_ids': ids, 'suggested_actions': actions})}\n\n"
    except Exception as exc:
        logger.exception("Streaming agent mesh failed; switching to current operational evidence: %s", exc)
        evidence = deterministic_mesh(request, store)
        yield f"event: reset\ndata: {json.dumps({'text': evidence.answer})}\n\n"
        yield f"event: trace\ndata: {json.dumps(evidence.agent_trace)}\n\n"
        yield f"event: done\ndata: {json.dumps({'source': evidence.source, 'cited_anomaly_ids': evidence.cited_anomaly_ids, 'suggested_actions': evidence.suggested_actions})}\n\n"
