# Stop Distribution Management System

Write-Host "🛑 Stopping Distribution Management System..." -ForegroundColor Red
Write-Host ""

# Stop backend processes
Write-Host "Stopping backend server..." -ForegroundColor Yellow
Get-Process | Where-Object { $_.ProcessName -like "*python*" -and $_.CommandLine -like "*uvicorn*" } | Stop-Process -Force -ErrorAction SilentlyContinue

# Stop frontend processes (Node)
Write-Host "Stopping frontend server..." -ForegroundColor Yellow
Get-Process | Where-Object { $_.ProcessName -eq "node" } | Stop-Process -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "✅ All servers stopped!" -ForegroundColor Green
Write-Host ""
