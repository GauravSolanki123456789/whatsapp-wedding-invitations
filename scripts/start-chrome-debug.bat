@echo off
REM Optional manual start — Auto Send usually launches Chrome for you.
cd /d "%~dp0.."

set "CHROME=%LocalAppData%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"

set "PROFILE=%cd%\.chrome-whatsapp-profile"
if not exist "%PROFILE%" mkdir "%PROFILE%"

start "" "%CHROME%" --remote-debugging-port=9223 --remote-allow-origins=* --user-data-dir="%PROFILE%" --profile-directory=Default https://web.whatsapp.com
echo Chrome started with WhatsApp (port 9223). Scan QR once, then use Auto Send in the app.
pause
