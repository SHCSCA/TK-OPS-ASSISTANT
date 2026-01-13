@echo off
setlocal
chcp 65001 >nul
echo ========================================
echo  TikTok 蓝海运营助手
echo ========================================
echo.

REM --- 1. 检查并选择 Python 版本 ---
set PYTHON_CMD=

REM 优先检查 "python" 命令
python -c "import sys; exit(0 if (3,8) <= sys.version_info <= (3,12) else 1)" >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=python
    goto :FoundPython
)

REM 如果默认 python 不兼容 (例如 3.14), 尝试通过 'py' 启动器寻找指定版本
echo [信息] 系统 'python' 版本不兼容 (需要 3.8-3.12). 正在检查其他版本...

REM 尝试 3.11 (推荐)
py -3.11 --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=py -3.11
    goto :FoundPython
)

REM 尝试 3.10
py -3.10 --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=py -3.10
    goto :FoundPython
)

REM 尝试 3.12
py -3.12 --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=py -3.12
    goto :FoundPython
)

REM 尝试 3.8 或 3.9
py -3.9 --version >nul 2>&1
if not errorlevel 1 ( set PYTHON_CMD=py -3.9 & goto :FoundPython )
py -3.8 --version >nul 2>&1
if not errorlevel 1 ( set PYTHON_CMD=py -3.8 & goto :FoundPython )

:NotFound
echo.
echo [严重错误] 未找到兼容的 Python 版本!
echo.
echo 您当前运行的是 Python 3.14+，它尚不支持 pyqt5 和 pandas 等核心库。
echo.
echo === 需要操作 ===
echo 请下载并安装 Python 3.11 (推荐):
echo https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
echo.
echo 1. 安装 Python 3.11
REM 2. 重新运行此脚本
echo.
if not defined NO_PAUSE pause
exit /b 1

:FoundPython
echo [信息] 使用 Python 解释器: %PYTHON_CMD%
%PYTHON_CMD% --version

REM --- 2. 清理之前运行遗留的不兼容虚拟环境 ---
set "NEED_REBUILD="
if exist venv (
    if not exist venv\pyvenv.cfg (
        echo [警告] 虚拟环境缺少 pyvenv.cfg，可能已损坏。正在重新构建...
        set NEED_REBUILD=1
    ) else (
        type venv\pyvenv.cfg | findstr "version = 3.14" >nul
        if not errorlevel 1 (
            echo [警告] 检测到来自 Python 3.14 的虚拟环境。正在重新构建...
            set NEED_REBUILD=1
        )
    )
    if not exist venv\Scripts\activate.bat (
        echo [警告] 虚拟环境似乎已损坏。正在重新构建...
        set NEED_REBUILD=1
    )
    if not exist venv\Scripts\python.exe (
        echo [警告] 虚拟环境缺少 python.exe，可能已损坏。正在重新构建...
        set NEED_REBUILD=1
    )
)

REM --- 3. 创建虚拟环境 ---
if "%NEED_REBUILD%"=="1" (
    echo [信息] 正在重新创建虚拟环境...
    REM 尝试停止占用 venv\Scripts\python.exe 的进程，避免删除/重建时报“拒绝访问”
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$p = Join-Path (Resolve-Path .).Path 'venv\\Scripts\\python.exe'; if (Test-Path $p) { Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.Path -and ($_.Path -ieq $p) } | Stop-Process -Force -ErrorAction SilentlyContinue }" >nul 2>&1

    rmdir /s /q venv 2>nul
    if exist venv (
        set "OLD_VENV=venv_old_%RANDOM%_%RANDOM%"
        echo [警告] 无法删除 venv，尝试重命名为 %OLD_VENV% ...
        ren venv "%OLD_VENV%" 2>nul
        if exist venv (
            echo [错误] venv 仍被占用，无法重建。
            echo 请先关闭已启动的程序窗口/相关 python 进程后重试。
            if not defined NO_PAUSE pause
            exit /b 1
        )
    )

    %PYTHON_CMD% -m venv venv
    if errorlevel 1 (
        echo [错误] 重新创建 venv 失败。
        if not defined NO_PAUSE pause
        exit /b 1
    )
)
if not exist venv (
    echo [信息] 正在创建虚拟环境...
    %PYTHON_CMD% -m venv venv
    if errorlevel 1 (
        echo [错误] 创建 venv 失败。
        if not defined NO_PAUSE pause
        exit /b 1
    )
)

REM --- 4. 安装依赖 ---
echo [信息] 正在激活虚拟环境...
call venv\Scripts\activate.bat

set "VENV_PY=%~dp0venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
    echo [错误] 未找到虚拟环境 Python：%VENV_PY%
    if not defined NO_PAUSE pause
    exit /b 1
)

echo [信息] 正在升级 pip...
"%VENV_PY%" -m pip install --upgrade pip

echo [信息] 正在安装依赖...
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [错误] 依赖安装失败。
    if not defined NO_PAUSE pause
    exit /b 1
)

REM --- 5. 运行应用程序 ---
echo.
echo [成功] 正在启动应用程序...
"%VENV_PY%" src\main.py

if not defined NO_PAUSE pause
exit /b 0
