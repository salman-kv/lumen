@echo off
rem Starts Lumen on this PC and prints a free public link (Cloudflare quick tunnel) for the hiring team.
rem Needs: uv, node, curl, a Groq key in backend\.env (see README), and tools\cloudflared.exe (downloaded if missing).
cd /d "%~dp0.."
if not exist tools\cloudflared.exe (
  echo Downloading cloudflared...
  mkdir tools 2>nul
  curl -L -o tools\cloudflared.exe https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe
)
call "%~dp0update_live.bat"
if errorlevel 1 exit /b 1
echo.
echo Look for the line  https://<random-words>.trycloudflare.com  below. Send that link to the reviewers.
echo Keep this window open while they test. Close it to stop sharing. (A new link is made each time.)
echo.
tools\cloudflared.exe tunnel --url http://localhost:8000 --no-autoupdate
