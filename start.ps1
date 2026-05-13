# Levanta backend y frontend en paralelo
Write-Host "Iniciando Stock Screener..." -ForegroundColor Cyan

$backend = Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$PSScriptRoot\backend'; uvicorn main:app --reload --port 8000" -PassThru
$frontend = Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$PSScriptRoot\frontend'; npm run dev" -PassThru

Write-Host ""
Write-Host "Backend:  http://localhost:8000" -ForegroundColor Green
Write-Host "Frontend: http://localhost:5173" -ForegroundColor Green
Write-Host ""
Write-Host "Presiona Ctrl+C para detener." -ForegroundColor Yellow

Wait-Process -Id $backend.Id, $frontend.Id
