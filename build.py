import os
import sys
import time
import shutil
import subprocess
import threading
from pathlib import Path
from itertools import cycle

# 配置颜色
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

# 全局状态
stop_spinner = False
build_status = "初始化..."

def spinner_task():
    """显示旋转动画的线程"""
    spinner = cycle(['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'])
    start_time = time.time()
    
    while not stop_spinner:
        elapsed = time.time() - start_time
        sys.stdout.write(f"\r{Colors.CYAN}{next(spinner)}{Colors.ENDC} {build_status}... [{Colors.BLUE}{elapsed:.1f}s{Colors.ENDC}]   ")
        sys.stdout.flush()
        time.sleep(0.1)
    
    # 清除行
    sys.stdout.write(f"\r{' ' * 60}\r")
    sys.stdout.flush()

def run_command(cmd, desc):
    """运行命令并更新状态"""
    global build_status
    build_status = desc
    
    # Windows 下隐藏控制台窗口的 flag (仅用于 subprocess)
    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        shell=True,
        encoding='utf-8'
    )
    
    stdout, stderr = process.communicate()
    
    if process.returncode != 0:
        return False, stdout + stderr
    return True, stdout

def main():
    global stop_spinner, build_status
    
    # 启用 VT100 模式 (Windows 10+)
    os.system('') 

    print(f"{Colors.HEADER}==================================================={Colors.ENDC}")
    print(f"{Colors.HEADER}  TikTok 运营助手构建工具 (Python Mode){Colors.ENDC}")
    print(f"{Colors.HEADER}==================================================={Colors.ENDC}")
    print("")

    # 1. 启动动画线程
    t = threading.Thread(target=spinner_task)
    t.start()

    try:
        # A. 清理环境
        build_status = "Clean old builds"
        if os.path.exists("build"): shutil.rmtree("build")
        if os.path.exists("dist"): shutil.rmtree("dist")
        
        # B. 检查 PyInstaller & Binaries
        build_status = "Check environment"
        
        # Check FFmpeg binaries for bundling
        bin_dir = Path("bin")
        has_ffmpeg = (bin_dir / "ffmpeg.exe").exists()
        has_ffprobe = (bin_dir / "ffprobe.exe").exists()
        
        if not (has_ffmpeg and has_ffprobe):
            print(f"{Colors.WARNING}[WARN] 'bin/ffmpeg.exe' or 'bin/ffprobe.exe' not found.{Colors.ENDC}")
            print(f"{Colors.WARNING}       The generated EXE will allow operations but require FFmpeg in system PATH.{Colors.ENDC}")
            print(f"{Colors.WARNING}       To bundle FFmpeg, create a 'bin' folder and place the executables there.{Colors.ENDC}")
            time.sleep(2) # Give user a chance to read
        else:
             print(f"{Colors.GREEN}[INFO] Found FFmpeg binaries in 'bin/'. They will be bundled.{Colors.ENDC}")

        python_exe = sys.executable
        # 简单检查
        
        # C. 执行构建
        # 注意：这里调用 PyInstaller，将 log 级别设为 ERROR 以减少干扰，但反正我们捕获了输出
        build_status = "Compiling & Packaging (This takes time)"
        cmd = f'"{python_exe}" -m PyInstaller tk-ops-assistant.spec --noconfirm --clean --log-level WARN'
        
        success, output = run_command(cmd, "Building EXE")
        
        stop_spinner = True
        t.join()

        if not success:
            print(f"{Colors.FAIL}[ERROR] 构建失败！{Colors.ENDC}")
            print("错误日志片段：")
            print("-" * 20)
            print(output[-2000:]) # 打印最后 2000 字符
            print("-" * 20)
            sys.exit(1)
        
        # D. 后处理 (.env 复制)
        print(f"{Colors.GREEN}[✓] 编译完成{Colors.ENDC}")
        
        if not os.path.exists("dist"):
            os.makedirs("dist")
            
        if os.path.exists(".env"):
            shutil.copy(".env", os.path.join("dist", ".env"))
            print(f"{Colors.GREEN}[✓] 配置文件已同步{Colors.ENDC}")
        else:
            with open(os.path.join("dist", ".env"), 'w') as f:
                f.write("")
            print(f"{Colors.Warning}[!] 未找到 .env，已创建空文件{Colors.ENDC}")

        exe_path = os.path.abspath(os.path.join("dist", "tk-ops-assistant.exe"))
        
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print("")
            print(f"{Colors.GREEN}{Colors.BOLD}构建成功！{Colors.ENDC}")
            print(f"产物路径: {Colors.BLUE}{exe_path}{Colors.ENDC}")
            print(f"文件大小: {Colors.CYAN}{size_mb:.2f} MB{Colors.ENDC}")
        else:
            print(f"{Colors.FAIL}错误：未找到生成的 EXE 文件！{Colors.ENDC}")
            sys.exit(1)

    except KeyboardInterrupt:
        stop_spinner = True
        t.join()
        print(f"\n{Colors.WARNING}构建已取消{Colors.ENDC}")
        sys.exit(0)
    except Exception as e:
        stop_spinner = True
        t.join()
        print(f"\n{Colors.FAIL}发生未知错误: {e}{Colors.ENDC}")
        sys.exit(1)

if __name__ == "__main__":
    main()
