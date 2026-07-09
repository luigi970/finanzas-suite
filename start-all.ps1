# start-all.ps1 — arranca toda la suite (launcher + maximos + finanzas + fiscal)

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
Write-Host "  finanzas suite — iniciando todos los procesos" -ForegroundColor Cyan
Write-Host ""

# Launcher (hub de configuración)
Start-Process powershell -WindowStyle Hidden -ArgumentList `
    "-Command", "cd '$Root\launcher\backend'; uvicorn main:app --port 8099 > '$LogDir\launcher-backend.log' 2>&1"

Start-Process powershell -WindowStyle Hidden -ArgumentList `
    "-Command", "cd '$Root\launcher\frontend'; npm run dev > '$LogDir\launcher-frontend.log' 2>&1"

# maximos
Start-Process powershell -WindowStyle Hidden -ArgumentList `
    "-Command", "cd '$Root\maximos\backend'; uvicorn main:app --port 8000 > '$LogDir\maximos-backend.log' 2>&1"

Start-Process powershell -WindowStyle Hidden -ArgumentList `
    "-Command", "cd '$Root\maximos\frontend'; npm run dev > '$LogDir\maximos-frontend.log' 2>&1"

# finanzas
Start-Process powershell -WindowStyle Hidden -ArgumentList `
    "-Command", "cd '$Root\finanzas\backend'; uvicorn main:app --port 8001 > '$LogDir\finanzas-backend.log' 2>&1"

Start-Process powershell -WindowStyle Hidden -ArgumentList `
    "-Command", "cd '$Root\finanzas\frontend'; npm run dev > '$LogDir\finanzas-frontend.log' 2>&1"

# fiscal
Start-Process powershell -WindowStyle Hidden -ArgumentList `
    "-Command", "cd '$Root\fiscal\backend'; uvicorn main:app --port 8002 > '$LogDir\fiscal-backend.log' 2>&1"

Start-Process powershell -WindowStyle Hidden -ArgumentList `
    "-Command", "cd '$Root\fiscal\frontend'; npm run dev > '$LogDir\fiscal-frontend.log' 2>&1"

# Esperar al launcher (entrada principal)
Wait-Port 8099 "launcher backend"
Wait-Port 5172 "launcher frontend"

# Abrir solo el launcher — desde ahí se accede a todo
Write-Host ""
Write-Host "  Abriendo launcher..." -ForegroundColor Cyan
Start-Process "http://localhost:5172"

Write-Host ""
Write-Host "  Todo iniciado. Launcher en http://localhost:5172" -ForegroundColor Green
Write-Host "  Logs en .\logs\  |  Para detener: .\stop-all.ps1" -ForegroundColor Yellow
Write-Host ""
