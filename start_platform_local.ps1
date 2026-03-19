# start_platform_local.ps1
# This script starts the Boce Platform services locally without Docker.

Write-Host "🚀 Starting Domain Operations Platform (Local Mode)..." -ForegroundColor Cyan

# 1. Kill any existing instances
Write-Host "🧹 Cleaning up old processes..." -ForegroundColor Gray
taskkill /F /IM python.exe 2>$null

# 2. Start API in the background
Write-Host "📡 Starting API Service on port 3000..." -ForegroundColor Green
Start-Process python -ArgumentList "-m", "app.cli", "api" -WindowStyle Hidden

# 3. Start Scheduler in the background
Write-Host "⏰ Starting Priority Scheduler..." -ForegroundColor Green
Start-Process python -ArgumentList "-m", "app.cli", "scheduler" -WindowStyle Hidden

Write-Host "✅ Platform is LIVE!" -ForegroundColor Cyan
Write-Host "🔗 Dashboard: http://localhost:3000/dashboard" -ForegroundColor Gray
Write-Host "📝 Logs are being written to the terminal in a few seconds..." -ForegroundColor Gray

# 4. Tail logs (optional - just showing current status)
Start-Sleep -Seconds 2
Get-Process python | Select-Object Id, ProcessName, StartTime
