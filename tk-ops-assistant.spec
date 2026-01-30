# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, copy_metadata, collect_submodules, collect_data_files
import sys
from pathlib import Path

# PyInstaller 执行 spec 时不一定提供 __file__，做兼容兜底
project_root = (
    Path(__file__).resolve().parent
    if '__file__' in globals()
    else Path.cwd()
)

# 确保能发现 src 目录下的顶层包（ui/utils/workers 等）
src_path = str(project_root / 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

datas = []
binaries = []
# [关键修改] 移除了 'PyQt5.sip' (由 runtime-hook 处理)，保留其他业务库
hiddenimports = ['pandas', 'openpyxl', 'PIL', 'yt_dlp', 'openai']

# imageio_ffmpeg 移除 (改用 bin 目录或 PATH 自带 ffmpeg)

# qt_material 需要额外资源（主题/样式）
datas += collect_data_files('qt_material')
hiddenimports += collect_submodules('qt_material')

# Playwright 依赖驱动与子模块（避免按需功能在 EXE 中导入失败）
hiddenimports += collect_submodules('playwright')
datas += collect_data_files('playwright')

# 延迟加载模块（importlib 动态导入）需要显式收集
hiddenimports += collect_submodules('ui')
hiddenimports += collect_submodules('workers')
hiddenimports += collect_submodules('api')
hiddenimports += collect_submodules('services')
hiddenimports += collect_submodules('utils')
hiddenimports += collect_submodules('tts')
hiddenimports += collect_submodules('db')
hiddenimports += collect_submodules('video')
hiddenimports += collect_submodules('ai')

# [修复] 解决依赖库元数据缺失问题
datas += copy_metadata('requests')
# 兼容部分 pandas 版本的依赖
datas += copy_metadata('numpy') 
datas += copy_metadata('pandas')

# 包含 bundled bin 目录 (FFmpeg)
bin_path = project_root / 'bin'
if bin_path.exists():
    datas.append((str(bin_path), 'bin'))

# 将 .env 一并打进去
env_path = project_root / '.env'
if env_path.exists():
    datas.append((str(env_path), '.'))

# 将 icon.ico 一并打进去（用于窗口图标）
icon_path = project_root / 'icon.ico'
if icon_path.exists():
    datas.append((str(icon_path), '.'))

a = Analysis(
    ['src\\main.py'],
    pathex=['src'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(project_root / 'pyinstaller_hooks' / 'pyi_rth_sip_singleton.py')],
    excludes=['tkinter', 'matplotlib', 'scipy', 'notebook', 'share'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='tk-ops-assistant',
    icon=str(project_root / 'icon.ico'),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False, # GUI 模式（可分发直接启动）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
