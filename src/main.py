"""程序入口（启动/异常兜底/全局样式）

职责：
- 解决 PyQt5/sip 在部分环境下的重复加载问题（尤其是 PyInstaller 场景）
- 初始化日志、同步 .env 并热加载 config
- 设置全局异常处理器，尽量把崩溃原因落盘并弹窗提示
- 创建主窗口并进入 Qt 事件循环
"""
import sys
import traceback
import logging


def _ensure_single_sip_module() -> None:
    """确保 sip 只被加载一次。

    在当前环境里，`import sip` 实际会解析到 `PyQt5.sip` 的同一个扩展模块。
    若两个名字分别被导入，会导致同一个 `.pyd` 在进程内初始化两次，从而触发：
    "cannot load module more than once per process"。
    """
    try:
        if "sip" in sys.modules and "PyQt5.sip" not in sys.modules:
            sys.modules["PyQt5.sip"] = sys.modules["sip"]
            return
        if "PyQt5.sip" in sys.modules and "sip" not in sys.modules:
            sys.modules["sip"] = sys.modules["PyQt5.sip"]
            return

        # 两者都没加载时：优先加载 PyQt5.sip 作为“唯一真源”，并别名到 sip。
        try:
            from PyQt5 import sip as sip_mod  # type: ignore
        except Exception:
            sip_mod = None

        if sip_mod is None:
            import importlib

            sip_mod = importlib.import_module("sip")

        sys.modules.setdefault("PyQt5.sip", sip_mod)
        sys.modules.setdefault("sip", sip_mod)
    except Exception:
        # 不阻塞启动；后续如果仍有问题，会在启动日志中给出 traceback
        pass


# 必须在任何 PyQt5 子模块导入之前执行
_ensure_single_sip_module()


from PyQt5.QtWidgets import QApplication, QMessageBox

# 引入日志管理器和全局样式
from utils.logger import LoggerManager, logger
import config
from utils.styles import apply_global_theme

# [已移除] 显式导入 PyQt5.sip 可能导致 PyInstaller 环境下出现 "cannot load module more than once" 错误
# PyInstaller 的 hook-PyQt5 通常能自动处理 sip 依赖
# try:
#     import PyQt5.sip
# except ImportError:
#     pass

# 延迟导入 MainWindow，直到 main() 函数执行，以便捕获导入阶段的错误
# from ui.main_window import MainWindow 


def global_exception_handler(exc_type, exc_value, exc_traceback):
    """
    全局异常捕获钩子
    当程序发生未捕获异常时，记录日志并弹窗提示，防止程序静默崩溃。
    """
    # 忽略键盘中断 (Ctrl+C)
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    logger.error(f"未捕获的异常 (Uncaught Exception):\n{error_msg}")
    
    # 尝试弹窗提示用户
    try:
        app = QApplication.instance()
        if app:
            error_box = QMessageBox()
            error_box.setIcon(QMessageBox.Critical)
            error_box.setWindowTitle("程序运行错误")
            error_box.setText("发生了一个未预期的错误，程序可能需要关闭。")
            error_box.setDetailedText(error_msg)
            error_box.exec_()
    except:
        pass


def main():
    """主程序入口"""
    # 初始化日志系统
    LoggerManager.setup_logger()
    logger.info("正在启动 TikTok 蓝海运营助手...")

    # 同步 .env（补齐关键项/迁移旧 key），避免 README/.env.example 与实际配置漂移
    try:
        config.sync_env_file()
        config.reload_config()
    except Exception:
        pass

    # 启动信息落盘（脱敏）
    try:
        info = config.get_startup_info()
        logger.info(f"启动信息：{info}")
    except Exception:
        pass

    # 关键依赖版本（尽量不影响启动）
    def _safe_ver(mod_name: str) -> str:
        try:
            mod = __import__(mod_name)
            return getattr(mod, "__version__", "unknown")
        except Exception:
            return "unavailable"

    try:
        logger.info(
            "依赖版本：PyQt5=%s, moviepy=%s, yt_dlp=%s, openpyxl=%s",
            _safe_ver("PyQt5"),
            _safe_ver("moviepy"),
            _safe_ver("yt_dlp"),
            _safe_ver("openpyxl"),
        )
    except Exception:
        pass

    # 注册全局异常处理
    sys.excepthook = global_exception_handler

    app = QApplication(sys.argv)
    
    # 设置全局样式表（统一入口，避免局部 setStyleSheet 覆盖主题）
    theme_mode = getattr(config, "THEME_MODE", "dark")
    apply_global_theme(app, theme_mode)

    # 启动时配置缺失提示（中文）
    try:
        missing = config.validate_required_config()
        if missing:
            logger.warning(f"检测到必填配置缺失：{missing}")
            QMessageBox.warning(
                None,
                "配置未完善",
                "检测到部分必填配置缺失：\n- " + "\n- ".join(missing) + "\n\n你仍可进入程序，但相关功能可能不可用。",
            )
    except Exception:
        pass
    
    try:
        # 创建并显示主窗口 (在此处导入，确保环境已就绪)
        from ui.main_window import MainWindow
        window = MainWindow()
        
        # 运行主循环
        logger.info("主界面加载完成，进入事件循环。")
        sys.exit(app.exec_())
    except Exception as e:
        # 这里经常是 ImportError/Qt 依赖问题；务必写入完整堆栈，便于 EXE 环境排查
        try:
            logging.getLogger().exception("启动过程中发生致命错误")
        except Exception:
            pass
        logger.error(f"启动过程中发生致命错误: {str(e)}")
        raise


if __name__ == '__main__':
    # 全局异常捕获 (针对入口级错误)
    try:
        main()
    except ImportError as e:
        # 如果是导入错误（通常为 Qt/sip/二进制依赖问题），输出完整堆栈到日志/控制台
        try:
            detail = traceback.format_exc()
            try:
                logging.getLogger().error(detail)
            except Exception:
                pass
            try:
                print(detail)
            except Exception:
                pass
        except Exception:
            pass

        # 尝试显示原生 MsgBox
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, f"关键模块导入失败: {str(e)}\n请检查环境依赖或重新安装。", "启动错误 (Import Error)", 16)
        except:
            print(f"CRITICAL: {e}")
    except Exception as e:
        # 其他启动错误
        try:
            detail = traceback.format_exc()
            try:
                logging.getLogger().error(detail)
            except Exception:
                pass
            try:
                print(detail)
            except Exception:
                pass
        except Exception:
            pass
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, f"程序启动失败: {str(e)}", "致命错误 (Fatal Error)", 16)
        except:
            print(f"FATAL: {e}")
