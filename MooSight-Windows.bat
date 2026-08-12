@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title MooSight Setup and Launcher

echo ==================================================
echo              MooSight - Easy Setup
echo ==================================================
echo.
echo This will set up everything MooSight needs and start it.
echo The first run can take several minutes.
echo.

REM --- Find Python 3.10, or install it automatically with Windows Package Manager ---
py -3.10 --version >nul 2>&1
if errorlevel 1 (
  echo [1/4] Python 3.10 is not installed. Installing it automatically...
  where winget >nul 2>&1
  if errorlevel 1 (
    echo.
    echo Automatic Python installation needs Windows Package Manager ^(winget^).
    echo Opening the official Python 3.10.11 Windows download page instead.
    start "" "https://www.python.org/downloads/release/python-31011/"
    echo Install the 64-bit Windows installer, then double-click this file again.
    pause
    exit /b 1
  )

  winget install --id Python.Python.3.10 -e --source winget --accept-package-agreements --accept-source-agreements
  if errorlevel 1 goto :pythonfail

  REM Refresh common Python Launcher location for this process.
  if exist "%LOCALAPPDATA%\Programs\Python\Launcher\py.exe" set "PATH=%LOCALAPPDATA%\Programs\Python\Launcher;%PATH%"
)

py -3.10 --version >nul 2>&1
if errorlevel 1 (
  echo.
  echo Python was installed, but Windows has not refreshed it for this window yet.
  echo Close this window and double-click MooSight-Windows.bat again.
  pause
  exit /b 0
)

echo [2/4] Python is ready.

REM --- Create isolated environment ---
if not exist ".venv\Scripts\python.exe" (
  echo [3/4] Preparing MooSight for the first time...
  py -3.10 -m venv .venv
  if errorlevel 1 goto :fail

  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  if errorlevel 1 goto :fail
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto :fail
) else (
  echo [3/4] MooSight is already prepared.
)

echo [4/4] Starting MooSight...
echo.
echo Your browser will open automatically.
echo Keep this window open while using MooSight.
echo Press Ctrl+C here when you want to stop it.
echo.
start "" "http://127.0.0.1:5001"
".venv\Scripts\python.exe" sf.py -l 127.0.0.1:5001
set "EXITCODE=%ERRORLEVEL%"

if not "%EXITCODE%"=="0" (
  echo.
  echo MooSight stopped with error code %EXITCODE%.
  echo Take a screenshot of this window and send it to ChatGPT.
  pause
)
exit /b %EXITCODE%

:pythonfail
echo.
echo Windows could not automatically install Python.
echo Opening the official Python download page.
start "" "https://www.python.org/downloads/release/python-31011/"
echo Install the 64-bit Windows installer, then run this file again.
pause
exit /b 1

:fail
echo.
echo MooSight setup did not finish successfully.
echo Take a screenshot of the error above and send it to ChatGPT.
pause
exit /b 1
