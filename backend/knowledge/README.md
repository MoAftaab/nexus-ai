# NexusAI knowledge workspace

This folder is the retrieval layer for the operations copilot. On startup, NexusAI
generates a concise Markdown operational brief and control playbook from the same synthetic
dataset used by the API. Uploaded documents are parsed, cross-checked, and stored as Markdown
records under `ingested/` with a timestamp and source filename.

Retrieval is intentionally local and lexical for this hackathon build: it keeps uploaded data
inside the application and does not need a second model or a vector provider. Relevant Markdown
excerpts are passed to the GPT-5.4 mini specialist mesh only when an operator asks a question.

