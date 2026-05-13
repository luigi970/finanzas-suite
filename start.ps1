# Stock Screener — arranque para Windows, Linux y macOS (PowerShell / pwsh)

$Root = $PSScriptRoot

Write-Host "Iniciando Stock Screener..." -ForegroundColor Cyan

if ($IsWindows -or (-not $IsLinux -and -not $IsMacOS)) {
    # Windows: abre dos ventanas separadas
    $backend  = Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$Root\backend'; uvicorn main:app --reload --port 8000" -PassThru
    $frontend = Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$Root\frontend'; npm run dev" -PassThru
    Write-Host ""
    Write-Host "Backend:  http://localhost:8000" -ForegroundColor Green
    Write-Host "Frontend: http://localhost:5173"  -ForegroundColor Green
    Write-Host ""
    Write-Host "Cerrá las ventanas para detener." -ForegroundColor Yellow
    Wait-Process -Id $backend.Id, $frontend.Id
} else {
    # Linux / macOS: corre en background en la misma terminal
    $backendJob  = Start-Job -ScriptBlock { param($r) Set-Location "$r/backend";  uvicorn main:app --reload --port 8000 } -ArgumentList $Root
    $frontendJob = Start-Job -ScriptBlock { param($r) Set-Location "$r/frontend"; npm run dev } -ArgumentList $Root

    Write-Host ""
    Write-Host "Backend:  http://localhost:8000" -ForegroundColor Green
    Write-Host "Frontend: http://localhost:5173"  -ForegroundColor Green
    Write-Host ""
    Write-Host "Presioná Ctrl+C para detener." -ForegroundColor Yellow

    try {
        while ($true) {
            Receive-Job -Job $backendJob, $frontendJob
            Start-Sleep 1
        }
    } finally {
        Stop-Job  -Job $backendJob, $frontendJob
        Remove-Job -Job $backendJob, $frontendJob
    }
}
