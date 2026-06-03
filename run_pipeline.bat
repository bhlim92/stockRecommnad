@echo off
:: ==============================================================================
:: Stock Discovery & Portfolio Rebalancing Scheduler Execution Script
:: ==============================================================================
setlocal enabledelayedexpansion

:: Set project directory paths
set PROJECT_DIR=c:\Users\samsung\proj\stockRecommnad
set VENV_DIR=%PROJECT_DIR%\venv
set LOGS_DIR=%PROJECT_DIR%\logs

cd /d "%PROJECT_DIR%"

:: Ensure log directory exists
if not exist "%LOGS_DIR%" (
    mkdir "%LOGS_DIR%"
)

echo [%DATE% %TIME%] Starting Stock Discovery Pipeline run... >> "%LOGS_DIR%\scheduler.log"

:: Check if virtual environment exists, if not create it
if not exist "%VENV_DIR%" (
    echo [%DATE% %TIME%] Virtual environment not found. Creating one... >> "%LOGS_DIR%\scheduler.log"
    python -m venv "%VENV_DIR%" >> "%LOGS_DIR%\scheduler.log" 2>&1
    if !ERRORLEVEL! neq 0 (
        echo [%DATE% %TIME%] ERROR: Failed to create virtual environment. >> "%LOGS_DIR%\scheduler.log"
        exit /b !ERRORLEVEL!
    )
)

:: Activate virtual environment
call "%VENV_DIR%\Scripts\activate.bat" >> "%LOGS_DIR%\scheduler.log" 2>&1

:: Install/verify dependencies
echo [%DATE% %TIME%] Verifying dependencies... >> "%LOGS_DIR%\scheduler.log"
pip install -r "%PROJECT_DIR%\requirements.txt" >> "%LOGS_DIR%\scheduler.log" 2>&1
if !ERRORLEVEL! neq 0 (
    echo [%DATE% %TIME%] WARNING: Failed to verify or install dependencies. Proceeding with existing packages. >> "%LOGS_DIR%\scheduler.log"
)

:: Run the orchestrator script
echo [%DATE% %TIME%] Executing main.py... >> "%LOGS_DIR%\scheduler.log"
python "%PROJECT_DIR%\main.py" >> "%LOGS_DIR%\scheduler.log" 2>&1

set PIPELINE_STATUS=!ERRORLEVEL!
if !PIPELINE_STATUS! neq 0 (
    echo [%DATE% %TIME%] ERROR: main.py execution failed with exit code !PIPELINE_STATUS!. >> "%LOGS_DIR%\scheduler.log"
) else (
    echo [%DATE% %TIME%] Pipeline executed successfully. >> "%LOGS_DIR%\scheduler.log"
)

echo [%DATE% %TIME%] Pipeline run finished. >> "%LOGS_DIR%\scheduler.log"
echo -------------------------------------------------- >> "%LOGS_DIR%\scheduler.log"

deactivate
exit /b !PIPELINE_STATUS!
