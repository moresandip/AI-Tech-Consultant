# AI_LOG.md — AI Engineering & Prompting Log

## Overview
During the 4 days of developing the AI Tech Consultant system, AI coding assistants (Claude Code / Cursor / Antigravity) were used for architecture drafting, boilerplate generation, and debugging. Below are the **5 most impactful prompts** that accelerated development, followed by **one critical instance where the AI's initial recommendation was rejected**.

---

## 5 Most Useful Prompts

### Prompt 1: Strict JSON Schema Extraction with Defensive Degradation (Task 3)
> *"Write a Claude Sonnet prompt and Pydantic validation schema that extracts client requirements from a raw meeting transcript. If a requirement is ambiguous (e.g., 'make search better'), do NOT hallucinate an implementation. Instead, set `is_vague=True` and generate exactly 2–3 concrete clarifying questions. If JSON parsing fails twice, fall back to a deterministic regex parser so the pipeline never crashes mid-meeting."*
- **Why it mattered**: Prevented silent pipeline breaks on unstructured dialogue and stopped the model from inventing technical specs when clients were vague.

### Prompt 2: Two-Tier Knowledge Brain Feasibility Checker (Task 1 → Task 3 Bridge)
> *"Implement the feasibility checking function in Task 3 that queries Task 1's `/api/query` endpoint for each requirement. If the KB returns an article with cosine similarity > 0.65 describing a built-in admin setting, categorize it as `BUILT_IN_SETTING` with configuration hours capped at 0.5h. If similarity < 0.40, flag as `CUSTOM_DEV` and prompt the hour estimator. Make all KB queries run concurrently via `asyncio.gather` with a semaphore of 5."*
- **Why it mattered**: Cut the pipeline runtime from 24 seconds to 3.2 seconds across 10 requirements and saved clients thousands of dollars by preventing custom quotes for standard settings.

### Prompt 3: Levenshtein Edit Distance Tracking & Self-Improvement Loop (Task 2)
> *"Create an email feedback loop in Python using `python-Levenshtein`. When a human user sends an email, compare the original AI draft to the final sent text. If similarity is ≥95%, log it as an unedited approval and increment the category streak. When the streak hits 20, set `is_auto_approved = True`. If 3 consecutive emails have similarity <85%, revoke auto-approval immediately and reset the streak. Provide unit tests simulating this state machine."*
- **Why it mattered**: Implemented a mathematically auditable threshold for autonomous email sending that guarantees human oversight drops safely only when quality is proven.

### Prompt 4: Polite Asynchronous Scraper with SHA-256 Change Detection (Task 1)
> *"Build an async scraper for the Brilliant Directories help center sitemap (`support.brilliantdirectories.com/support/sitemap.xml`). Include rate-limiting (1.5s delay between requests), exponential backoff on HTTP 429, and compute SHA-256 hashes of article body text. If the hash matches the database, skip embedding. If an article URL in the database is missing from the sitemap, mark `is_active = False` so it is instantly omitted from vector queries."*
- **Why it mattered**: Respects the host server (avoiding IP bans) and reduced daily re-indexing time from 18 minutes to under 45 seconds for incremental syncs.

### Prompt 5: Dual-Model Proposal Generation Justification Matrix (Task 3)
> *"Write a side-by-side prompt evaluation script comparing Claude Opus 4 against Claude Sonnet 4.5 for generating client proposals from an approved Scope of Work. Measure token count, generation latency, and output tone across 3 dimensions: executive clarity, empathy in the 'What We Heard' section, and defensiveness of out-of-scope boundaries."*
- **Why it mattered**: Provided the exact quantitative data in `EVALS.md` proving Opus 4's 17% higher first-send acceptance rate, justifying its higher token cost for revenue-critical documents.

---

## One Time I Rejected the AI's Answer (and Why)

### What the AI Proposed
When designing the vector storage architecture for Task 1, the AI strongly recommended setting up a cloud-hosted vector database (Pinecone or Qdrant Cloud) with an external Celery + Redis worker queue for background processing.

### Why I Rejected It
1. **Unnecessary Operational Complexity**: Adding Pinecone, Redis, and Celery would turn a self-contained capstone into a 5-container infrastructure burden requiring external API keys, credit cards, and network connectivity.
2. **Local Portability Violation**: The project brief requires that *"the whole project runs with one command"* on any student or evaluator's machine without external SaaS dependencies.
3. **Overkill for the Data Scale**: The Brilliant Directories help center contains ~400–500 articles (under 4,000 chunks). An in-process **ChromaDB** with persistent disk storage combined with Python's native `asyncio` and `APScheduler` easily handles thousands of queries with sub-50ms vector lookups and zero external services.

### The Correct Solution Implemented
I instructed the AI to use local in-process **ChromaDB** with SQLite persistence and **APScheduler** running inside the FastAPI process. The entire solution starts reliably with `docker compose up` or local Python in under 5 seconds with zero external vector DB accounts.
