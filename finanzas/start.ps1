Write-Host "Arrancando Finanzas Personales..." -ForegroundColor Cyan

# Backend
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\backend'; python -m uvicorn main:app --reload --port 8001"

# Frontend
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\frontend'; npm run dev"

Write-Host ""
Write-Host "Backend:  http://localhost:8001" -ForegroundColor Green
Write-Host "Frontend: http://localhost:5174" -ForegroundColor Green
