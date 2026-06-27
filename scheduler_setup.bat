@echo off
REM One-shot setup: creates logs\ and registers a daily Task Scheduler job
REM that runs main.py at 07:00 local time. Re-runnable (/f overwrites).

set PROJECT_DIR=C:\Users\ashis\carbon_signal_extractor
set LOG_DIR=%PROJECT_DIR%\logs
set RUNNER=%PROJECT_DIR%\run_sweep.bat
set TASK_NAME=CarbonMarketSweep

if not exist "%LOG_DIR%" (
    mkdir "%LOG_DIR%"
    echo Created %LOG_DIR%
) else (
    echo %LOG_DIR% already exists
)

if not exist "%RUNNER%" (
    echo ERROR: runner not found at %RUNNER%
    exit /b 1
)

echo Registering task "%TASK_NAME%" daily at 07:00...
schtasks /create /tn "%TASK_NAME%" /tr "\"%RUNNER%\"" /sc daily /st 07:00 /f
if errorlevel 1 (
    echo schtasks /create failed
    exit /b 1
)

echo.
echo Verifying...
schtasks /query /tn "%TASK_NAME%"
