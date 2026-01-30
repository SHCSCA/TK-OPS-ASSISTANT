# 独立 EXE 打包指南 (Standalone Packaging Guide)

本指南用于说明如何将 `TK-OPS-Assistant` 打包为免安装、零依赖的 `.exe` 文件。

## 前置要求

1.  **环境准备**:
    *   已安装 Python 3.10+
    *   已创建并激活虚拟环境 (`start.bat` 会自动完成)
    *   已安装所有依赖: `pip install -r requirements.txt`

2.  **FFmpeg 准备 (关键)**:
    为了确保打包后的程序在没有安装 FFmpeg 的电脑上也能处理视频，**强烈建议**将 FFmpeg 二进制文件打包进程序。
    
    *   **步骤 1**: 在项目根目录下创建一个名为 `bin` 的文件夹。
    *   **步骤 2**: 下载 Windows 版 FFmpeg (推荐 gyan.dev 或 releases)。
    *   **步骤 3**: 解压并提取 `ffmpeg.exe` 和 `ffprobe.exe`。
    *   **步骤 4**: 将这两个文件放入 `bin/` 文件夹中。
    
    最终结构应如下所示：
    ```
    tk-ops-assistant/
    ├── bin/
    │   ├── ffmpeg.exe
    │   └── ffprobe.exe
    ├── src/
    ├── build.bat
    └── ...
    ```

## 执行打包

1.  打开终端（或 CMD/PowerShell）。
2.  运行打包脚本：
    ```powershell
    .\build.bat
    ```
3.  脚本会自动：
    *   清理旧的构建文件 (`build/`, `dist/`)。
    *   检测 `bin/` 目录下的 FFmpeg 文件。
    *   调用 PyInstaller 进行打包。

## 产物说明

*   **输出位置**: `dist/tk-ops-assistant/` 文件夹。
*   **主程序**: `dist/tk-ops-assistant/tk-ops-assistant.exe`。
*   **分发**: 您可以将整个 `tk-ops-assistant` 文件夹压缩为 zip 发送给通过户。用户解压后直接运行 exe 即可，无需安装 Python 或 FFmpeg。

## 故障排除

*   **FFmpeg 未找到**: 如果运行 exe 时提示 FFmpeg 错误，请检查是否在打包前创建了 `bin` 目录。如果没有打包进去，用户需要在自己的电脑上安装 FFmpeg 并配置环境变量。
*   **依赖缺失**: 如果启动时黑屏或闪退，请查看 `Logs/` 目录下的日志文件。
