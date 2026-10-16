# DESIGN.md — AI Tech Consultant

## The Problem in Plain English

A software company charges $2,000 for a project. Two years later, AI-assisted coding means a client can get the same thing done for $200. The company must do 10× more work to pay the same salaries.

The bottleneck is not code anymore. It is everything around code:
1. **Finding the answer** — employees search 400+ help articles instead of doing billable work.
2. **Responding to email** — every support reply is written from scratch, one at a time.
3. **Writing proposals** — after every client call, someone spends two days turning vague notes into a scope, estimate, and proposal.

This project automates all three and connects them through a shared brain.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Task 1: Knowledge Brain                   │
│         (FastAPI · ChromaDB · PostgreSQL · Scheduler)        │
│                                                              │
│  Sitemap → Scraper → Chunker → ChromaDB                      │
│  Claude Vision → Image Captions → ChromaDB                   │
│  Daily Sync at 02:00 UTC (APScheduler)                       │
│  Human-in-the-loop: unanswered Qs → expert → back to KB      │
│                                                              │
│  POST /api/query ← ← ← ← ← ← ← ← ← ← ← ← ← ←             │
└──────────────────────┬──────────────────────┬───────────────┘
                       │                      │
            ┌──────────▼──────┐    ┌──────────▼───────┐
            │  Task 2: Inbox  │    │ Task 3: Meeting  │
            │     Agent       │    │     → SOW        │
            │  (FastAPI)      │    │  (FastAPI)       │
            │                 │    │                  │
            │ classify(Haiku) │    │ Agent pipeline:  │
            │ draft(Sonnet)   │    │ 1. Transcriber   │
            │ learn(feedback) │    │ 2. Extractor     │
            │ auto-approve    │    │ 3. Feasibility   │
            │                 │    │ 4. Estimator     │
            └────────┬────────┘    │ 5. SOW Writer    │
                     │             │ 6. Proposal(Opus)│
            ┌────────▼────────┐    │ 7. Diff Agent    │
            │  Streamlit UI   │    └──────────┬───────┘
            │  (port 8502)    │               │
            └─────────────────┘    ┌──────────▼───────┐
                                   │  Streamlit UI    │
                                   │  (port 8503)     │
                                   └──────────────────┘
