# start-all.ps1

$Root = $PSScriptRoot
$LogDir = Join-Path $Root "logs"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }

function Wait-Port($port, $label, $maxSecs = 40) {
    Write-Host "  $label" -NoNewline
    for ($i = 0; $i -lt $maxSecs; $i++) {
        $ok = Test-NetConnection -ComputerName localhost -Port $port -InformationLevel Quiet -WarningAction SilentlyContinue
        if ($ok) { Write-Host " OK" -ForegroundColor Green; return }
        Start-Sleep 1; Write-Host -NoNewline "."
    }
    Write-Host " timeout" -ForegroundColor Yellow
}

function Start-App($dir, $cmd, $logName) {
    $logOut = Join-Path $LogDir $logName
    $logErr = Join-Path $LogDir ($logName -replace '\.log$', '-err.log')
    Start-Process powershell `
        -ArgumentList "-NoProfile", "-NonInteractive", "-Command", "Set-Location '$dir'; $cmd" `
        -WindowStyle Hidden `
        -RedirectStandardOutput $logOut `
        -RedirectStandardError $logErr
}

Write-Host "finanzas suite - iniciando" -ForegroundColor Cyan

Start-App "$Root\launcher\backend"  "uvicorn main:app --port 8099" "launcher-backend.log"
Start-App "$Root\launcher\frontend" "npm run dev"                  "launcher-frontend.log"
Start-App "$Root\maximos\backend"   "uvicorn main:app --port 8000" "maximos-backend.log"
Start-App "$Root\maximos\frontend"  "npm run dev"                  "maximos-frontend.log"
Start-App "$Root\finanzas\backend"  "uvicorn main:app --port 8001" "finanzas-backend.log"
Start-App "$Root\finanzas\frontend" "npm run dev"                  "finanzas-frontend.log"
Start-App "$Root\fiscal\backend"    "uvicorn main:app --port 8002" "fiscal-backend.log"
Start-App "$Root\fiscal\frontend"   "npm run dev"                  "fiscal-frontend.log"

Wait-Port 8099 "launcher backend"
Wait-Port 5172 "launcher frontend"

Write-Host ""
Start-Process "http://localhost:5172"
Write-Host "  Launcher en http://localhost:5172" -ForegroundColor Green
Write-Host "  Logs en .\logs\  |  Detener: .\stop-all.ps1" -ForegroundColor Yellow
Write-Host ""
