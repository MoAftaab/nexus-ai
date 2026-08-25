# Product Requirements Document: The Lenny Growth Assistant

**Version:** 1.0  
**Author:** Mohd Aftaab  
**Date:** August 2026  
**Status:** Draft  

---

## Table of Contents

1. [Forward Deployment Brief](#1-forward-deployment-brief)
2. [Product Overview](#2-product-overview)
3. [User Personas & Jobs-To-Be-Done](#3-user-personas--jobs-to-be-done)
4. [Success Metrics](#4-success-metrics)
5. [Assumptions](#5-assumptions)
6. [Scope Choices](#6-scope-choices)
7. [Core Requirements](#7-core-requirements)
8. [Product Tasks & Features](#8-product-tasks--features)
9. [User Flows](#9-user-flows)
10. [Acceptance Criteria](#10-acceptance-criteria)
11. [Risks & Trade-offs](#11-risks--trade-offs)
12. [Deployment & Operational Readiness](#12-deployment--operational-readiness)
13. [Implementation Plan](#13-implementation-plan)

---

## 1. Forward Deployment Brief

### 1.1 User and Problem

**Primary User:** Product managers, growth leads, and startup founders who consume Lenny Rachitsky's podcast content and need actionable, trustworthy advice on product strategy and growth.

**Job to Complete:** The user needs to quickly extract specific, grounded answers from 269+ hours of expert interviews across Lenny's Podcast — without manually searching through transcripts, watching full episodes, or guessing which episode covers their question.

**Pain Removed:**
- **Time waste**: Users currently spend 30–60 minutes scanning episode titles, skimming transcripts, or re-watching episodes to find a single insight. The assistant reduces this to a 10-second conversational query.
- **Knowledge fragmentation**: Insights from different guests on the same topic (e.g., "How to find product-market fit") are scattered across dozens of episodes. The assistant synthesizes cross-episode knowledge into coherent, cited answers.
- **Content creation burden**: Users who want to share Lenny-inspired content spend hours crafting well-structured essays. The "Ship 30 for 30" skill automates this into a polished, publication-ready format.
- **Hallucination anxiety**: Generic ChatGPT answers on product topics are plausible-sounding but ungrounded. This assistant only answers from verified transcript sources, citing episode and guest.

### 1.2 Success Metrics

| Metric | Target | Measurement Method |
|--------|--------|--------------------|
| **Answer Groundedness Rate** | ≥ 90% of answers cite at least one specific transcript source | Automated check: responses must contain source metadata (guest name, episode title) |
| **Retrieval Relevance (Hit Rate)** | ≥ 80% of queries return at least one relevant chunk in top-5 results | Manual evaluation on a 50-question test set + automated MRR scoring |
| **"I Don't Know" Accuracy** | 100% refusal rate for off-topic queries (e.g., "What's the weather?") | Adversarial test set of 20 out-of-scope questions |
| **Time-to-First-Token (TTFT)** | < 3 seconds for cloud LLM, < 8 seconds for local Ollama | Instrumented latency logging on `/chat` endpoint |
| **Session Continuity** | Follow-up questions correctly reference prior context within the session | Manual QA: 10 multi-turn conversation test cases |
| **Ship 30 Essay Quality** | Essays follow all 5 Ship 30 for 30 structural principles | Rubric-based manual evaluation |
| **Evaluator Setup Time** | Clone-to-running in < 5 minutes | Timed walkthrough with fresh machine |

### 1.3 Assumptions

> **IMPORTANT**: These assumptions were made because the client brief was intentionally ambiguous. Each is documented with its rationale and fallback plan.

| # | Assumption | Rationale | Fallback |
|---|-----------|-----------|----------|
| A1 | **Single-user system** — no authentication or multi-tenancy required | The brief says "sessions" but never mentions users, login, or roles. Building auth adds complexity without clear requirements. | If auth is needed, add a simple API key or OAuth layer. Session isolation already exists. |
| A2 | **Transcripts are static** — the 269 episodes in the ChatPRD repo are the complete dataset for this engagement | The brief points to a specific GitHub repo. Real-time podcast ingestion would require YouTube API integration and scheduling. | The ingestion pipeline is designed to be re-runnable. Add new transcripts to the `episodes/` folder and re-index. |
| A3 | **Ollama with a small model (e.g., Llama 3.1 8B or Mistral 7B) is acceptable for local demo** | The brief says "a model that works comfortably on your machine." Consumer hardware (16GB RAM) can't run 70B+ models reliably. | Document which models were tested and their quality trade-offs. Evaluator can swap to a larger model if their hardware supports it. |
| A4 | **PostgreSQL via Supabase (cloud) or local Docker container** | The brief allows Supabase or Railway. Using Supabase for convenience + local Docker fallback for offline evaluation. | Provide both docker-compose (local PG) and Supabase connection string options. |
| A5 | **"Grounded" means the assistant should refuse to answer when retrieval returns no relevant results** | The brief says "acknowledge when the available material does not support an answer." This is a hard constraint, not a suggestion. | The system prompt explicitly instructs the LLM to say "I don't have enough information from Lenny's transcripts to answer this." |
| A6 | **Ship 30 for 30 writing principles are encoded as structured rules, not a vague prompt** | The brief explicitly says: "Read the linked source, identify the relevant writing principles, and encode them in the skill rather than relying on an unstructured one-off prompt." | The skill is a dedicated tool with parameterized rules extracted from the Ship 30 for 30 guide. |
| A7 | **Artifact security is handled via sandboxed iframe rendering with CSP headers** | The brief says "Treat generated HTML as untrusted." Sandboxed iframes with `sandbox` attribute and Content-Security-Policy prevent XSS. | Alternative: server-side HTML sanitization with DOMPurify before rendering. |
| A8 | **The Claude Agent SDK (Python) is the primary agent framework** | The brief offers "Anthropic Claude Agent SDK or Pi Coding Agent." Claude Agent SDK has better Python/FastAPI integration and is better documented. | If Agent SDK has limitations, fall back to direct Anthropic API calls with manual tool routing. |

### 1.4 Scope Choices

#### Included (In Scope)

| Feature | Why Included |
|---------|-------------|
| RAG-based conversational assistant over Lenny's transcripts | Core requirement (Section 4.1) |
| Multi-session chat with independent context | Core requirement (Section 3.1) |
| Session persistence in PostgreSQL | Core requirement (Section 3.1) |
| Ship 30 for 30 content generation skill | Core requirement (Section 4.2) |
| Artifact viewer (Markdown + HTML/CSS) with security | Core requirement (Section 4.3) |
| Cloud LLM integration (Anthropic Claude) | Core requirement (Section 3.2) |
| Local LLM via Ollama (mandatory for demo) | Core requirement (Section 3.2) |
| Model toggle visible in UI | Core requirement (Section 3.2) |
| Docker Compose one-command startup | Core requirement (Section 5) |
| Structured logging and observability | Core requirement (Section 5) |
| Graceful error handling and resilience | Core requirement (Section 5) |
| Source citations in every grounded answer | Core requirement (Section 3.3) |
| Health endpoints | Core requirement (Section 3.1) |
| `.env.example` with safe defaults | Core requirement (Section 5) |

#### Excluded (Out of Scope)

| Feature | Why Excluded |
|---------|-------------|
| User authentication / login | No mention of auth in brief. Single-user assumption (A1). Would add 2+ days of OAuth/JWT work. |
| Real-time transcript ingestion from YouTube | Brief points to static repo. Auto-ingestion needs YouTube Data API, scheduling, and webhook infra. |
| Voice input / TTS output | Not mentioned. Would require Whisper/TTS integration. |
| Mobile-native app | Brief says "web application." Responsive web is sufficient. |
| Fine-tuned models | Overkill for RAG-based approach. Prompt engineering + retrieval is more maintainable. |
| Collaborative / multi-user sessions | Brief only mentions independent sessions, not shared sessions. |
| Analytics dashboard | Nice-to-have but not required. Structured logs provide equivalent diagnostic power. |
| Automated transcript summarization | Brief focuses on Q&A and essay generation, not summarization. |
| Payment / billing | Not a commercial product. |

---

## 2. Product Overview

**The Lenny Growth Assistant** is a full-stack, AI-powered conversational web application that transforms 269 Lenny's Podcast transcripts into an interactive knowledge base. Users can ask complex product management and growth questions, receive source-grounded answers, generate publication-ready Ship 30 for 30 essays, and create rendered Markdown/HTML artifacts — all within a polished chat interface.

### 2.1 Product Vision

> "Every product leader should have instant, trustworthy access to the collective wisdom of the world's best product thinkers — without the friction of searching, watching, or reading 269 episodes."

### 2.2 High-Level Architecture

```mermaid
graph TB
    subgraph "Frontend - Next.js/React"
        UI[Chat Interface]
        AV[Artifact Viewer]
        MT[Model Toggle]
    end

    subgraph "Backend - FastAPI"
        API[REST API Layer]
        SM[Session Manager]
        AG[Agent Layer - Claude Agent SDK]
    end

    subgraph "Agent Skills"
        RAG[RAG QnA Skill]
        S30[Ship 30 for 30 Skill]
        ART[Artifact Generation Skill]
    end

    subgraph "Data Layer"
        PG[(PostgreSQL)]
        VS[(Vector Store - ChromaDB)]
        TR[Transcript Files]
    end

    subgraph "LLM Providers"
        CL[Anthropic Claude API]
        OL[Ollama Local]
    end

    UI --> API
    AV --> API
    MT --> API
    API --> SM
    API --> AG
    AG --> RAG
    AG --> S30
    AG --> ART
    SM --> PG
    RAG --> VS
    VS --> TR
    AG --> CL
    AG --> OL
```

---

## 3. User Personas & Jobs-To-Be-Done

### Persona 1: PM Priya — Mid-level Product Manager

- **Context**: Works at a Series B startup. Listens to Lenny's Podcast on commute but can't recall specific frameworks.
- **JTBD**: "When I'm preparing a product strategy doc, I want to quickly find what experts said about my specific problem, so I can ground my decisions in battle-tested advice."
- **Key Scenario**: Types "What frameworks do experts recommend for prioritizing features?" → Gets a synthesized answer with citations from 3–5 relevant episodes.

### Persona 2: Founder Faisal — Early-stage Startup CEO

- **Context**: Building a B2B SaaS product. Needs tactical growth advice but doesn't have time for 100+ hours of podcast content.
- **JTBD**: "When I'm stuck on a growth challenge, I want specific, actionable advice from people who've solved this problem before, so I can move fast without expensive consultants."
- **Key Scenario**: Types "How did early-stage startups find their first 1000 users?" → Gets a grounded answer with specific examples from guests like Brian Chesky, Lenny himself, etc.

### Persona 3: Content Creator Cara — Growth Newsletter Writer

- **Context**: Writes a weekly newsletter on product and growth topics. Needs fresh, well-structured content.
- **JTBD**: "When I need to write a newsletter issue, I want to turn podcast insights into a polished Ship 30 for 30 essay, so I can publish faster without sacrificing quality."
- **Key Scenario**: Asks a question, gets a grounded answer, then says "Turn this into a Ship 30 for 30 essay" → Gets a ~1,250-word essay with hook, narrative, headings, and takeaway.

---

## 4. Success Metrics

(See Section 1.2 for the complete metrics table with targets and measurement methods.)

### Operational Metrics (for handoff)

| Metric | Target |
|--------|--------|
| API uptime during demo | 99.9% (no crashes during evaluation) |
| Docker Compose startup time | < 2 minutes on first run |
| Log discoverability | Any failure can be diagnosed from structured logs within 60 seconds |
| Configuration change time | Switching LLM provider takes < 30 seconds via env var change |

---

## 5. Assumptions

(See Section 1.3 for the complete assumptions table.)

---

## 6. Scope Choices

(See Section 1.4 for complete inclusion/exclusion tables.)

---

## 7. Core Requirements

### 7.1 API, Sessions, and Persistence

#### 7.1.1 Backend Framework: FastAPI

- All API endpoints built with FastAPI
- Pydantic models for request/response validation
- OpenAPI (Swagger) auto-generated documentation at `/docs`
- CORS configured for frontend origin

#### 7.1.2 Agent Integration: Claude Agent SDK

- Agent layer built using the Anthropic Claude Agent SDK
- Skills/tools registered as discrete agent capabilities:
  - `rag_query` — retrieves and answers from transcript knowledge base
  - `ship30_essay` — generates Ship 30 for 30 formatted essays
  - `generate_artifact` — creates Markdown or HTML/CSS artifacts
- Agent routing determines which skill to invoke based on user intent
- Fallback behavior: if agent routing fails, default to `rag_query`

#### 7.1.3 Session Handling

- **New Session**: `POST /api/sessions` creates a new session with a unique `session_id` (UUID v4)
- **Independent Context**: Each session maintains its own conversation history. Messages from session A never leak into session B.
- **Session Listing**: `GET /api/sessions` returns all sessions with metadata (title, created_at, last_message_at, message_count)
- **Session History**: `GET /api/sessions/{session_id}/messages` returns full message history for a session

#### 7.1.4 Persistence: PostgreSQL

**Database Schema:**

```sql
-- Sessions table
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Messages table
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,  -- stores sources, model used, latency, etc.
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_messages_session_id ON messages(session_id);
CREATE INDEX idx_messages_created_at ON messages(created_at);
CREATE INDEX idx_sessions_updated_at ON sessions(updated_at);

-- Artifacts table
CREATE TABLE artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    message_id UUID REFERENCES messages(id),
    type VARCHAR(20) NOT NULL CHECK (type IN ('markdown', 'html')),
    title VARCHAR(255),
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_artifacts_session_id ON artifacts(session_id);
```

#### 7.1.5 API Quality

**Request/Response Contracts:**

```python
# Chat Request
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    session_id: UUID

# Chat Response
class ChatResponse(BaseModel):
    message_id: UUID
    content: str
    sources: list[SourceCitation]
    artifact: Optional[ArtifactResponse]
    model_used: str
    latency_ms: int

# Source Citation
class SourceCitation(BaseModel):
    guest: str
    episode_title: str
    youtube_url: Optional[str]
    relevance_score: float

# Error Response
class ErrorResponse(BaseModel):
    error: str
    code: str  # e.g., "SESSION_NOT_FOUND", "LLM_UNAVAILABLE"
    detail: Optional[str]
    timestamp: datetime
```

**Structured Errors:**

| HTTP Status | Error Code | When |
|-------------|-----------|------|
| 400 | `INVALID_REQUEST` | Missing/invalid fields |
| 404 | `SESSION_NOT_FOUND` | Invalid session_id |
| 422 | `VALIDATION_ERROR` | Pydantic validation failure |
| 500 | `LLM_ERROR` | Model timeout or API failure |
| 500 | `RETRIEVAL_ERROR` | Vector store unavailable |
| 503 | `SERVICE_UNAVAILABLE` | Database connection failure |

**Health Endpoints:**

```
GET /health          -> {"status": "ok", "timestamp": "..."}
GET /health/ready    -> {"database": "ok", "vector_store": "ok", "llm": "ok|degraded"}
```

### 7.2 Flexible LLM Configuration

#### 7.2.1 Configuration Layer

```python
# config.py
class LLMConfig(BaseModel):
    provider: Literal["anthropic", "ollama"] = "ollama"
    model: str = "llama3.1:8b"
    api_key: Optional[str] = None  # Required for anthropic
    base_url: Optional[str] = "http://localhost:11434"  # For Ollama
    temperature: float = 0.3
    max_tokens: int = 4096
    timeout_seconds: int = 120
```

#### 7.2.2 Cloud LLM: Anthropic Claude

- Model: `claude-sonnet-4-20250514` (or latest available)
- Requires `ANTHROPIC_API_KEY` environment variable
- Used for higher-quality responses when API key is available

#### 7.2.3 Local LLM: Ollama (Mandatory for Demo)

- Default model: `llama3.1:8b` or `mistral:7b` (fits in 16GB RAM)
- Ollama must be running locally on port 11434
- **The submitted demo MUST run using Ollama**

#### 7.2.4 Toggle Behavior

- **UI Indicator**: The current provider and model name are displayed in the chat header (e.g., "Ollama - llama3.1:8b" or "Claude - claude-sonnet-4")
- **Configuration**: Set via `LLM_PROVIDER` and `LLM_MODEL` environment variables
- **Runtime Toggle**: A settings panel or dropdown in the UI allows switching between configured providers without restarting
- **Fallback Behavior**:
  1. If the selected provider is unavailable (e.g., Ollama not running), display a clear error: "Ollama is not available at localhost:11434. Please start Ollama or switch to cloud provider."
  2. Do NOT silently fall back — the user must explicitly choose to switch providers
  3. Log the failure with structured logging

### 7.3 Knowledge Base

#### 7.3.1 Data Source

- **Repository**: [ChatPRD/lennys-podcast-transcripts](https://github.com/ChatPRD/lennys-podcast-transcripts)
- **Content**: 269 episode transcripts in Markdown format with YAML frontmatter
- **Structure**: Each episode has `episodes/{guest-name}/transcript.md` containing:
  - Guest name, episode title, YouTube URL, publish date, description, duration
  - Full text transcript

#### 7.3.2 Ingestion Pipeline

```mermaid
graph LR
    A[Clone/Pull Transcript Repo] --> B[Parse YAML Frontmatter]
    B --> C[Extract Metadata per Episode]
    C --> D[Chunk Transcripts]
    D --> E[Generate Embeddings]
    E --> F[Store in Vector DB]
    F --> G[Build Metadata Index]
```

**Step-by-step:**

1. **Load**: Clone or pull the `ChatPRD/lennys-podcast-transcripts` repo. Read all `transcript.md` files from `episodes/*/` directory.

2. **Parse**: Extract YAML frontmatter (guest, title, youtube_url, publish_date, description) and separate the transcript body text.

3. **Chunk**: Split each transcript into chunks using a semantic chunking strategy:
   - **Chunk size**: ~1,000 tokens (approximately 750 words)
   - **Overlap**: 200 tokens between adjacent chunks to preserve context at boundaries
   - **Chunk boundaries**: Prefer splitting at paragraph/speaker boundaries to keep semantic units intact
   - Each chunk retains a reference to its source episode metadata (guest, title, youtube_url)

4. **Embed**: Generate vector embeddings for each chunk using:
   - **Cloud**: Anthropic's embedding API or OpenAI's `text-embedding-3-small`
   - **Local**: A local embedding model via `sentence-transformers` (e.g., `all-MiniLM-L6-v2`) to avoid API dependency for the demo

5. **Store**: Store embeddings and chunk text in a vector database:
   - **Primary**: ChromaDB (lightweight, embedded, no extra infra)
   - **Alternative**: `pgvector` extension in PostgreSQL (consolidates into one DB)

6. **Index**: Build a metadata index so the system can filter by guest, topic, or date before vector search.

7. **Refresh**: The ingestion script is idempotent — running it again only processes new/modified transcripts. A hash of each transcript file is stored to detect changes.

#### 7.3.3 Source Tracing (Grounding)

Every answer MUST include:
- **Guest name(s)** mentioned in the cited transcript(s)
- **Episode title(s)** with clickable YouTube links
- **Relevance score** (cosine similarity from vector search) — shown internally for debugging, may be shown to user optionally
- If the retrieval returns no results above a relevance threshold (e.g., cosine similarity < 0.3), the assistant MUST respond: *"I don't have enough information from Lenny's transcripts to answer this question confidently."*

---

## 8. Product Tasks & Features

### 8.1 Grounded Conversational Assistant (RAG)

#### Description
A RAG (Retrieval-Augmented Generation) system that answers product management and growth questions strictly from Lenny's Podcast transcripts.

#### Behavior Specification

| Scenario | Expected Behavior |
|----------|-------------------|
| User asks an in-scope question | Retrieve relevant chunks, synthesize answer, cite sources |
| User asks a follow-up question | Use session context to understand "it", "that", pronouns referencing prior Q&A |
| User asks about a topic not in the transcripts | Respond with: "I don't have enough information from Lenny's transcripts to answer this." |
| User asks a completely off-topic question | Respond with: "I'm designed to answer questions about product management and growth based on Lenny's Podcast. I can't help with that topic." |
| User asks a question that spans multiple episodes | Synthesize across relevant chunks from different episodes, cite all sources |
| Retrieval returns low-confidence results | Include a caveat: "Based on limited transcript data, here's what I found..." |

#### System Prompt (Core)

```
You are The Lenny Growth Assistant, an AI-powered expert on product management, 
growth strategy, and startup leadership. Your knowledge comes exclusively from 
Lenny Rachitsky's Podcast transcripts — interviews with world-class product 
leaders and growth experts.

RULES:
1. ONLY answer based on the provided transcript context. Never make up information.
2. ALWAYS cite your sources with guest name and episode title.
3. If the context doesn't contain relevant information, say so explicitly.
4. Maintain conversational context within the session.
5. Be concise but thorough. Use bullet points for clarity.
6. When multiple guests discuss the same topic, synthesize their perspectives.
```

#### Technical Implementation

- **Retrieval**: Top-K vector search (k=5 by default) with metadata filtering
- **Context window**: Concatenate top-K chunks into the LLM context with source metadata tags
- **Re-ranking**: Optional cross-encoder re-ranking for improved relevance (if latency budget allows)
- **Session memory**: Last N messages (default: 10) from the session are prepended to the prompt for continuity

### 8.2 Ship 30 for 30 Content Skill

#### Description
A dedicated agent skill/tool that transforms grounded RAG answers into publication-ready Ship 30 for 30-style essays.

#### Ship 30 for 30 Writing Principles (Encoded from Source)

These principles are extracted from the [Ship 30 for 30 Ultimate Guide](https://www.ship30for30.com/post/how-to-start-writing-online-the-ship-30-for-30-ultimate-guide) and hardcoded into the skill — NOT left as vague instructions to the LLM:

| # | Principle | Implementation in Skill |
|---|-----------|------------------------|
| 1 | **Strong Hook (First Line)** | The essay MUST open with a provocative question, a surprising statistic, or a bold contrarian statement. The hook should create a "curiosity gap" that compels the reader to continue. Template patterns: "Most people think X. They're wrong." / "In [year], [person] did something nobody expected." / "What if everything you knew about X was backwards?" |
| 2 | **Specificity over Generality** | Every claim MUST be tied to a specific guest, a specific episode, a specific number, or a specific framework. No vague statements like "experts say." Instead: "Brian Chesky told Lenny that Airbnb's earliest growth came from..." |
| 3 | **One Clear Takeaway** | The essay MUST end with a single, actionable takeaway the reader can implement today. Format: "The One Thing to Do This Week: [specific action]." |
| 4 | **Skimmable Formatting** | - Use `##` headings every 200-300 words to break the essay into scannable sections. - Use **bold** for key phrases (2-3 per section). - Use bullet lists for steps, frameworks, or lists of 3+ items. - Keep paragraphs to 2-3 sentences max. |
| 5 | **Narrative Progression (4A Framework)** | Structure the essay using one of the 4A paths: **Actionable** (here's how), **Analytical** (here are the numbers), **Aspirational** (yes, you can), or **Anthropological** (here's why). The skill auto-selects the best framework based on the topic. |
| 6 | **Approximately 1,250 Words** | The generated essay should be approximately 1,250 words (plus or minus 150 words). This is the sweet spot for Ship 30 for 30 — long enough for depth, short enough to be read in 5 minutes. |
| 7 | **Proven Approach Structure** | Organize main points using a consistent pattern throughout (e.g., all "Steps," all "Lessons," all "Mistakes"). Never mix organizational patterns within one essay. |

#### Skill Interface

```python
class Ship30Skill:
    """Dedicated Ship 30 for 30 essay generation skill."""
    
    name = "ship30_essay"
    description = "Generate a Ship 30 for 30 style essay from grounded transcript knowledge"
    
    parameters = {
        "topic": str,           # The essay topic (from conversation context)
        "sources": list[dict],  # Grounded sources from RAG retrieval
        "framework": Optional[Literal[
            "actionable", "analytical", "aspirational", "anthropological"
        ]]
    }
    
    def generate(self, topic: str, sources: list, framework: str = None) -> str:
        """
        1. If no framework specified, auto-detect best framework from topic keywords
        2. Retrieve additional relevant chunks for the topic
        3. Build essay prompt with hardcoded Ship 30 for 30 rules
        4. Generate essay with source citations embedded
        5. Validate output: word count, heading count, bold emphasis, takeaway
        6. Return formatted Markdown essay
        """
```

#### Trigger Conditions
The Ship 30 for 30 skill is invoked when the user says:
- "Write a Ship 30 for 30 essay about..."
- "Turn this into a Ship 30 for 30 article"
- "Create an essay about..."
- "Write about [topic] in Ship 30 format"
- Any message containing "ship 30" or "essay" in the context of content creation

### 8.3 Artifact Generation & In-App Viewer

#### Description
When requested, the assistant generates Markdown documents or complete HTML/CSS snippets. These render inside an Artifact Viewer panel beside the chat — similar to Claude's Artifacts feature.

#### Artifact Types

| Type | Format | Use Case |
|------|--------|----------|
| **Markdown** | `.md` with GFM support | Essays, summaries, reports, comparison tables |
| **HTML/CSS** | Complete, self-contained HTML with inline CSS | Styled content, infographics, formatted reports, interactive elements |

#### Artifact Viewer Requirements

1. **Split-pane layout**: Chat on the left (60%), Artifact Viewer on the right (40%). Viewer appears when an artifact is generated.
2. **Markdown rendering**: Full GitHub Flavored Markdown support (headings, bold, italic, lists, code blocks, tables, links).
3. **HTML rendering**: Rendered in a sandboxed `<iframe>` with strict security policies.
4. **Copy/Download**: Users can copy artifact content to clipboard or download as a file.
5. **History**: Artifacts are stored per-session and can be re-viewed.

#### Security: HTML Artifact Rendering

> **CAUTION**: Generated HTML is treated as **untrusted content**. The following isolation strategy is implemented:

**What the viewer PERMITS:**
- Inline CSS styling (colors, fonts, layout, flexbox, grid)
- Standard HTML elements (div, p, h1-h6, span, ul, ol, li, table, img with data URIs)
- Self-contained HTML documents with `<style>` tags

**What the viewer BLOCKS:**
- `<script>` tags and inline JavaScript (`onclick`, `onerror`, etc.) — stripped before rendering
- External resource loading (no `<link>`, `<img src="http://...">`, `<iframe>`)
- `<form>` elements and form submissions
- `<meta>` refresh or redirect tags
- `javascript:` protocol URLs

**Implementation:**
```html
<iframe
  sandbox="allow-same-origin"
  srcdoc="<!-- sanitized HTML -->"
  style="width: 100%; height: 100%; border: none;"
  referrerpolicy="no-referrer"
></iframe>
```

**Defense in depth:**
1. **Server-side**: HTML is sanitized using a whitelist-based sanitizer (e.g., `bleach` or `nh3` in Python) before storage
2. **Client-side**: The iframe `sandbox` attribute restricts script execution
3. **CSP headers**: `Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; img-src data:`

**Why this approach:**
- `sandbox` without `allow-scripts` prevents any JavaScript execution, blocking XSS
- `allow-same-origin` is needed for CSS to work but is safe because scripts are blocked
- Server-side sanitization is the primary defense; iframe sandbox is defense-in-depth
- External resource blocking prevents data exfiltration and tracking pixels

---

## 9. User Flows

### Flow 1: New Conversation then Grounded Q&A

```mermaid
sequenceDiagram
    actor User
    participant UI as Frontend
    participant API as FastAPI
    participant Agent as Agent Layer
    participant VS as Vector Store
    participant LLM as LLM Provider

    User->>UI: Click "New Chat"
    UI->>API: POST /api/sessions
    API->>API: Create session in DB
    API-->>UI: session_id returned
    
    User->>UI: Type question
    UI->>API: POST /api/chat with session_id and message
    API->>API: Store user message
    API->>Agent: Route to RAG skill
    Agent->>VS: Vector search top-5
    VS-->>Agent: Relevant chunks plus metadata
    Agent->>LLM: Prompt with context plus chat history
    LLM-->>Agent: Generated response with citations
    Agent-->>API: Response plus sources
    API->>API: Store assistant message
    API-->>UI: content, sources, model_used
    UI->>User: Display answer with source cards
```

### Flow 2: Ship 30 for 30 Essay Generation

```mermaid
sequenceDiagram
    actor User
    participant UI as Frontend
    participant API as FastAPI
    participant Agent as Agent Layer
    participant S30 as Ship 30 Skill
    participant LLM as LLM Provider

    User->>UI: Write a Ship 30 essay about product-market fit
    UI->>API: POST /api/chat with session_id and message
    API->>Agent: Route to Ship 30 skill
    Agent->>S30: Extract topic and retrieve sources
    S30->>S30: Select 4A framework - Actionable
    S30->>LLM: Essay prompt with rules plus sources
    LLM-->>S30: Generated essay about 1250 words
    S30->>S30: Validate structure and word count
    S30-->>Agent: Formatted essay plus metadata
    Agent-->>API: Response plus artifact
    API->>API: Store message plus artifact in DB
    API-->>UI: content and artifact of type markdown
    UI->>User: Display in chat plus open Artifact Viewer
```

### Flow 3: HTML Artifact Generation

```mermaid
sequenceDiagram
    actor User
    participant UI as Frontend
    participant API as FastAPI
    participant Agent as Agent Layer
    participant LLM as LLM Provider

    User->>UI: Create an HTML comparison table of growth frameworks
    UI->>API: POST /api/chat with session_id and message
    API->>Agent: Route to artifact skill
    Agent->>LLM: Generate HTML/CSS artifact
    LLM-->>Agent: Raw HTML content
    Agent->>Agent: Sanitize HTML server-side
    Agent-->>API: Sanitized artifact
    API->>API: Store artifact in DB
    API-->>UI: content and artifact of type html
    UI->>UI: Render in sandboxed iframe
    UI->>User: Display artifact in viewer panel
```

### Flow 4: Model Switching

```mermaid
sequenceDiagram
    actor User
    participant UI as Frontend
    participant API as FastAPI

    User->>UI: Click model selector dropdown
    UI->>UI: Show available providers
    User->>UI: Select Anthropic Claude
    UI->>API: POST /api/config/llm with provider anthropic
    API->>API: Validate API key exists
    alt API key present
        API-->>UI: status ok, provider anthropic, model claude-sonnet-4
        UI->>User: Update header to show Claude claude-sonnet-4
    else API key missing
        API-->>UI: error ANTHROPIC_API_KEY not configured
        UI->>User: Show error toast
    end
```

---

## 10. Acceptance Criteria

### AC-1: Grounded Q&A

- [ ] User can ask a product/growth question and receive an answer grounded in Lenny's transcripts
- [ ] Every answer includes at least one source citation with guest name and episode title
- [ ] Follow-up questions correctly reference prior conversation context
- [ ] Off-topic questions receive a polite refusal with explanation
- [ ] Questions with no relevant transcript data receive an "I don't know" response
- [ ] Answers are concise, formatted with bullets/headings where appropriate

### AC-2: Session Management

- [ ] User can create a new chat session
- [ ] Each session maintains independent conversation context
- [ ] Session history persists across page refreshes
- [ ] Session list shows title, timestamp, and preview
- [ ] Old sessions can be resumed with full history restored

### AC-3: Ship 30 for 30 Essays

- [ ] User can request a Ship 30 for 30 essay on any topic covered by the transcripts
- [ ] Generated essay is approximately 1,250 words (plus or minus 150)
- [ ] Essay opens with a strong hook (question, statistic, or contrarian statement)
- [ ] Essay uses consistent organizational pattern (all Steps, all Lessons, etc.)
- [ ] Essay includes headings every 200-300 words
- [ ] Essay uses bold for key phrases (2-3 per section)
- [ ] Essay ends with a specific, actionable takeaway
- [ ] All claims are grounded in cited transcript sources
- [ ] Essay renders correctly in the Artifact Viewer

### AC-4: Artifact Viewer

- [ ] Markdown artifacts render with full GFM support (headings, bold, tables, code blocks)
- [ ] HTML artifacts render in a sandboxed iframe beside the chat
- [ ] Script tags are stripped from HTML artifacts
- [ ] External resource loading is blocked
- [ ] Users can copy artifact content to clipboard
- [ ] Users can download artifacts as files
- [ ] Artifact viewer can be opened/closed without losing content
- [ ] Multiple artifacts per session are accessible

### AC-5: LLM Configuration

- [ ] Demo runs successfully on Ollama with a local model
- [ ] At least one cloud provider (Anthropic Claude) is integrated
- [ ] Current provider/model is visible in the UI
- [ ] Switching providers updates the UI indicator
- [ ] Missing Ollama connection shows a clear error (not a crash)
- [ ] Missing API key for cloud provider shows a clear error
- [ ] Model configuration is driven by environment variables

### AC-6: Persistence

- [ ] All conversations are stored in PostgreSQL
- [ ] Session IDs, timestamps, and user metadata are persisted
- [ ] Message content, role, and source citations are persisted
- [ ] Artifacts are persisted and re-viewable
- [ ] Database schema is documented and migrations are provided

### AC-7: API Quality

- [ ] All endpoints have Pydantic request/response validation
- [ ] Invalid requests return structured error responses with error codes
- [ ] `GET /health` returns system status
- [ ] `GET /health/ready` checks database, vector store, and LLM connectivity
- [ ] API documentation is auto-generated at `/docs`

### AC-8: Deployment & Operability

- [ ] `docker-compose up` starts the entire system (or documented equivalent)
- [ ] `.env.example` exists with safe defaults and clear documentation
- [ ] No secrets are committed to the repository
- [ ] Structured logs are emitted for all key operations
- [ ] Failures (DB down, LLM timeout, empty retrieval) are handled gracefully
- [ ] README provides complete setup, run, test, and troubleshoot instructions

---

## 11. Risks & Trade-offs

### Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Hallucination**: LLM generates plausible but unsourced claims | High | Critical | Strict system prompt: "ONLY answer from provided context." Post-generation validation: check if response contains source citations. If not, reject and retry with stricter prompt. |
| **Latency (Local LLM)**: Ollama on consumer hardware is slow (10-30s per response) | High | Medium | Set appropriate timeout (120s). Show typing indicator. Consider streaming responses. Recommend minimum 16GB RAM in docs. Acknowledge latency in UI. |
| **Retrieval Quality**: Vector search returns irrelevant chunks | Medium | High | Use overlap chunking (200 tokens). Implement metadata filtering. Consider hybrid search (vector + keyword BM25). Test with a curated eval set. |
| **Cost (Cloud LLM)**: Anthropic API costs accumulate during development/testing | Medium | Low | Default to Ollama for development. Set API usage alerts. Use smaller context windows where possible. |
| **Local-Model Quality**: 7B/8B models produce lower quality answers than Claude | High | Medium | Accept this trade-off explicitly. Document quality differences. Recommend cloud provider for production use. Focus on retrieval quality to compensate. |
| **Data Leakage**: Transcript content sent to cloud LLM APIs | Low | Medium | Document that transcript chunks are sent to the LLM provider. For sensitive deployments, use Ollama-only mode. |
| **Unsafe Artifact Rendering**: XSS via generated HTML | Medium | Critical | Server-side HTML sanitization (whitelist approach) + sandboxed iframe. Never allow script tags. Block external resources. CSP headers. |
| **Database Connection Failures**: PostgreSQL becomes unavailable | Low | High | Connection pooling with retry logic. Health check endpoint monitors DB. Graceful degradation: chat still works (in-memory) but history isn't saved. |
| **Ollama Not Available**: Evaluator hasn't installed/started Ollama | Medium | High | Clear error message with installation instructions. Health check reports Ollama status. README has step-by-step Ollama setup. |
| **Embedding Model Mismatch**: Different embedding models produce incompatible vectors | Low | High | Pin the embedding model version. Store model name in vector DB metadata. Validate on startup. |

### Key Trade-off Decisions

| Decision | Option A (Chosen) | Option B (Rejected) | Rationale |
|----------|-------------------|---------------------|-----------|
| Vector DB | ChromaDB (embedded) | pgvector (PostgreSQL extension) | ChromaDB requires zero extra setup, works in Docker, and is sufficient for 269 episodes (~50K chunks). pgvector would consolidate into one DB but adds PostgreSQL extension complexity. |
| Embedding Model | `all-MiniLM-L6-v2` (local) | OpenAI `text-embedding-3-small` (API) | Local embedding avoids API dependency for the demo. Quality is slightly lower but acceptable for the transcript corpus size. |
| Chunking Strategy | Fixed-size with overlap (1000 tokens, 200 overlap) | Semantic chunking (by topic) | Fixed-size is simpler, more predictable, and works well with transcript-style content. Semantic chunking adds complexity without proportional benefit for conversational transcripts. |
| Agent Framework | Claude Agent SDK | Raw Anthropic API + manual routing | Agent SDK provides structured tool calling, conversation management, and cleaner skill registration. Manual routing is more flexible but requires more boilerplate. |
| Session Context | Last 10 messages in prompt | Full session in prompt | Full session would quickly exceed context limits for long conversations. Last 10 messages provides adequate context for follow-ups. Older messages are available via retrieval if needed. |

---

## 12. Deployment & Operational Readiness

### 12.1 One-Command Startup

```bash
# Clone the repository
git clone https://github.com/<your-username>/lenny-growth-assistant.git
cd lenny-growth-assistant

# Copy environment template
cp .env.example .env
# Edit .env to add any API keys (optional for Ollama-only mode)

# Start everything
docker-compose up --build
```

**`docker-compose.yml` services:**
- `frontend` — Next.js app on port 3000
- `backend` — FastAPI app on port 8000
- `postgres` — PostgreSQL 16 on port 5432
- `chromadb` — ChromaDB on port 8001 (or embedded in backend)

### 12.2 Configuration

**`.env.example`:**
```env
# === Required ===
DATABASE_URL=postgresql://lenny:lenny@postgres:5432/lenny_assistant

# === LLM Configuration ===
# Provider: "ollama" (default, for demo) or "anthropic"
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1:8b

# Ollama (required when LLM_PROVIDER=ollama)
OLLAMA_BASE_URL=http://localhost:11434

# Anthropic (required when LLM_PROVIDER=anthropic)
# ANTHROPIC_API_KEY=sk-ant-...

# === Optional ===
# Embedding model for RAG
EMBEDDING_MODEL=all-MiniLM-L6-v2

# Vector store
CHROMA_PERSIST_DIR=./data/chroma

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 12.3 Observability

**Structured Logging:**
```json
{
  "timestamp": "2026-08-24T10:30:00Z",
  "level": "INFO",
  "service": "backend",
  "event": "chat_response",
  "session_id": "abc-123",
  "model": "llama3.1:8b",
  "provider": "ollama",
  "retrieval_chunks": 5,
  "relevance_scores": [0.87, 0.82, 0.76, 0.71, 0.65],
  "latency_ms": 4200,
  "token_count": 1240
}
```

**What is logged:**

| Event | Fields | Purpose |
|-------|--------|---------|
| `chat_request` | session_id, message_length | Track usage |
| `retrieval_query` | query, top_k, results_count, scores | Debug retrieval quality |
| `llm_call` | provider, model, prompt_tokens, latency | Monitor model performance |
| `chat_response` | session_id, response_length, sources_count | Verify grounding |
| `artifact_generated` | type, size, sanitized | Track artifact creation |
| `error` | error_code, message, stack_trace | Diagnose failures |
| `health_check` | db_status, vector_status, llm_status | Operational monitoring |

### 12.4 Resilience

| Failure Scenario | Behavior |
|-----------------|----------|
| Missing API keys | Startup continues. Health check reports "degraded" for the provider. Clear error when that provider is selected. |
| Ollama not running | Health check reports "unavailable." Chat returns: "Ollama is not running. Please start Ollama or switch to cloud provider." |
| Model timeout | After 120s, return: "The model took too long to respond. Please try again or switch to a different model." Logged as warning. |
| Empty retrieval results | Response: "I couldn't find relevant information in Lenny's transcripts for this question." No hallucinated answer. |
| Database connection failure | API returns 503 with clear message. Chat can continue in-memory for the current session (degraded mode). |
| Vector store corrupted | Health check detects. Error message suggests re-running ingestion script. |
| Malformed transcript file | Ingestion skips the file, logs a warning, continues with remaining files. |

### 12.5 Handoff Documentation

The README.md and accompanying docs must enable a client engineer to:

1. **Run**: Clone -> `docker-compose up` -> working system in < 5 minutes
2. **Test**: Run automated tests (`pytest`), follow the manual test plan
3. **Troubleshoot**: Check `/health/ready`, read structured logs, diagnose common failures
4. **Extend**: 
   - Add new transcripts: drop files in `episodes/`, re-run ingestion
   - Add new LLM providers: implement the `LLMProvider` interface, add to config
   - Add new agent skills: register a new tool with the Agent SDK
   - Modify essay rules: edit the Ship 30 for 30 skill parameters

---

## 13. Implementation Plan

### Phase 1: Foundation (Backend Core)
- [ ] FastAPI project setup with folder structure
- [ ] PostgreSQL schema + migrations (sessions, messages, artifacts)
- [ ] Database connection pooling and health checks
- [ ] Session CRUD endpoints
- [ ] LLM configuration layer (Ollama + Anthropic toggle)
- [ ] Health endpoints (`/health`, `/health/ready`)
- [ ] Structured logging setup

### Phase 2: Knowledge Base
- [ ] Transcript ingestion script (parse YAML + chunk + embed)
- [ ] ChromaDB vector store setup
- [ ] Embedding generation (local `all-MiniLM-L6-v2`)
- [ ] Vector search endpoint (top-K retrieval)
- [ ] Source citation formatting

### Phase 3: Agent Layer
- [ ] Claude Agent SDK integration
- [ ] RAG Q&A skill (query -> retrieve -> generate -> cite)
- [ ] Ship 30 for 30 essay skill (with hardcoded writing rules)
- [ ] Artifact generation skill (Markdown + HTML)
- [ ] Agent routing logic (intent detection -> skill selection)
- [ ] Session context management (last N messages)

### Phase 4: Frontend
- [ ] Next.js/React project setup
- [ ] Chat interface (message list, input, streaming)
- [ ] Session sidebar (create, list, switch sessions)
- [ ] Model toggle UI (provider selector in header)
- [ ] Artifact Viewer (split-pane, Markdown renderer, sandboxed iframe)
- [ ] Source citation cards
- [ ] Loading/error states
- [ ] Responsive layout

### Phase 5: Integration & Polish
- [ ] End-to-end testing (chat -> retrieval -> response -> display)
- [ ] Docker Compose configuration
- [ ] `.env.example` with documentation
- [ ] Automated tests (API, retrieval, routing, persistence)
- [ ] Manual test plan for UI
- [ ] Error handling and resilience testing
- [ ] Performance optimization (streaming, caching)

### Phase 6: Documentation & Delivery
- [ ] README.md (architecture, setup, run, test, troubleshoot)
- [ ] architecture.md (schema, API, components, flows, security)
- [ ] design.md (UI/UX principles, states, responsive, accessibility)
- [ ] Demo video script and recording
- [ ] Agent transcripts folder cleanup
- [ ] Final code review and security check

---

## Appendix A: API Endpoint Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Basic health check |
| `GET` | `/health/ready` | Detailed readiness check (DB, vector, LLM) |
| `POST` | `/api/sessions` | Create a new chat session |
| `GET` | `/api/sessions` | List all sessions |
| `GET` | `/api/sessions/{id}` | Get session details |
| `DELETE` | `/api/sessions/{id}` | Delete a session |
| `GET` | `/api/sessions/{id}/messages` | Get message history |
| `POST` | `/api/chat` | Send a message and get AI response |
| `GET` | `/api/sessions/{id}/artifacts` | List artifacts for a session |
| `GET` | `/api/artifacts/{id}` | Get a specific artifact |
| `GET` | `/api/config/llm` | Get current LLM configuration |
| `POST` | `/api/config/llm` | Update LLM provider/model |

## Appendix B: Technology Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Frontend | Next.js 14+ / React 18 | SSR, fast development, great DX |
| Styling | Tailwind CSS | Rapid UI development, consistent design |
| Markdown Rendering | `react-markdown` + `remark-gfm` | Full GFM support |
| Backend | FastAPI (Python 3.11+) | Required by brief. Async, fast, auto-docs |
| Agent Framework | Claude Agent SDK | Required by brief. Structured tool calling |
| Database | PostgreSQL 16 | Required by brief. Robust, JSONB support |
| Vector Store | ChromaDB | Lightweight, embedded, Python-native |
| Embeddings | `all-MiniLM-L6-v2` | Local, no API dependency, good quality |
| Cloud LLM | Anthropic Claude (Sonnet) | Required by brief |
| Local LLM | Ollama (Llama 3.1 8B) | Required by brief for demo |
| Containerization | Docker + Docker Compose | One-command startup |
| Testing | pytest + httpx (backend), Jest (frontend) | Standard, well-supported |
| Logging | `structlog` (Python) | JSON structured logging |

## Appendix C: Ship 30 for 30 Essay Template

```markdown
# [Provocative Title That Creates a Curiosity Gap]

[1-2 sentence hook: a surprising claim, question, or contrarian statement]

[1 sentence establishing credibility: who said this, from which episode]

---

## [Section 1: The Problem / Setup]

[2-3 paragraphs establishing the problem or context]
[**Bold key phrases** for scannability]
[Cite specific guest and episode]

## [Section 2: The Insight / Framework]

[2-3 paragraphs presenting the core insight]
- Bullet point 1
- Bullet point 2  
- Bullet point 3

[**Bold key phrases** for scannability]
[Cite specific guest and episode]

## [Section 3: The Evidence / Examples]

[2-3 paragraphs with concrete examples from transcripts]
[Cite specific guest and episode]

## [Section 4: How to Apply This]

[2-3 paragraphs with actionable steps]
1. Step one
2. Step two
3. Step three

---

## The One Thing to Do This Week

[Single, specific, actionable takeaway]

---

*Sources: [Guest 1 - Episode Title](youtube_url), [Guest 2 - Episode Title](youtube_url)*
```
