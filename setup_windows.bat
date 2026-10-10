@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
    py -3 -m venv .venv
) else (
    python -m venv .venv
)
if errorlevel 1 goto :failed
call ".venv\Scripts\python.exe" -m pip install --upgrade pip
call ".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :failed
echo.
echo Installation complete. Double click start_windows.bat to launch.
pause
exit /b 0
:failed
echo.
echo Setup failed. Install Python 3.11 or 3.12 from python.org and try again.
pause
exit /b 1
