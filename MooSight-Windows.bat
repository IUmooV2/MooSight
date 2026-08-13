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

REM --- Validate that this launcher is inside a complete MooSight checkout ---
if not exist "sf.py" (
  echo MooSight cannot start because sf.py is missing.
  echo Download/extract the complete MooSight repository, not only this BAT file.
  pause
  exit /b 1
)
if not exist "moosight.py" (
  echo MooSight cannot start because moosight.py is missing.
  echo Download/extract the complete MooSight repository, not only this BAT file.
  pause
  exit /b 1
)
if not exist "requirements.txt" (
  echo MooSight cannot start because requirements.txt is missing.
  echo Download/extract the complete MooSight repository, not only this BAT file.
  pause
  exit /b 1
)

REM --- Find Python 3.10, or install it automatically with Windows Package Manager ---
py -3.10 --version >nul 2>&1
if errorlevel 1 (
  echo [1/10] Python 3.10 is not installed. Installing it automatically...
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

echo [2/10] Python is ready.

REM --- Create isolated environment ---
if not exist ".venv\Scripts\python.exe" (
  echo [3/10] Preparing MooSight for the first time...
  py -3.10 -m venv .venv
  if errorlevel 1 goto :fail

  ".venv\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
  if errorlevel 1 goto :fail
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto :fail
) else (
  echo [3/10] MooSight environment already exists.
)

echo [4/10] Checking installed Python dependencies...
".venv\Scripts\python.exe" -m pip check
if errorlevel 1 (
  echo.
  echo MooSight found incompatible or missing Python packages.
  echo Delete the .venv folder and run this launcher again to rebuild it cleanly.
  pause
  exit /b 1
)

echo [5/10] Running MooSight preflight checks...
".venv\Scripts\python.exe" -m tools.preflight --host 127.0.0.1 --port 5001
if errorlevel 1 (
  echo.
  echo MooSight's preflight checks found a problem that would prevent a reliable start.
  echo Review the FAIL line above. If you want help, take a screenshot of this window.
  pause
  exit /b 1
)

echo [6/10] Enforcing modern exception-handling policy...
".venv\Scripts\python.exe" -m tools.verify_exception_policy
if errorlevel 1 (
  echo.
  echo MooSight found unsafe exception handling in the modernized runtime.
  echo Bare except and BaseException handlers are not allowed in MooSight-owned modern code.
  echo Review the FAIL line above and take a screenshot if you want help troubleshooting it.
  pause
  exit /b 1
)

echo [7/10] Enforcing modern security policy...
".venv\Scripts\python.exe" -m tools.verify_modern_security
if errorlevel 1 (
  echo.
  echo MooSight found a blocked security pattern in the modernized runtime.
  echo Global TLS overrides, global TLS-warning suppression, and shell=True are not allowed there.
  echo Review the FAIL line above and take a screenshot if you want help troubleshooting it.
  pause
  exit /b 1
)

echo [8/10] Verifying legacy exception containment...
".venv\Scripts\python.exe" -m tools.verify_legacy_exception_containment
if errorlevel 1 (
  echo.
  echo MooSight found a legacy method with unsafe exception handling still reachable at runtime.
  echo Review the FAIL line above before starting the application.
  pause
  exit /b 1
)

echo [9/10] Verifying modern core security and routing...
".venv\Scripts\python.exe" -m tools.verify_modern_runtime
if errorlevel 1 (
  echo.
  echo MooSight's modern runtime verification failed.
  echo The application will not start with an uncertain networking/security configuration.
  echo Review the FAIL line above and take a screenshot if you want help troubleshooting it.
  pause
  exit /b 1
)

echo [10/10] Starting MooSight with the modern core...
echo.
echo Your browser will open automatically.
echo Keep this window open while using MooSight.
echo Press Ctrl+C here when you want to stop it.
echo.
start "" "http://127.0.0.1:5001"
".venv\Scripts\python.exe" moosight.py -l 127.0.0.1:5001
set "EXITCODE=%ERRORLEVEL%"

if not "%EXITCODE%"=="0" (
  echo.
  echo MooSight stopped with error code %EXITCODE%.
  echo Take a screenshot of this window and send it here for troubleshooting.
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
echo Take a screenshot of the error above and send it here for troubleshooting.
pause
exit /b 1
