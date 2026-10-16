# AI Tech Consultant — One-Command Startup Script (PowerShell / Windows)
[CmdletBinding()]
param (
    [switch]$Docker = $false,
    [switch]$NoUI = $false
)

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "       AI TECH CONSULTANT — MULTI-AGENT PLATFORM          " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Environment Check
if (-not (Test-Path ".env")) {
    Write-Host "[!] .env file not found. Copying from .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "[+] Created .env file. Please ensure your ANTHROPIC_API_KEY is configured." -ForegroundColor Green
}

# 2. Docker Execution Mode
if ($Docker) {
    Write-Host "[*] Starting platform via Docker Compose..." -ForegroundColor Green
    docker compose up --build
    exit 0
}

# 3. Local Multi-Process Mode
Write-Host "[*] Starting services locally in background processes..." -ForegroundColor Green

$RootPath = (Get-Item -Path ".").FullName

# Start Task 1: Knowledge Brain API (Python FastAPI - Port 8001)
Write-Host "  -> Starting Task 1: Knowledge Brain (Python) on http://localhost:8001" -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$RootPath\task1-knowledge-brain'; uvicorn app.main:app --port 8001 --reload" | Out-Null

# Start Task 2: Inbox Agent (TypeScript Node.js - Port 8002)
Write-Host "  -> Starting Task 2: Inbox Agent (TypeScript / Node.js) on http://localhost:8002" -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$RootPath\task2-inbox-agent'; npm start" | Out-Null

# Start Task 3: Meeting-to-Scope API (Python FastAPI - Port 8003)
Write-Host "  -> Starting Task 3: Meeting to Scope (Python) on http://localhost:8003" -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$RootPath\task3-meeting-to-scope'; uvicorn app.main:app --port 8003 --reload" | Out-Null

if (-not $NoUI) {
    Start-Sleep -Seconds 2
    # Start Task 1 UI (Streamlit)
    Write-Host "  -> Starting Task 1 UI on http://localhost:8501" -ForegroundColor Cyan
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$RootPath\task1-knowledge-brain'; streamlit run app/ui.py --server.port 8501" | Out-Null

    # Start Task 3 UI (Streamlit)
    Write-Host "  -> Starting Task 3 UI on http://localhost:8503" -ForegroundColor Cyan
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$RootPath\task3-meeting-to-scope'; streamlit run app/ui.py --server.port 8503" | Out-Null
}

Write-Host "`nAll services launched successfully!" -ForegroundColor Green
Write-Host "----------------------------------------------------------"
Write-Host "Task 1 (Knowledge Brain - Python)    : http://localhost:8001/docs  | UI: http://localhost:8501"
Write-Host "Task 2 (Inbox Agent - TypeScript)    : API & UI: http://localhost:8002"
Write-Host "Task 3 (Meeting to Scope - Python)   : http://localhost:8003/docs  | UI: http://localhost:8503"
Write-Host "----------------------------------------------------------"
Write-Host "Press Ctrl+C or close child terminal windows to terminate."
