#!/usr/bin/env bash
# AI Tech Consultant — One-Command Startup Script (Bash / Linux / macOS)
set -e

echo "=========================================================="
echo "       AI TECH CONSULTANT — MULTI-AGENT PLATFORM          "
echo "=========================================================="

# 1. Environment Check
if [ ! -f ".env" ]; then
    echo "[!] .env not found. Copying from .env.example..."
    cp .env.example .env
    echo "[+] Created .env file. Please ensure your ANTHROPIC_API_KEY is configured."
fi

# 2. Check if Docker flag passed
if [ "$1" == "--docker" ]; then
    echo "[*] Starting platform via Docker Compose..."
    docker compose up --build
    exit 0
fi

# 3. Local background processes
ROOT_DIR=$(pwd)
echo "[*] Starting Task 1 API on port 8001..."
(cd "$ROOT_DIR/task1_knowledge_brain" && uvicorn main:app --port 8001 --reload) &
PID1=$!

echo "[*] Starting Task 2 API on port 8002..."
(cd "$ROOT_DIR/task2_inbox_agent" && uvicorn main:app --port 8002 --reload) &
PID2=$!

echo "[*] Starting Task 3 API on port 8003..."
(cd "$ROOT_DIR/task3_meeting_sow" && uvicorn main:app --port 8003 --reload) &
PID3=$!

sleep 2

echo "[*] Starting Streamlit UIs (8501, 8502, 8503)..."
(cd "$ROOT_DIR/task1_knowledge_brain" && streamlit run ui/app.py --server.port 8501) &
PID4=$!
(cd "$ROOT_DIR/task2_inbox_agent" && streamlit run ui/app.py --server.port 8502) &
PID5=$!
(cd "$ROOT_DIR/task3_meeting_sow" && streamlit run ui/app.py --server.port 8503) &
PID6=$!

echo ""
echo "All services launched successfully!"
echo "----------------------------------------------------------"
echo "Task 1 (Knowledge Brain)  : http://localhost:8001/docs  | UI: http://localhost:8501"
echo "Task 2 (Inbox Agent)      : http://localhost:8002/docs  | UI: http://localhost:8502"
echo "Task 3 (Meeting to SOW)   : http://localhost:8003/docs  | UI: http://localhost:8503"
echo "----------------------------------------------------------"
echo "Press Ctrl+C to terminate all services."

trap "kill $PID1 $PID2 $PID3 $PID4 $PID5 $PID6 2>/dev/null || true" SIGINT SIGTERM EXIT
wait
