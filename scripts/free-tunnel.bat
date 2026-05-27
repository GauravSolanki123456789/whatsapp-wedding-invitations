@echo off
REM Free instant public link while your laptop runs the app (no GitHub needed).
REM Requires cloudflared: winget install Cloudflare.cloudflared

echo Starting Streamlit...
start "Streamlit" cmd /k "cd /d %~dp0.. && streamlit run app.py --server.port 8501"

timeout /t 5 /nobreak >nul

echo.
echo Starting free Cloudflare tunnel...
echo Your public link will appear below (copy the https://....trycloudflare.com URL):
echo.

cloudflared tunnel --url http://localhost:8501