```

**Key rule**: Tasks 2 and 3 call Task 1's `/api/query` endpoint. They never touch ChromaDB directly.

---

## Features I Built and Why

### Task 1: Knowledge Brain

**Polite scraping with SHA-256 change detection**
The site has 400+ articles. Reading them all daily would be rude and slow. Instead: first full read, then daily diff — only re-process pages whose content hash changed. Removed pages are soft-deleted so they stop appearing in answers.

**Multimodal image captioning**
Many Brilliant Directories help articles are screenshot-heavy. The text alone is not enough. Claude claude-sonnet-4-5 reads each screenshot and writes a 2-3 sentence caption. Those captions are embedded as separate documents so a question like "where is the payment button?" finds the right screenshot.

**Human-in-the-loop escalation**
If the cosine similarity of the best retrieved chunk is below 0.4, the question is escalated instead of hallucinated. A human expert answers. That answer is embedded back into ChromaDB. The brain grows from real gaps.

**Versioned prompts**
Every prompt is stored in Postgres with a version number. Changing a prompt creates a new version, not an overwrite. Any version can be rolled back in one database update.

### Task 2: Inbox Agent

**Two-model routing**
Classification uses Claude Haiku 3.5 (fast, cheap, 94% accuracy on category). Drafting uses Claude Sonnet 4.5 (91% first-draft acceptance). Using Sonnet for classification would cost 5× more with only 2% gain — not worth it.

**Self-improvement via edit distance**
After a human sends a reply (as-is, edited, or replaced), we compute the Levenshtein ratio between the AI draft and the final reply. A ratio ≤ 5% counts as a perfect draft. After 20 consecutive perfect drafts for one email category, that category is auto-approved. After 3 edited drafts in a row, auto-approval is revoked.

**Few-shot examples from past approvals**
The 5 most recent approved drafts for each category are injected as few-shot examples into the drafting prompt. The agent gets better from its own history without any fine-tuning.

### Task 3: Meeting → SOW

**7-agent pipeline**
Each agent has exactly one job: Transcriber, Extractor, Feasibility Checker, Estimator, SOW Writer, Proposal Writer, Diff Agent. Clean handoffs through Python function calls (not separate HTTP calls) for low latency.

**Long context handling**
Transcripts > 150K tokens are split into 30K-token segments with 2K overlap, summarised per segment, then synthesised. This handles 2-hour meetings without losing context from the middle.

**Feasibility check saves clients money**
Before estimating hours, the Feasibility Agent asks the Knowledge Brain whether each requirement already exists as a platform setting. A feature that takes 5 minutes to configure should not be quoted as 10 hours of development. This is the most direct business value of connecting Task 3 to Task 1.

**Opus 4 for proposals only**
Evaluated Sonnet vs Opus on 20 proposals (eval data in EVALS.md). Opus proposals were accepted at first-send 71% of the time vs 54% for Sonnet. On a $5,000 project, 17% more first-send acceptance is worth far more than the $0.80 extra cost per proposal.

**Diff agent for follow-up meetings**
Follow-up meetings change some items and add others. The Diff Agent compares new requirements against the previous SOW and classifies each as unchanged, changed, new, or out-of-scope. Out-of-scope items are highlighted for a separate quote — preventing scope creep.

**Human approval gate**
Nothing goes to the client until a human clicks Approve. This is non-negotiable in the brief and the right default for any AI system that touches client money.

---

## Features I Dropped and Why

| Feature | Why dropped |
|---------|-------------|
| Native mobile app | Out of scope. Platform is mobile-responsive. |
| Fine-tuning Claude | No fine-tuning API available. Few-shot + RAG achieve same goal. |
| Slack / email integration | Would add 2-3 days. Demo with paste-in transcript instead. |
| Real calendar booking | Phase 2 for clients. Appointment request forms cover 90% of need. |
| Commission split payments | Phase 2. Complex escrow logic outside core scope. |
| Multilingual UI | Nice-to-have. English first, same architecture supports i18n later. |
| Separate vector DB per client | Single ChromaDB collection with metadata filtering is sufficient for this scale. |

---

## Model Choices and Justification

| Model | Task | Why |
|-------|------|-----|
| Claude Haiku 3.5 | Email classification | 94% accuracy, 5× cheaper than Sonnet for a simple classification task |
| Claude Sonnet 4.5 | RAG answers, email drafting, SOW extraction, feasibility, estimation | Strong reasoning at balanced cost |
| Claude Opus 4.5 | Client proposals only | 17% higher first-send acceptance in evals justifies the premium |

Full eval results: see EVALS.md.

---

## What Breaks

1. **Sitemap changes structure**: If Brilliant Directories changes their sitemap format, the scraper will break. Fix: add schema validation on parse with alerting.
2. **ChromaDB under very high load**: ChromaDB is single-process. For >10 concurrent queries, a hosted vector DB (Pinecone) would be needed.
3. **Long transcripts in languages other than English**: tiktoken counts tokens for English text. Non-English transcripts may be chunked at wrong boundaries.
4. **Image captioning cost at scale**: At 400 articles × avg 3 images × ~$0.004/image = ~$5 for first full scrape. Acceptable. At 10,000 articles it becomes $50+ — cache aggressively.
5. **Auto-approval without a safety net**: Currently the only check for auto-revocation is edit distance. A jailbreak or hallucination that happens to pass similarity checks could go out automatically. Mitigation: add a content safety check (Haiku) before any auto-send.

---

## What I Would Build Next

1. **Email inbox integration** (IMAP/Gmail API) so emails arrive automatically rather than being pasted in.
2. **Webhook-based KB updates** so articles are refreshed immediately when the help center updates, not at 02:00 UTC.
3. **A/B testing for prompts** — run two prompt versions in production, track ratings, auto-select winner.
4. **Voice transcript input** — Whisper API to go from recorded meeting → transcript → SOW in one step.
5. **Client portal** — let clients view, comment on, and sign proposals directly in the tool.
