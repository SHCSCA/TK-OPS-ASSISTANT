@echo off
chcp 65001 >nul
echo ===================================================
echo   TK运营助手 V3.0 环境升级脚本
echo   (安装 Playwright 浏览器内核 + DeepSeek 依赖)
echo ===================================================
echo.

call venv\Scripts\activate.bat

echo 1. 正在安装/更新 Python 依赖...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ❌ 依赖安装失败，请检查网络或配置。
    pause
    exit /b %errorlevel%
)

echo.
echo 2. 正在安装 Playwright 浏览器内核 (Chromium)...
echo    注意：这可能需要下载约 100MB+ 文件，请耐心等待。
echo.
playwright install chromium
if %errorlevel% neq 0 (
    echo ❌ 浏览器内核安装失败。
    echo 请尝试手动运行: venv\Scripts\playwright install chromium
    pause
    exit /b %errorlevel%
)

echo.
echo ✅ V3.0 环境升级完成！
echo    后续请像往常一样运行 start.bat 即可。
echo.
pause
