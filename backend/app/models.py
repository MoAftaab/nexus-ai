from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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
    site_id: str = "wolfsburg"
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
    request_id: str | None = Field(default=None, max_length=80)
    # Populated only by the authenticated API route from live workflow data.
    # Any client-supplied value is overwritten before the mesh is invoked.
    workflow_context: dict[str, object] | None = None


class WaltCommandRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    message: str = Field(min_length=1, max_length=4000)
    # The resolver uses the recent turns only to understand natural follow-ups
    # such as “mail of him?” after “Who is my manager?”. It never treats this
    # client-provided history as authorization or workflow state.
    history: list[ChatTurn] = Field(default_factory=list, max_length=12)
    request_id: str | None = Field(default=None, max_length=80)


class WaltFeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_id: str = Field(min_length=1, max_length=100)
    rating: Literal["helpful", "not_helpful"]
    question: str = Field(default="", max_length=4000)
    answer: str = Field(default="", max_length=10000)


class ChatResponse(BaseModel):
    answer: str
    source: Literal["openai", "operational_evidence"]
    cited_anomaly_ids: list[str]
    suggested_actions: list[str]
    agent_trace: list[dict[str, str]] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"
    source_refs: list[str] = Field(default_factory=list)


class DetailRequestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requested_fields: list[str] = Field(default_factory=list, max_length=20)
    question: str = Field(default="", max_length=1000)
    due_hours: int = Field(default=24, ge=1, le=168)


class DetailResponseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    response: str = Field(min_length=1, max_length=4000)
    evidence_attachments: list[str] = Field(default_factory=list, max_length=20)


class DelegationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assignee_user_id: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=3, max_length=1000)


class WorkflowPreviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=3, max_length=1000)
    recipient_user_id: str | None = Field(default=None, max_length=64)


class WorkflowConfirmationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action_id: str = Field(min_length=1, max_length=64)


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
