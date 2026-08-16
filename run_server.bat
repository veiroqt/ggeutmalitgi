@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found at .venv
    echo Run these first:
    echo   python -m venv .venv
    echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

if not exist ".env" (
    echo [WARNING] .env file not found. Copy .env.example to .env and fill in
    echo JWT_SECRET and KOREAN_DICT_API_KEY.
    echo.
)

netstat -ano | findstr ":8000" | findstr "LISTENING" >nul
if %errorlevel%==0 (
    echo [INFO] Something is already listening on port 8000.
    echo Try opening http://localhost:8000 directly.
    echo.
    pause
    exit /b 0
)

echo Starting the word-chain game server...
echo Open http://localhost:8000 in your browser.
echo Press Ctrl+C in this window to stop the server.
echo.

".venv\Scripts\python.exe" -m uvicorn backend.main:app --reload

echo.
echo Server stopped.
pause
