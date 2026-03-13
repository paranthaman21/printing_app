@echo off
echo ===========================================
echo Starting SaaS Printing Project (Phase 1)
echo ===========================================
echo.

echo Step 1: Installing required packages...
python -m pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Failed to install packages. Make sure Python is installed!
    pause
    exit /b
)

echo.
echo Step 2: Starting the server...
cd backend
python app.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] The server stopped unexpectedly.
    pause
    exit /b
)
