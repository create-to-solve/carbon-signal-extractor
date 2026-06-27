@echo off
REM Runner invoked by Task Scheduler. Captures stdout+stderr to the log file.
set PROJECT_DIR=C:\Users\ashis\carbon_signal_extractor
set PYTHON_EXE=C:\Users\ashis\AppData\Local\Programs\Python\Python312\python.exe
set LOG_DIR=%PROJECT_DIR%\logs
set LOG_FILE=%LOG_DIR%\scheduler.log

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

cd /d "%PROJECT_DIR%"
set CARBON_NONINTERACTIVE=1
"%PYTHON_EXE%" main.py >> "%LOG_FILE%" 2>&1
exit /b %ERRORLEVEL%
