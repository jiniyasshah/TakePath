@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run setup_windows.bat first.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m unittest discover -s tests -v
if errorlevel 1 goto :failed
".venv\Scripts\python.exe" -m compileall -q action_studio main.py
if errorlevel 1 goto :failed
echo.
echo Automated core checks passed.
pause
exit /b 0
:failed
echo.
echo One or more checks failed.
pause
exit /b 1
