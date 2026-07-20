# NexusAI multi-agent architecture

NexusAI uses a specialist-agent mesh with one explicit orchestration boundary. Every model
call uses OpenAI `gpt-5.4-mini`; no other LLM provider or model family is configured.

```mermaid
flowchart LR
    D["Generated operational datasets\nMaster · inventory · dispatch · documents · containers"] --> S["Sentinel\nDetection"]
    M["Selected ML detector\nHighest validation F1"] --> S
    S --> C["Correlator\nCross-system linkage"]
    R["Markdown RAG context\nOperational brief + ingested packets"] --> C
    C --> G["Cascade\nDependency simulation"]
    G --> I["Impact\nExposure quantification"]
    I --> F["Fix\nHuman-approved controls"]
    S --> N["Nexus Orchestrator"]
    C --> N
    G --> N
    I --> N
    F --> N
    N --> H["Operator\nChat answer, node map, approval"]
    H --> A["Audit trail"]
```

## Runtime contract

1. Deterministic agents create verified findings from the generated source records.
2. Markdown retrieval selects relevant operational and ingested-document context.
3. With `OPENAI_API_KEY` configured, all five GPT-5.4 mini specialists run in parallel.
4. The Nexus Orchestrator makes one GPT-5.4 mini synthesis call and returns agent handoffs.
5. A human operator must approve state-changing controls. Agent responses cannot alter source
   data directly.

Without a configured key, the same specialist roles return evidence-bound deterministic
handoffs. This preserves a complete demo while never silently substituting another LLM.

