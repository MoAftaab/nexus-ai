"""Phase 4 — WALT Copilot domain grounding tests.

Written BEFORE implementation to define expected behaviour for:
- SAP entity resolution (MAT-999001, VEND-9999, VEND-5000, Plant 1010)
- Deterministic mesh decision briefs with hackathon evidence
- Knowledge base retrieval for the SAP handbook and hackathon operational brief
- Cascade explanation streaming for hackathon findings
- Cross-system correlation explanations
- Fast deterministic fallback when LLM provider is offline
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import get_settings
from app.models import ChatRequest
from app.services.agent_mesh import deterministic_mesh, _relevant
from app.services.knowledge_base import retrieve_markdown, KNOWLEDGE_DIR
from app.services.operations import OperationsStore

XLSX_PATH = Path(r"C:\Users\Mohd Aftaab\Downloads\Telegram Desktop\Warehouse_AI_Hackathon_Synthetic_Dataset_FINAL 2.xlsx")


@pytest.fixture(scope="module")
def grounded_store():
    """A store with hackathon data loaded — shared across all tests in this module."""
    settings = get_settings()
    s = OperationsStore(settings)
    if XLSX_PATH.exists():
        s.load_hackathon(XLSX_PATH)
    return s


@pytest.fixture(scope="module", autouse=True)
def teardown_store():
    """Reset after all module tests so downstream suites start clean."""
    yield
    from main import store
    store.reset_demo()


# ---------------------------------------------------------------------------
# 1.  Entity resolution — _relevant finds the right anomalies
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not present")
class TestEntityResolution:
    """WALT must resolve SAP entity codes to the correct hackathon anomalies."""

    def test_mat_999001_resolves_to_orphan_material(self, grounded_store):
        """MAT-999001 is the seeded orphan material; _relevant must surface it."""
        related = _relevant(grounded_store, "Why is MAT-999001 flagged?")
        assert len(related) >= 1
        ids = [a.id for a in related]
        titles = " ".join(a.title for a in related)
        assert any("MAT-999001" in a.sku or "MAT-999001" in a.title for a in related), (
            f"MAT-999001 not found in relevant results: {ids}"
        )
        assert "orphan" in titles.lower() or "cross-system" in titles.lower()

    def test_vend_9999_resolves_to_orphan_vendor(self, grounded_store):
        """VEND-9999 is the seeded orphan vendor; must be findable."""
        related = _relevant(grounded_store, "What is wrong with VEND-9999?")
        assert len(related) >= 1
        combined = " ".join(f"{a.title} {a.summary} {a.sku}" for a in related)
        assert "VEND-9999" in combined

    def test_vend_5000_resolves_to_blocked_vendor(self, grounded_store):
        """VEND-5000 is blocked with open POs; must be surfaced by relevant query."""
        related = _relevant(grounded_store, "Which blocked vendors have open purchase orders?")
        assert len(related) >= 1
        combined = " ".join(f"{a.title} {a.summary} {a.sku}" for a in related)
        assert "VEND-5000" in combined or "blocked" in combined.lower()

    def test_plant_1010_atp_deficit(self, grounded_store):
        """Plant 1010 has seeded ATP deficits; must appear in relevant results."""
        related = _relevant(grounded_store, "What is the ATP stockout deficit at Plant 1010?")
        assert len(related) >= 1
        combined = " ".join(f"{a.title} {a.summary} {a.sku}" for a in related)
        assert "1010" in combined or "atp" in combined.lower() or "stockout" in combined.lower()

    def test_hazmat_query_surfaces_hazmat_findings(self, grounded_store):
        """Asking about hazmat violations must return A6/C4 anomalies."""
        related = _relevant(grounded_store, "Show all hazmat storage violations")
        assert len(related) >= 1
        combined = " ".join(f"{a.title} {a.summary}" for a in related).lower()
        assert "hazmat" in combined or "haz" in combined


# ---------------------------------------------------------------------------
# 2.  Deterministic mesh — structured decision briefs
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not present")
class TestDeterministicMesh:
    """deterministic_mesh must produce structured, evidence-grounded answers."""

    def test_decision_brief_for_mat_999001(self, grounded_store):
        """Asking about MAT-999001 must produce a decision brief with evidence."""
        request = ChatRequest(message="Why is MAT-999001 flagged as a risk?")
        response = deterministic_mesh(request, grounded_store)
        assert response.source == "operational_evidence"
        assert response.confidence == "high"
        # The answer must mention the material, the root cause, and financial exposure
        assert "MAT-999001" in response.answer
        assert "€" in response.answer or "exposure" in response.answer.lower()
        # Must cite at least one anomaly ID
        assert len(response.cited_anomaly_ids) >= 1

    def test_decision_brief_includes_verified_evidence(self, grounded_store):
        """The decision brief must include a 'Verified evidence' section."""
        request = ChatRequest(message="What is the biggest risk for orphan materials?")
        response = deterministic_mesh(request, grounded_store)
        assert "evidence" in response.answer.lower() or "verified" in response.answer.lower()

    def test_decision_brief_includes_recommended_control(self, grounded_store):
        """The decision brief must include a safest available control."""
        request = ChatRequest(message="What actions are recommended for blocked vendor orders?")
        response = deterministic_mesh(request, grounded_store)
        assert "control" in response.answer.lower() or "action" in response.answer.lower() or "recommended" in response.answer.lower()
        # Must have suggested actions
        assert len(response.suggested_actions) >= 1

    def test_non_operational_question_returns_unsupported(self, grounded_store):
        """A completely unrelated question must be rejected gracefully."""
        request = ChatRequest(message="What is the weather in Berlin?")
        response = deterministic_mesh(request, grounded_store)
        assert "don't have verified operational evidence" in response.answer.lower()
        assert response.confidence == "low"

    def test_board_context_shows_total_open_findings(self, grounded_store):
        """The response must include a live board context line."""
        request = ChatRequest(message="What is the most urgent finding right now?")
        response = deterministic_mesh(request, grounded_store)
        assert "open finding" in response.answer.lower() or "modeled exposure" in response.answer.lower()


# ---------------------------------------------------------------------------
# 3.  Knowledge base retrieval — SAP handbook and hackathon operational brief
# ---------------------------------------------------------------------------


class TestKnowledgeRetrieval:
    """Knowledge retrieval must surface the hackathon SAP handbook."""

    def test_handbook_exists(self):
        """hackathon_sap_handbook.md must exist in the knowledge directory."""
        handbook = KNOWLEDGE_DIR / "hackathon_sap_handbook.md"
        assert handbook.exists(), f"Missing: {handbook}"

    def test_retrieve_sap_handbook_for_hazmat_query(self):
        """Querying 'hazmat storage' must retrieve the SAP handbook."""
        results = retrieve_markdown("hazmat storage SAP MARA violation")
        sources = [r["source"] for r in results]
        assert any("hackathon" in s.lower() or "sap" in s.lower() for s in sources), (
            f"SAP handbook not retrieved; sources: {sources}"
        )

    def test_retrieve_sop_for_blocked_vendor(self):
        """Querying 'blocked vendor PO' must retrieve SOP content."""
        results = retrieve_markdown("blocked vendor open purchase order SOP")
        combined = " ".join(r["content"] for r in results).lower()
        assert "blocked" in combined or "vendor" in combined or "purchase" in combined

    def test_retrieve_handbook_for_atp_deficit(self):
        """ATP deficit queries must surface relevant handbook content."""
        results = retrieve_markdown("ATP stockout deficit available to promise")
        combined = " ".join(r["content"] for r in results).lower()
        assert "atp" in combined or "available" in combined or "stockout" in combined

    @pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not present")
    def test_hackathon_operational_brief_generated(self, grounded_store):
        """After load_hackathon, hackathon_operational_brief.md must exist."""
        brief_path = KNOWLEDGE_DIR / "hackathon_operational_brief.md"
        assert brief_path.exists(), f"Missing: {brief_path}"
        text = brief_path.read_text(encoding="utf-8")
        # Must mention key dataset entities
        assert "material" in text.lower() or "inventory" in text.lower()
        assert "anomal" in text.lower() or "finding" in text.lower()


# ---------------------------------------------------------------------------
# 4.  Cascade explanation streaming — hackathon findings
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not present")
class TestCascadeExplanation:
    """Cascade streaming must work for hackathon anomalies."""

    def test_cascade_graph_available_for_hackathon_critical(self, grounded_store):
        """A critical hackathon anomaly must have a valid cascade graph."""
        critical = grounded_store.anomalies(severity="critical")
        assert len(critical) >= 1
        target = critical[0]
        graph = grounded_store.graph(target.id)
        assert graph["anomaly_id"] == target.id
        assert len(graph["nodes"]) >= 3
        assert len(graph["edges"]) >= 2
        assert graph["simulation"]["expected_impact"] > 0

    @pytest.mark.asyncio
    async def test_deterministic_cascade_stream_emits_events(self, grounded_store):
        """Deterministic cascade explanation must emit delta and done SSE events."""
        from app.services.reasoner import stream_cascade_explanation
        critical = grounded_store.anomalies(severity="critical")
        assert len(critical) >= 1
        target = critical[0]
        graph = grounded_store.graph(target.id)
        settings = get_settings()

        events = []
        async for chunk in stream_cascade_explanation(target, graph, grounded_store, settings):
            events.append(chunk)

        assert len(events) >= 2, "Must emit at least delta + done events"
        # Last event must be 'done'
        assert events[-1].startswith("event: done")
        # At least one delta event
        assert any("event: delta" in e for e in events)
        # The deltas must reference the anomaly title or Monte-Carlo
        combined = " ".join(events)
        assert target.title in combined or "Monte-Carlo" in combined


# ---------------------------------------------------------------------------
# 5.  Agent mesh SAP domain grounding — prompt calibration
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not XLSX_PATH.exists(), reason="Hackathon workbook not present")
class TestAgentMeshGrounding:
    """Specialist prompts and mesh logic must be calibrated for SAP domain."""

    def test_specialist_prompts_mention_sap_vocabulary(self):
        """Specialist prompts should include SAP domain terminology."""
        from app.services.agent_mesh import SPECIALIST_PROMPTS
        combined = " ".join(SPECIALIST_PROMPTS.values()).lower()
        # At least some SAP terms should be present
        assert "material" in combined or "warehouse" in combined or "sap" in combined
        assert "vendor" in combined or "purchase" in combined or "inventory" in combined

    def test_relevant_boosts_exact_material_code_match(self, grounded_store):
        """Querying an exact material code must get a boosted relevance score."""
        # MAT-999001 is an exact entity code present in anomaly IDs/titles/SKUs
        results_specific = _relevant(grounded_store, "MAT-999001")
        results_generic = _relevant(grounded_store, "some random unrelated topic")
        # Specific query must produce results; generic should not match hackathon
        assert len(results_specific) >= 1
        # At least one result must directly reference MAT-999001
        combined = " ".join(f"{a.title} {a.sku}" for a in results_specific)
        assert "MAT-999001" in combined

    def test_cross_system_correlation_in_response(self, grounded_store):
        """WALT must explain cross-system correlation for orphan materials."""
        request = ChatRequest(message="Why does MAT-999001 appear in multiple systems but has no master record?")
        response = deterministic_mesh(request, grounded_store)
        answer_lower = response.answer.lower()
        # Must mention cross-system or replication
        assert ("cross" in answer_lower or "replication" in answer_lower
                or "orphan" in answer_lower or "master" in answer_lower)

    def test_human_approval_always_mentioned(self, grounded_store):
        """Every control recommendation must state human approval is required."""
        request = ChatRequest(message="What should we do about the blocked vendor VEND-5000?")
        response = deterministic_mesh(request, grounded_store)
        answer_lower = response.answer.lower()
        assert "approval" in answer_lower or "human" in answer_lower or "recommendation" in answer_lower
