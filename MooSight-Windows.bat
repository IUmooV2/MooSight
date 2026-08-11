@echo off
setlocal
cd /d "%~dp0"

echo ==================================================
echo MooSight Windows Launcher
echo ==================================================

where py >nul 2>&1
if errorlevel 1 (
  echo Python Launcher ^(py.exe^) was not found.
  echo Install Python 3.10 for Windows, then run this file again.
  pause
  exit /b 1
)

py -3.10 --version >nul 2>&1
if errorlevel 1 (
  echo Python 3.10 was not found.
  echo MooSight's upstream test workflow currently covers Python 3.7 through 3.10.
  echo Install Python 3.10 for the most conservative first-run setup.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Creating virtual environment...
  py -3.10 -m venv .venv
  if errorlevel 1 goto :fail

  echo [2/3] Installing MooSight dependencies...
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  if errorlevel 1 goto :fail
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto :fail
) else (
  echo Existing virtual environment found.
)

echo [3/3] Starting MooSight at http://127.0.0.1:5001
start "" "http://127.0.0.1:5001"
".venv\Scripts\python.exe" sf.py -l 127.0.0.1:5001
set EXITCODE=%ERRORLEVEL%

if not "%EXITCODE%"=="0" (
  echo.
  echo MooSight exited with code %EXITCODE%.
  echo Copy the error shown above and send it to ChatGPT for troubleshooting.
  pause
)
exit /b %EXITCODE%

:fail
echo.
echo Setup failed. Copy the error shown above and send it to ChatGPT.
pause
exit /b 1
