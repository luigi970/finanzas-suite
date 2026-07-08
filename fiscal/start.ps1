# start.ps1 — arranca el asistente fiscal (backend 8002 + frontend 5175)

$Root   = $PSScriptRoot
$LogDir = "$Root\..\logs"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory $LogDir | Out-Null }

Write-Host ""
Write-Host "  fiscal — asistente fiscal" -ForegroundColor Cyan
Write-Host ""

Start-Process powershell -WindowStyle Hidden -ArgumentList `
    "-Command", "cd '$Root\backend'; uvicorn main:app --port 8002 > '$LogDir\fiscal-backend.log' 2>&1"

Start-Process powershell -WindowStyle Hidden -ArgumentList `
    "-Command", "cd '$Root\frontend'; npm run dev > '$LogDir\fiscal-frontend.log' 2>&1"

Write-Host "  Iniciando..." -ForegroundColor Yellow
Start-Sleep 3
Start-Process "http://localhost:5175"
Write-Host "  http://localhost:5175" -ForegroundColor Green
Write-Host ""
