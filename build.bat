@echo off
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
echo ===================================================
echo  构建 TikTok 运营助手 (EXE)
echo ===================================================
echo.

REM Activate virtual environment
if exist venv\Scripts\activate.bat (
    echo [信息] 正在激活虚拟环境...
    call venv\Scripts\activate.bat
    set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
) else (
    echo [警告] 未找到虚拟环境。正在使用系统 Python。
    set "PYTHON_EXE=python"
)

REM Check if PyInstaller is installed
"%PYTHON_EXE%" -m pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 PyInstaller。正在安装...
    "%PYTHON_EXE%" -m pip install pyinstaller
)

echo [信息] 正在清理旧的构建文件...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

REM 保留仓库内的 tk-ops-assistant.spec（用于稳定打包）

echo [信息] 正在开始构建过程...
echo 这可能需要几分钟，请耐心等待。
echo.

REM Build command
REM --onefile: Create a single EXE file
REM --windowed: No console window (GUI mode)
REM --name: Output filename
REM --paths: Add src to python path to find modules
REM --hidden-import: Explicitly import modules that might be missed
"%PYTHON_EXE%" -m PyInstaller tk-ops-assistant.spec ^
    --distpath "dist" ^
    --workpath "build" ^
    --noconfirm ^
    --clean

if %errorlevel% neq 0 (
    echo.
    echo [错误] 构建失败！
    exit /b %errorlevel%
)

REM Ensure .env is placed next to exe (frozen mode reads BASE_DIR=.exe folder)
if not exist "dist" mkdir "dist" >nul 2>&1
if exist ".env" (
    copy /y ".env" "dist\.env" >nul
) else (
    echo.>"dist\.env"
)

echo.
echo ===================================================
echo  构建成功！
echo ===================================================
echo.
echo 可执行文件位于：
echo %~dp0dist\tk-ops-assistant.exe
echo.
exit /b 0
