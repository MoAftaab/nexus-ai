from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["critical", "high", "medium", "low"]
AnomalyStatus = Literal["open", "investigating", "resolved"]


class Evidence(BaseModel):
    label: str
    value: str
    source: str


class FixAction(BaseModel):
    id: str
    title: str
    owner: str
    eta: str
    confidence: int = Field(ge=0, le=100)
    status: Literal["recommended", "approved", "applied"] = "recommended"
    description: str
    impact_saved: int


class CascadeNode(BaseModel):
    id: str
    label: str
    kind: Literal["source", "process", "risk", "outcome"]
    health: Literal["critical", "risk", "watch", "healthy"]
    impact: int = 0
    time_to_impact: str = "Monitored"
    detail: str


class CascadeEdge(BaseModel):
    source: str
    target: str
    label: str
    probability: int = Field(ge=0, le=100)


class Anomaly(BaseModel):
    id: str
    title: str
    type: str
    severity: Severity
    status: AnomalyStatus = "open"
    system: str
    zone: str
    sku: str
    detected_at: datetime
    time_to_impact: str
    impact: int
    confidence: int = Field(ge=0, le=100)
    summary: str
    root_cause: str
    evidence: list[Evidence]
    actions: list[FixAction]
    cascade_nodes: list[CascadeNode]
    cascade_edges: list[CascadeEdge]


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=12)


class ChatResponse(BaseModel):
    answer: str
    source: Literal["openai", "nexus_deterministic"]
    cited_anomaly_ids: list[str]
    suggested_actions: list[str]
    agent_trace: list[dict[str, str]] = Field(default_factory=list)


class DocumentInspection(BaseModel):
    document_id: str | None = None
    filename: str
    type: str
    status: Literal["clean", "attention"]
    confidence: int
    summary: str
    fields: list[dict[str, str]]
    mismatches: list[dict[str, str]]
    preview_url: str | None = None
