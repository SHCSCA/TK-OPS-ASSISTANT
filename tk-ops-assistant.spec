# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, copy_metadata
from pathlib import Path

# PyInstaller 执行 spec 时不一定提供 __file__，做兼容兜底
project_root = (
    Path(__file__).resolve().parent
    if '__file__' in globals()
    else Path.cwd()
)

datas = []
binaries = []
# [关键修改] 移除了 'PyQt5.sip' (由 runtime-hook 处理)，保留其他业务库
hiddenimports = ['pandas', 'openpyxl', 'PIL', 'moviepy', 'yt_dlp', 'openai', 'imageio_ffmpeg']

# imageio_ffmpeg 必须收集，因为它包含 ffmpeg 二进制文件
tmp_ret = collect_all('imageio_ffmpeg')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# [修复] 解决依赖库元数据缺失问题
datas += copy_metadata('imageio')
datas += copy_metadata('moviepy')
datas += copy_metadata('requests')
# 兼容部分 pandas 版本的依赖
datas += copy_metadata('numpy') 
datas += copy_metadata('pandas')

# 将 .env 一并打进去
env_path = project_root / '.env'
if env_path.exists():
    datas.append((str(env_path), '.'))

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
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True, # [调试] 开启控制台以捕获闪退日志
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
