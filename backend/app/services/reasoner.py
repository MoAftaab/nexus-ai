"""Compatibility boundary for the API chat endpoint."""
import json

from app.config import Settings
from app.models import ChatRequest, ChatResponse
from app.services.agent_mesh import run_agent_mesh
from app.services.agent_mesh import stream_agent_mesh
from app.services.operations import OperationsStore


async def answer_chat(request: ChatRequest, store: OperationsStore, settings: Settings) -> ChatResponse:
    return await run_agent_mesh(request, store, settings)


async def stream_chat(request: ChatRequest, store: OperationsStore, settings: Settings):
    async for event in stream_agent_mesh(request, store, settings):
        yield event


CASCADE_EXPLAIN_PROMPT = (
    "You are the Cascade specialist of an automotive supply-chain intelligence mesh, "
    "narrating a dependency graph for a warehouse operator.\n"
    "Explain, in 120-180 words of plain operational language: (1) what went wrong at the "
    "source, (2) how it propagates hop by hop — cite each edge's probability from the "
    "graph, (3) when and where the worst consequence lands, and (4) which single control "
    "stops the propagation earliest.\n"
    "GUARDRAILS: use ONLY nodes, edges, probabilities, euro amounts and deadlines present "
    "in the provided graph JSON and finding. Never invent numbers. Controls require human "
    "approval — never claim anything was executed."
)


from app.services.llm_client import get_llm_client


async def stream_cascade_explanation(anomaly, graph_payload: dict, store: OperationsStore, settings: Settings):
    """SSE narration of one cascade graph; uses LLM (OpenAI / AgentRouter Claude) with deterministic fallback."""
    llm_client = get_llm_client(settings)
    if llm_client.active_provider == "deterministic" and not (settings.openai_api_key or settings.agentrouter_api_key):
        edges = graph_payload.get("edges", [])
        chain = " → ".join(f"{edge['source'].split('-')[-1]} ({edge['probability']}%)" for edge in edges)
        if edges:
            chain += f" → {edges[-1]['target'].split('-')[-1]}"
        simulation = graph_payload.get("simulation", {})
        text = (
            f"**{anomaly.title}.** {anomaly.summary} Propagation path: {chain or 'no downstream edges'}. "
            f"Across {simulation.get('trials', 0):,} Monte-Carlo trials the cascade reaches an outcome in "
            f"{simulation.get('propagation_probability', 0) * 100:.0f}% of runs, with €{simulation.get('expected_impact', 0):,} expected exposure. "
            f"Earliest effective control: {anomaly.actions[0].title if anomaly.actions else 'escalate to operations'} — human approval required."
        )
        for word in text.split(' '):
            yield f"event: delta\ndata: {json.dumps({'text': word + ' '})}\n\n"
        yield f"event: done\ndata: {json.dumps({'source': 'nexus_deterministic'})}\n\n"
        return

    graph_facts = {
        "finding": {"id": anomaly.id, "title": anomaly.title, "severity": anomaly.severity, "impact": anomaly.impact, "time_to_impact": anomaly.time_to_impact, "root_cause": anomaly.root_cause},
        "nodes": [{"id": node["id"], "label": node["label"], "kind": node["kind"], "impact": node.get("impact", 0), "detail": node.get("detail", "")} for node in graph_payload.get("nodes", [])],
        "edges": graph_payload.get("edges", []),
        "simulation": graph_payload.get("simulation", {}),
        "available_controls": [{"title": action.title, "owner": action.owner, "eta": action.eta, "confidence": action.confidence} for action in anomaly.actions],
    }
    try:
        async for delta in llm_client.stream(
            instructions=CASCADE_EXPLAIN_PROMPT,
            input_text=f"GRAPH JSON\n{json.dumps(graph_facts)}",
            temperature=0.3,
            max_tokens=1024,
        ):
            yield f"event: delta\ndata: {json.dumps({'text': delta})}\n\n"
        yield f"event: done\ndata: {json.dumps({'source': llm_client.active_provider})}\n\n"
    except Exception:
        edges = graph_payload.get("edges", [])
        chain = " → ".join(f"{edge['source'].split('-')[-1]} ({edge['probability']}%)" for edge in edges)
        if edges:
            chain += f" → {edges[-1]['target'].split('-')[-1]}"
        simulation = graph_payload.get("simulation", {})
        text = (
            f"**{anomaly.title}.** {anomaly.summary} Propagation path: {chain or 'no downstream edges'}. "
            f"Across {simulation.get('trials', 0):,} Monte-Carlo trials the cascade reaches an outcome in "
            f"{simulation.get('propagation_probability', 0) * 100:.0f}% of runs, with €{simulation.get('expected_impact', 0):,} expected exposure. "
            f"Earliest effective control: {anomaly.actions[0].title if anomaly.actions else 'escalate to operations'} — human approval required."
        )
        for word in text.split(' '):
            yield f"event: delta\ndata: {json.dumps({'text': word + ' '})}\n\n"
        yield f"event: done\ndata: {json.dumps({'source': 'nexus_deterministic'})}\n\n"
