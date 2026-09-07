@echo off
rem ==============================================================================
rem KCMS Collaborative Labeler - Server Start Script (Windows Batch)
rem ==============================================================================

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"

:: Check for Python
where python >nul 2>nul
if %errorlevel% equ 0 (
    set "PYTHON_CMD=python"
    goto :check_cloudflared
)

where py >nul 2>nul
if %errorlevel% equ 0 (
    set "PYTHON_CMD=py"
    goto :check_cloudflared
)

where python3 >nul 2>nul
if %errorlevel% equ 0 (
    set "PYTHON_CMD=python3"
    goto :check_cloudflared
)

echo [ERROR] Python is not installed or not in your Windows PATH.
echo Please install Python from https://www.python.org/ and check "Add Python to PATH".
pause
exit /b 1

:check_cloudflared
:: Check for Cloudflare Tunnel
where cloudflared >nul 2>nul
if %errorlevel% equ 0 (
    echo [INFO] Cloudflare CLI detected.
    goto :find_script
)

where npx >nul 2>nul
if %errorlevel% equ 0 (
    echo [INFO] Cloudflare available via npx.
    goto :find_script
)

echo [INFO] Cloudflare not detected. (Install Node.js or download cloudflared.exe for public links)

:find_script
if exist "%SCRIPT_DIR%run.py" (
    set "RUN_PATH=%SCRIPT_DIR%run.py"
    goto :start_server
)

if exist "%SCRIPT_DIR%labeling_app\run.py" (
    set "RUN_PATH=%SCRIPT_DIR%labeling_app\run.py"
    goto :start_server
)

echo [ERROR] Could not find run.py in %SCRIPT_DIR%.
pause
exit /b 1

:start_server
echo [INFO] Starting KCMS Collaborative Labeler on Windows...
%PYTHON_CMD% "%RUN_PATH%" %*
pause
