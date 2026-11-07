@echo off
rem Starts Lumen on this PC and prints a free public link (Cloudflare quick tunnel) for the hiring team.
rem Needs: Ollama running with qwen2.5:3b, uv installed, tools\cloudflared.exe (see README "Share from your PC").
cd /d "%~dp0.."
if not exist tools\cloudflared.exe (
  echo Downloading cloudflared...
  mkdir tools 2>nul
  curl -L -o tools\cloudflared.exe https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe
)
echo Starting Lumen on http://localhost:8000 ...
start "Lumen server" /min cmd /c "cd backend && set SEED_DEMO=true&& uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips=*"
timeout /t 20 /nobreak >nul
echo.
echo Look for the line  https://<random-words>.trycloudflare.com  below. Send that link to the reviewers.
echo Keep this window open while they test. Close it to stop sharing.
echo.
tools\cloudflared.exe tunnel --url http://localhost:8000 --no-autoupdate
