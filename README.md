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
| Task 3 API (Meeting → SOW) | http://localhost:8003/docs |
| Task 3 SOW Builder UI | http://localhost:8503 |

## Quick Start (Local — no Docker)

```bash
cp .env.example .env        # add your ANTHROPIC_API_KEY and DATABASE_URL
pip install -e task1_knowledge_brain
pip install -e task2_inbox_agent
pip install -e task3_meeting_sow

# Terminal 1 — Task 1
cd task1_knowledge_brain && uvicorn main:app --port 8001 --reload

# Terminal 2 — Task 2
cd task2_inbox_agent && uvicorn main:app --port 8002 --reload

# Terminal 3 — Task 3
cd task3_meeting_sow && uvicorn main:app --port 8003 --reload

# Terminal 4 — UIs (one each)
cd task1_knowledge_brain && streamlit run ui/app.py --server.port 8501
```

## First Run: seed the Knowledge Brain

```bash
# Trigger a full scrape (runs inside Task 1):
curl -X POST http://localhost:8001/api/scrape/full \
     -H "X-API-Key: dev-secret-task1"
```

This takes ~15 minutes on first run (polite 1.5 s delay between pages).  
Daily sync runs automatically at 02:00 UTC and only re-processes changed pages.

## Project structure

```
ai-tech-consultant/
├── task1_knowledge_brain/   Python · FastAPI · ChromaDB · RAG chatbot
├── task2_inbox_agent/       Python · FastAPI · email drafting + learning
├── task3_meeting_sow/       Python · FastAPI · multi-agent SOW pipeline
├── docker-compose.yml
└── .env.example
```

## Architecture in one sentence

Task 1 scrapes, embeds and answers questions.  
Tasks 2 and 3 call Task 1's `/api/query` endpoint — they never touch the vector DB directly.
