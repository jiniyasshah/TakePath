@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Dependencies are not installed. Run setup_windows.bat first.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" main.py
if errorlevel 1 pause
