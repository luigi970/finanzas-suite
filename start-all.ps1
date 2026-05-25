# start-all.ps1 — arranca maximos + finanzas sin ventanas visibles

$Root = $PSScriptRoot
$LogDir = "$Root\logs"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory $LogDir | Out-Null }

function Wait-Http($url, $label, $maxSecs = 30) {
    Write-Host "  Esperando $label..." -NoNewline
    for ($i = 0; $i -lt $maxSecs; $i++) {
        try {
            Invoke-WebRequest $url -TimeoutSec 1 -UseBasicParsing -ErrorAction Stop | Out-Null
            Write-Host " OK" -ForegroundColor Green
            return
        } catch { Start-Sleep 1; Write-Host -NoNewline "." }
    }
    Write-Host " timeout (ver logs/)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "  maximos + finanzas" -ForegroundColor Cyan
Write-Host ""

# Backends
Start-Process powershell -WindowStyle Hidden -ArgumentList `
    "-Command", "cd '$Root\backend'; uvicorn main:app --port 8000 > '$LogDir\maximos-backend.log' 2>&1"

Start-Process powershell -WindowStyle Hidden -ArgumentList `
    "-Command", "cd '$Root\finanzas\backend'; uvicorn main:app --port 8001 > '$LogDir\finanzas-backend.log' 2>&1"

# Frontends
Start-Process powershell -WindowStyle Hidden -ArgumentList `
    "-Command", "cd '$Root\frontend'; npm run dev > '$LogDir\maximos-frontend.log' 2>&1"

Start-Process powershell -WindowStyle Hidden -ArgumentList `
    "-Command", "cd '$Root\finanzas\frontend'; npm run dev > '$LogDir\finanzas-frontend.log' 2>&1"

# Esperar backends
Wait-Http "http://localhost:8001/api/health" "finanzas"
Wait-Http "http://localhost:8000/api/status" "maximos (opcional)"

# Abrir browser
Write-Host ""
Write-Host "  Abriendo finanzas en http://localhost:5174" -ForegroundColor Cyan
Start-Process "http://localhost:5174"

Write-Host ""
Write-Host "  Todo corriendo. Logs en .\logs\" -ForegroundColor Green
Write-Host "  Para detener: .\stop-all.ps1" -ForegroundColor Yellow
Write-Host ""
