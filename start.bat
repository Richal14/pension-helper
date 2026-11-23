@echo off
rem Pension Helper: ONE command that starts the backend, which also serves the frontend pages.
rem Double-click this file, or type  start.bat  in a terminal. Keep the window open; close it to stop.
setlocal
cd /d "%~dp0"

if not exist "backend\.venv\Scripts\python.exe" (
  echo First run: setting up Python packages...
  python -m venv backend\.venv || goto :fail
  backend\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -q -r backend\requirements.txt || goto :fail
)

if not exist "backend\.env" (
  echo backend\.env is missing. Copy backend\.env.example to backend\.env and fill it in.
  goto :fail
)

echo.
echo  Pension Helper is running at  http://localhost:8000
echo  Close this window to stop it.
echo.
start "" "http://localhost:8000"
backend\.venv\Scripts\python.exe -m uvicorn app:app --app-dir backend --host 127.0.0.1 --port 8000
goto :eof

:fail
echo.
echo Something went wrong. See the message above.
pause
exit /b 1
