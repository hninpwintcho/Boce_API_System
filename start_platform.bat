@echo off
REM start_platform.bat
REM This script starts the Boce API and Scheduler in the background on Windows.

echo 🚀 Starting Domain Operations Platform (Batch Mode)...

REM 1. Clean up old processes
echo 🧹 Cleaning up old processes...
taskkill /F /IM python.exe 2>nul

REM 2. Start services
echo 📡 Starting API and Scheduler...
start /b python -m app.cli api
start /b python -m app.cli scheduler

echo ✅ Services are running in the background!
echo 🔗 Dashboard: http://localhost:3000/dashboard
echo.
echo Use CTRL+C if you want to stop this window, but the background processes will stay alive.
