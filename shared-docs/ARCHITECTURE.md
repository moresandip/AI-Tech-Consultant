# System Architecture — AI Tech Consultant

## High-Level Topology

```
                               ┌──────────────────────────────────────────────────────────┐
                               │               Task 1: The Knowledge Brain                │
                               │           support.brilliantdirectories.com               │
                               │                                                          │
                               │  [Sitemap] ──> [Polite Scraper] ──> [SHA-256 Hasher]     │
                               │                     │                       │            │
                               │                     ▼                       ▼            │
                               │             [Claude Vision]         [ChromaDB Vector]    │
                               │             (Screenshots)           (Text + Captions)    │
                               │                     │                       │            │
                               │                     └───────┬───────────────┘            │
                               │                             ▼                            │
                               │                    FastAPI :8001                         │
                               │                    POST /api/query                       │
                               │                             ▲                            │
                               └─────────────────────────────┼────────────────────────────┘
                                                             │
                                   ┌─────────────────────────┴────────────────────────────┐
                                   │ Shared REST API Contract                             │
                                   │ (X-API-Key: dev-secret-task1)                        │
                                   └───────────────┬──────────────────────────────┬───────┘
                                                   │                              │
                        ┌──────────────────────────▼───┐             ┌────────────▼────────────────┐
                        │     Task 2: The Inbox Agent  │             │ Task 3: Meeting to Scope    │
                        ├──────────────────────────────┤             ├─────────────────────────────┤
                        │ Inbound Email Webhook (:8002)│             │ Meeting Pipeline API (:8003)│
                        │               │              │             │              │              │
                        │               ▼              │             │              ▼              │
                        │ Claude Haiku 3.5 Classifier  │             │ 1. Transcriber (Long Ctx)   │
                        │ (HOW_TO, BILLING, QUOTE, etc)│             │ 2. Requirements Extractor   │
                        │               │              │             │ 3. Feasibility Checker ─────┼──> Queries Task 1
                        │               ▼              │             │ 4. Hour Estimator           │
                        │ Queries Task 1 /api/query ───┼──> (Facts)  │ 5. SOW Writer (Internal)    │
                        │               │              │             │ 6. Proposal Writer (Opus 4) │
                        │               ▼              │             │ 7. Follow-up Diff Agent     │
                        │ Claude Sonnet 4.5 Drafter    │             │              │              │
                        │               │              │             │              ▼              │
                        │               ▼              │             │ Human Approval Gate         │
                        │ Levenshtein Learning Loop    │             │ (Cannot dispatch unapproved)│
                        │ (20 unedited = Auto-Approve) │             │              │              │
                        │               │              │             │              ▼              │
                        │               ▼              │             │ Streamlit UI (:8503)        │
                        │ Streamlit Review UI (:8502)  │             └─────────────────────────────┘
                        └──────────────────────────────┘
```

## Data Isolation & API Independence
1. **Zero Vector Coupling**: Tasks 2 and 3 do not embed ChromaDB client libraries or touch SQLite directly. They communicate strictly over HTTP using standard JSON.
2. **Deterministic Fallbacks**: If Task 1 is unreachable, Task 2 flags emails for human review; Task 3 flags all requirements as `NEEDS_EXPERT_REVIEW` rather than quoting inaccurate custom code.
3. **Audit Trail**: Every query, draft, feedback edit, and scope change is recorded in PostgreSQL with foreign keys and timestamped logs.
