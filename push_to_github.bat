@echo off
setlocal enabledelayedexpansion

REM Try to add common Git paths to environment for this session
set "PATH=%PATH%;C:\Program Files\Git\cmd;C:\Program Files (x86)\Git\cmd;C:\Users\%USERNAME%\AppData\Local\Programs\Git\cmd"

echo ===================================================
echo   TK-Ops-Pro GitHub Publisher
echo ===================================================

where git >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Git is still not found!
    echo Please restart VS Code to pick up the new installation.
    echo Or ensure Git is installed at C:\Program Files\Git
    pause
    exit /b
)

echo [Status] Git found at: 
where git

echo.
echo [1/6] Initializing/Checking repository...
if not exist .git (
    git init
)

echo [2/6] Adding files...
git add .

echo [3/6] Committing...
git commit -m "Update: Complete optimization and features" 

echo [4/6] Setting main branch...
git branch -M main

echo [5/6] Configuration Remote...
git remote remove origin 2>nul
git remote add origin https://github.com/SHCSCA/TK-OPS-ASSISTANT.git

echo [6/6] Pushing to GitHub...
echo (Please authenticate in the browser if prompted)
git push -u origin main

echo.
if %ERRORLEVEL% EQU 0 (
    echo [SUCCESS] Push completed!
) else (
    echo [ERROR] Push failed. Check your internet or permissions.
)
pause
