@echo off
REM Optional — Auto Send now restarts Chrome automatically.
echo Auto Send will restart Chrome for you. Just click the button in the app.
echo.
echo If you still want to start Chrome manually, close all Chrome windows first...
pause >nul

set "CHROME=%LocalAppData%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"

set "PROFILE=%LocalAppData%\Google\Chrome\User Data"
start "" "%CHROME%" --remote-debugging-port=9222 --remote-allow-origins=* --user-data-dir="%PROFILE%" --profile-directory=Default https://web.whatsapp.com
echo Chrome started with WhatsApp. Use Auto Send in the app.
