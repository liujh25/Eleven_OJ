@echo off
setlocal EnableExtensions
chcp 65001 >nul 2>&1
title Async OJ Launcher

cd /d "%~dp0"
set "PROJECT_ROOT=%CD%"
set "VENV_DIR=%PROJECT_ROOT%\.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "OJ_API_URL=http://127.0.0.1:8000"
set "FRONTEND_URL=http://127.0.0.1:8501"
if defined PYTHONPATH (
    set "PYTHONPATH=%PROJECT_ROOT%;%PYTHONPATH%"
) else (
    set "PYTHONPATH=%PROJECT_ROOT%"
)

echo ========================================
echo           Async OJ one-click start
echo ========================================
echo Project: %PROJECT_ROOT%
echo.

if not exist "%VENV_PY%" (
    echo [1/4] Creating Python virtual environment...
    where py >nul 2>&1
    if not errorlevel 1 (
        py -3.12 -m venv "%VENV_DIR%" >nul 2>&1
        if errorlevel 1 py -3 -m venv "%VENV_DIR%"
    ) else (
        python -m venv "%VENV_DIR%"
    )
    if not exist "%VENV_PY%" goto :venv_failed
) else (
    echo [1/4] Virtual environment found.
)

"%VENV_PY%" -c "import fastapi, streamlit, sqlalchemy, aiosqlite, bcrypt, cryptography, httpx, psutil, pydantic_settings, uvicorn, oj, frontend" >nul 2>&1
if errorlevel 1 (
    echo [2/4] Installing project dependencies. This may take a few minutes...
    "%VENV_PY%" -m pip install -e "%PROJECT_ROOT%"
    if errorlevel 1 goto :install_failed
) else (
    echo [2/4] Project dependencies are ready.
)

if /I "%~1"=="--check" (
    echo [OK] Environment check passed.
    exit /b 0
)

call :url_ready "%OJ_API_URL%/health" 2
if errorlevel 1 (
    echo [3/4] Starting FastAPI backend at %OJ_API_URL% ...
    start "Async OJ API" /D "%PROJECT_ROOT%" "%VENV_PY%" -m uvicorn oj.app:app --host 127.0.0.1 --port 8000
    call :wait_for_url "%OJ_API_URL%/health" 30
    if errorlevel 1 goto :api_failed
) else (
    echo [3/4] FastAPI backend is already running.
)

call :url_ready "%FRONTEND_URL%" 2
if errorlevel 1 (
    echo [4/4] Starting Streamlit frontend at %FRONTEND_URL% ...
    start "Async OJ Web" /D "%PROJECT_ROOT%" "%VENV_PY%" -m streamlit run frontend\app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false
    call :wait_for_url "%FRONTEND_URL%" 45
    if errorlevel 1 goto :frontend_failed
) else (
    echo [4/4] Streamlit frontend is already running.
)

echo.
echo Async OJ is ready: %FRONTEND_URL%
echo API documentation: %OJ_API_URL%/docs
echo Close the two service windows to stop the platform.
if /I not "%OJ_NO_BROWSER%"=="1" start "" "%FRONTEND_URL%"
exit /b 0

:url_ready
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "try { $response = Invoke-WebRequest -UseBasicParsing -Uri '%~1' -TimeoutSec %~2; if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) { exit 0 } } catch {}; exit 1" >nul 2>&1
exit /b %errorlevel%

:wait_for_url
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$deadline = (Get-Date).AddSeconds(%~2); do { try { $response = Invoke-WebRequest -UseBasicParsing -Uri '%~1' -TimeoutSec 2; if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) { exit 0 } } catch {}; Start-Sleep -Milliseconds 500 } while ((Get-Date) -lt $deadline); exit 1" >nul 2>&1
exit /b %errorlevel%

:venv_failed
echo [ERROR] Could not create .venv. Install Python 3.10 or newer and try again.
pause
exit /b 1

:install_failed
echo [ERROR] Dependency installation failed. Check the network and pip output above.
pause
exit /b 1

:api_failed
echo [ERROR] The backend did not become ready within 30 seconds.
echo Check the "Async OJ API" window for details. Port 8000 may already be occupied.
pause
exit /b 1

:frontend_failed
echo [ERROR] The frontend did not become ready within 45 seconds.
echo Check the "Async OJ Web" window for details. Port 8501 may already be occupied.
pause
exit /b 1
