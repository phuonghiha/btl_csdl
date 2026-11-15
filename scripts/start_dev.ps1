$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"

Write-Host "Dang khoi dong Backend FastAPI (http://127.0.0.1:8000)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd `"$BackendDir`"; uvicorn app.main:app --reload --port 8000"

Write-Host "Dang khoi dong Frontend React + Vite (http://localhost:5173)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd `"$FrontendDir`"; npm run dev"
