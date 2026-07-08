# start-all.ps1 — arranca maximos + finanzas sin ventanas visibles

$Root = $PSScriptRoot
$LogDir = "$Root\logs"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory $LogDir | Out-Null }

function Wait-Port($port, $label, $maxSecs = 40) {
    Write-Host "  Esperando $label..." -NoNewline
    for ($i = 0; $i -lt $maxSecs; $i++) {
        $ok = Test-NetConnection -ComputerName localhost -Port $port -InformationLevel Quiet -WarningAction SilentlyContinue
        if ($ok) { Write-Host " OK" -ForegroundColor Green; return }
        Start-Sleep 1; Write-Host -NoNewline "."
    }
    Write-Host " timeout (ver logs\)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "  maximos + finanzas + fiscal" -ForegroundColor Cyan
Write-Host ""

# Backends
Start-Process powershell -WindowStyle Hidden -ArgumentList `
    "-Command", "cd '$Root\maximos\backend'; uvicorn main:app --port 8000 > '$LogDir\maximos-backend.log' 2>&1"

Start-Process powershell -WindowStyle Hidden -ArgumentList `
    "-Command", "cd '$Root\finanzas\backend'; uvicorn main:app --port 8001 > '$LogDir\finanzas-backend.log' 2>&1"

# Frontends
Start-Process powershell -WindowStyle Hidden -ArgumentList `
    "-Command", "cd '$Root\maximos\frontend'; npm run dev > '$LogDir\maximos-frontend.log' 2>&1"

Start-Process powershell -WindowStyle Hidden -ArgumentList `
    "-Command", "cd '$Root\finanzas\frontend'; npm run dev > '$LogDir\finanzas-frontend.log' 2>&1"

Start-Process powershell -WindowStyle Hidden -ArgumentList `
    "-Command", "cd '$Root\fiscal\backend'; uvicorn main:app --port 8002 > '$LogDir\fiscal-backend.log' 2>&1"

Start-Process powershell -WindowStyle Hidden -ArgumentList `
    "-Command", "cd '$Root\fiscal\frontend'; npm run dev > '$LogDir\fiscal-frontend.log' 2>&1"

# Esperar a que los puertos estén escuchando
Wait-Port 8001 "finanzas backend"
Wait-Port 8000 "maximos backend (opcional)"
Wait-Port 5174 "finanzas frontend"
Wait-Port 5175 "fiscal frontend (opcional)"

# Abrir browser
Write-Host ""
Write-Host "  Abriendo apps..." -ForegroundColor Cyan
Start-Process "http://localhost:5174"
Start-Process "http://localhost:5173"
Start-Process "http://localhost:5175"

Write-Host ""
Write-Host "  Todo corriendo. Logs en .\logs\" -ForegroundColor Green
Write-Host "  Para detener: .\stop-all.ps1" -ForegroundColor Yellow
Write-Host ""
