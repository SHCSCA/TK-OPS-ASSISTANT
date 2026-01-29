@echo off
chcp 65001 >nul
set "PYTHONUTF8=1"

echo.
REM Activate virtual environment if exists
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

REM Check if python is available
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python or set up venv.
    pause
    exit /b 1
)

REM Call the Python build script
python build.py

if %errorlevel% neq 0 (
    echo.
    echo [Build Failed]
    pause
    exit /b %errorlevel%
)

echo.
pause
