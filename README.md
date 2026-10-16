# AI Tech Consultant

One system that answers product questions, handles customer emails, and turns client meetings into scopes of work.

## Quick Start (Docker — recommended)

```bash
cp .env.example .env        # add your ANTHROPIC_API_KEY
docker compose up --build   # starts all services
```

| Service | URL |
|---------|-----|
| Task 1 API (Knowledge Brain) | http://localhost:8001/docs |
| Task 1 Chatbot UI | http://localhost:8501 |
| Task 2 API (Inbox Agent) | http://localhost:8002/docs |
| Task 2 Inbox UI | http://localhost:8502 |
| Task 3 API (Meeting → Scope) | http://localhost:8003/docs |
| Task 3 SOW Builder UI | http://localhost:8503 |

## Quick Start (Local — One Command)

```powershell
# Windows PowerShell
.\run.ps1
```
```bash
# Linux / macOS / WSL
chmod +x run.sh && ./run.sh
```

## First Run: Seed the Knowledge Brain

```bash
# Trigger a full scrape (runs inside Task 1):
curl -X POST http://localhost:8001/api/scrape/full \
     -H "X-API-Key: dev-secret-task1"
```

This takes ~15 minutes on first run (polite 1.5s delay between pages).  
Daily sync runs automatically at 02:00 UTC and only re-processes changed pages via SHA-256 hashes.

## Project Structure

```
ai-tech-consultant/
├── task1-knowledge-brain/
│   ├── app/                 # API and business logic
│   ├── ingestion/           # Sitemap, crawling, parsing
│   ├── retrieval/           # Chunking, embeddings, search
│   ├── multimodal/          # Image understanding
│   ├── evaluation/          # Knowledge tests
│   └── tests/
├── task2-inbox-agent/
│   ├── src/
│   │   ├── email/            # Input and email classification
│   │   ├── knowledge-client/ # Calls Task 1 API
│   │   ├── drafting/         # Draft generation
│   │   ├── feedback/         # Human edits and learning
│   │   └── evaluation/
│   └── tests/
├── task3-meeting-to-scope/
│   ├── app/                 # API & SOW models
│   ├── agents/              # Separate agent responsibilities
│   ├── transcripts/         # Discovery & follow-up calls
│   ├── scope-diff/          # Compare meeting versions
│   ├── evaluation/          # SOW pipeline evals
│   └── tests/
├── shared-docs/             # Cross-task architecture & API contracts
├── README.md
├── DESIGN.md
├── EVALS.md
└── AI_LOG.md
```

## Architecture in One Sentence

Task 1 scrapes, embeds, and answers questions.  
Tasks 2 and 3 call Task 1's `/api/query` endpoint — they never touch the vector database directly.
