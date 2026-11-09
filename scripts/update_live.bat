@echo off
rem Rebuilds the frontend and restarts the Lumen server on this PC.
rem The public link (Cloudflare tunnel) keeps running and keeps the same address, so changes go live right away.
cd /d "%~dp0.."

echo [1/3] Building the frontend...
pushd frontend
call npm run build
if errorlevel 1 (
  echo.
  echo The build failed. Fix the error above, then run this again.
  popd
  exit /b 1
)
popd

echo [2/3] Stopping the old server on port 8000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000 " ^| findstr LISTENING') do taskkill /PID %%a /F >nul 2>&1

echo [3/3] Starting the server (a minimised window called "Lumen server" opens; close it to stop the site)...
start "Lumen server" /min cmd /c "cd backend && set SEED_DEMO=true&& uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips=*"

echo Waiting for it to be ready...
:wait
ping -n 4 127.0.0.1 >nul
curl -s -o nul http://localhost:8000/api/health
if errorlevel 1 goto wait

echo.
echo Done. The site is updated. Press Ctrl+F5 in your browser to see the changes.
