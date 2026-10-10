@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run setup_windows.bat first.
  pause
  exit /b 1
)
call ".venv\Scripts\python.exe" -m pip install "pyinstaller>=6,<7"
if errorlevel 1 goto :failed
call ".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --windowed --name TakePath --icon "assets\takepath.ico" --add-data "assets;assets" --add-data "examples;examples" --collect-all uiautomation main.py
if errorlevel 1 goto :failed
echo.
echo Finished: dist\TakePath\TakePath.exe
echo Windows may warn about unsigned executables; code signing is not included.
pause
exit /b 0
:failed
echo Build failed.
pause
exit /b 1
