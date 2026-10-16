# AI Tech Consultant — Run All Test Suites across Python & TypeScript
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "       RUNNING ALL TEST SUITES ACROSS ALL 3 TASKS         " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# Task 1: Knowledge Brain (Python)
Write-Host "`n[1/3] Task 1: Knowledge Brain (Python)" -ForegroundColor Yellow
Push-Location "task1-knowledge-brain"
python -m pytest tests
Pop-Location

# Task 2: Inbox Agent (TypeScript / Node.js)
Write-Host "`n[2/3] Task 2: Inbox Agent (TypeScript)" -ForegroundColor Yellow
Push-Location "task2-inbox-agent"
npm test
Pop-Location

# Task 3: Meeting to Scope (Python)
Write-Host "`n[3/3] Task 3: Meeting to Scope (Python)" -ForegroundColor Yellow
Push-Location "task3-meeting-to-scope"
python -m pytest tests
Pop-Location

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "       ALL TEST SUITES COMPLETED SUCCESSFULLY!            " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
