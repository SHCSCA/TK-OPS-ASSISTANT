"""PyInstaller runtime-hook: 统一 sip / PyQt5.sip，避免同一扩展被重复加载。

该问题在 Windows + PyQt5 场景常见：同一个 sip 扩展可能被以 `sip` 与 `PyQt5.sip`
两种名字导入；若分别触发初始化，会报：
"cannot load module more than once per process"。

Runtime-hook 会在主脚本执行前运行，因此能尽量在所有依赖导入之前完成别名映射。
"""

from __future__ import annotations

import sys


def _ensure_single_sip_module() -> None:
    try:
        # 若已有其一，直接把另一名字指向同一对象
        if "PyQt5.sip" in sys.modules and "sip" not in sys.modules:
            sys.modules["sip"] = sys.modules["PyQt5.sip"]
            return
        if "sip" in sys.modules and "PyQt5.sip" not in sys.modules:
            sys.modules["PyQt5.sip"] = sys.modules["sip"]
            return

        # 两者都未加载：优先加载 PyQt5.sip 作为“唯一真源”
        try:
            from PyQt5 import sip as sip_mod  # type: ignore
        except Exception:
            sip_mod = None

        if sip_mod is None:
            # 兜底：尝试顶层 sip（不同环境下可能存在/不存在）
            import importlib

            sip_mod = importlib.import_module("sip")

        sys.modules.setdefault("PyQt5.sip", sip_mod)
        sys.modules.setdefault("sip", sip_mod)
    except Exception:
        # 不阻塞启动；如果仍失败，入口处会记录更完整的 traceback
        return


_ensure_single_sip_module()
