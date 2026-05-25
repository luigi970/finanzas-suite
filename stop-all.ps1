# stop-all.ps1 — detiene todos los procesos de maximos + finanzas

$ports = @(8000, 8001, 5173, 5174)

Write-Host ""
foreach ($port in $ports) {
    $conn = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($conn) {
        $procId = $conn.OwningProcess | Select-Object -First 1
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        Write-Host "  Puerto $port liberado" -ForegroundColor Green
    } else {
        Write-Host "  Puerto $port ya estaba libre" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "  Todo detenido." -ForegroundColor Cyan
Write-Host ""
