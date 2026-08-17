"""Markdown-first retrieval for operational briefs and ingested supply-chain documents."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re

from app.services.seed import SyntheticDataset


KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / "knowledge"
INGESTED_DIR = KNOWLEDGE_DIR / "ingested"


def _safe_stem(value: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "-", Path(value).stem).strip(".-")
    return safe[:80] or "untitled-document"


def prepare_operational_markdown(data: SyntheticDataset) -> None:
    """Prepare the context files that the agent mesh retrieves, based on live source data."""
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True); INGESTED_DIR.mkdir(parents=True, exist_ok=True)
    critical_docs = [document for document in data.documents if not document["ppap_attached"]]
    lead_drift = max(data.suppliers, key=lambda supplier: supplier["actual_lead"] - supplier["configured_lead"])
    brief = f"""# Current operational brief

Generated at: {data.generated_at.isoformat()}
Dataset seed: {data.seed}

## Operation scope

- {len(data.skus)} automotive parts across {len(data.inventory)} inventory positions
- {len(data.dispatches)} dispatches, {len(data.documents)} document control records, and {len(data.containers)} reusable containers
- Largest supplier lead-time drift: {lead_drift['name']} is configured at {lead_drift['configured_lead']} days and observed at {lead_drift['actual_lead']} days

## Release controls

{''.join(f'- Batch {doc["batch"]} for SKU {doc["sku"]} lacks PPAP evidence and remains blocked for release.\n' for doc in critical_docs) or '- All batches have PPAP evidence.'}

## Data handling

This is generated operational context. Source-system findings must be corroborated with agent evidence before an operator applies a fix.
"""
    controls = """# Warehouse Control Tower AI control playbook

## JIS fitment conflict

Freeze the affected sequence, reconcile ERP and WMS fitment versions, validate the route, then regenerate the controlled sequence. Keep verified material in a safe manual lane while propagation completes.

## Inventory divergence

Reconstruct the transaction sequence from receipt, pick, adjustment and count events. Correct the journal that failed, validate the physical count, then refresh availability planning.

## Release-document gap

Do not release a batch until the required PPAP or VDA evidence is attached and quality has approved the control. Escalate supplier evidence requests before the next production shift.

## Human approval

Warehouse Control Tower AI can recommend a control and record its rationale. An operations owner approves each state-changing action.
"""
    (KNOWLEDGE_DIR / "operational_brief.md").write_text(brief, encoding="utf-8")
    (KNOWLEDGE_DIR / "control_playbook.md").write_text(controls, encoding="utf-8")


def index_document(filename: str, document_type: str, text: str, summary: str, mismatches: list[dict[str, str]]) -> str:
    """Persist one readable markdown record with source metadata for audit-friendly retrieval."""
    INGESTED_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc)
    key = f"{timestamp.strftime('%Y%m%dT%H%M%SZ')}-{_safe_stem(filename)}.md"
    mismatch_rows = "\n".join(f"- **{item['field']}**: document says `{item['document']}`; control expects `{item['system']}` ({item['severity']})" for item in mismatches) or "- No mismatches were detected."
    content = f"""# Ingested document: {filename}

- Indexed at: {timestamp.isoformat()}
- Document type: {document_type}
- Source filename: {filename}

## Inspection summary

{summary}

## Cross-check result

{mismatch_rows}

## Extracted text

{text[:18000] if text.strip() else '(No readable text was extracted.)'}
"""
    (INGESTED_DIR / key).write_text(content, encoding="utf-8")
    return key


def retrieve_markdown(query: str, limit: int = 4, max_chars: int = 6000) -> list[dict[str, str]]:
    """Return the most lexically relevant Markdown records; no external vector service needed."""
    terms = {term.lower() for term in re.findall(r"[a-zA-Z0-9-]{3,}", query)}
    candidates = []
    for path in KNOWLEDGE_DIR.rglob("*.md"):
        if path.name == "README.md":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        score = sum(text.lower().count(term) for term in terms)
        if score:
            candidates.append((score, path.name, text))
    if not candidates:
        for name in ("operational_brief.md", "control_playbook.md"):
            path = KNOWLEDGE_DIR / name
            if path.exists():
                candidates.append((0, path.name, path.read_text(encoding="utf-8")))
    return [{"source": name, "content": text[:max_chars]} for _, name, text in sorted(candidates, key=lambda item: (-item[0], item[1]))[:limit]]


# ---------------------------------------------------------------------------
# Role-based retrieval for the specialist agent mesh
# ---------------------------------------------------------------------------

_ROLE_PRIORITIES: dict[str, dict[str, int]] = {
    "Monitor Agent": {"operational_brief.md": 3, "control_playbook.md": 0},
    "Investigator Agent": {"operational_brief.md": 2, "control_playbook.md": 1},
    "Advisor Agent": {"operational_brief.md": 3, "control_playbook.md": 2},
    "Approval Agent": {"operational_brief.md": 1, "control_playbook.md": 3},
    "Audit Agent": {"operational_brief.md": 2, "control_playbook.md": 2},
    "Copilot Agent": {"operational_brief.md": 3, "control_playbook.md": 3},
    "Sentinel": {"operational_brief.md": 3, "control_playbook.md": 0},
    "Correlator": {"operational_brief.md": 2, "control_playbook.md": 1},
    "Cascade": {"operational_brief.md": 3, "control_playbook.md": 1},
    "Impact": {"operational_brief.md": 3, "control_playbook.md": 1},
    "Fix": {"operational_brief.md": 1, "control_playbook.md": 3},
}


def retrieve_for_role(query: str, role: str, limit: int = 4, max_chars: int = 6000) -> list[dict[str, str]]:
    """Return Markdown context prioritised for a specific specialist role.

    Each role has a boost map that up-weights the documents most relevant to its
    responsibility (e.g. the Fix agent sees the control playbook first, while
    Sentinel focuses on the operational brief and raw signals).  Ingested
    documents get an automatic boost for the Fix and Correlator roles because
    they carry cross-check and release evidence.
    """
    terms = {term.lower() for term in re.findall(r"[a-zA-Z0-9-]{3,}", query)}
    priorities = _ROLE_PRIORITIES.get(role, {})
    candidates: list[tuple[float, str, str]] = []
    for path in KNOWLEDGE_DIR.rglob("*.md"):
        if path.name == "README.md":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        lexical_score = sum(text.lower().count(term) for term in terms)
        role_boost = priorities.get(path.name, 1)
        # Boost ingested documents for roles that consume cross-check evidence.
        if path.parent == INGESTED_DIR and role in {"Fix", "Correlator"}:
            role_boost = max(role_boost, 2)
        combined = lexical_score * max(role_boost, 1) + role_boost
        if combined > 0:
            candidates.append((combined, path.name, text))
    if not candidates:
        for name in ("operational_brief.md", "control_playbook.md"):
            path = KNOWLEDGE_DIR / name
            if path.exists():
                candidates.append((priorities.get(name, 0), path.name, path.read_text(encoding="utf-8")))
    return [{"source": name, "content": text[:max_chars]} for _, name, text in sorted(candidates, key=lambda item: (-item[0], item[1]))[:limit]]


def list_ingested_documents() -> list[dict[str, str]]:
    """Return a compact, audit-safe list of Markdown records available to retrieval."""
    if not INGESTED_DIR.exists():
        return []
    return [{"id": path.name, "name": path.stem, "indexed_at": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()} for path in sorted(INGESTED_DIR.glob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True) if path.name != ".gitkeep"]
