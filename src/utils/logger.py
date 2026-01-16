"""日志模块（文件 + 控制台 + UI 实时输出）

目标：
- 所有业务代码统一调用标准 logging（或本模块导出的 logger），避免 print
- 文件日志自动轮转，便于 EXE 环境排障
- 通过 Qt Signal 把日志实时推送到 UI 日志窗口

注意：
- 本模块会 import config，请避免在 config import logger（防止循环依赖）。
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from PyQt5.QtCore import pyqtSignal, QObject
import config


class QtSignalHandler(logging.Handler, QObject):
    """
    自定义 Logging Handler
    将日志消息通过 Qt Signal 发送出去，用于在 UI 界面上显示。
    """
    # 定义信号：发送(日志级别, 格式化后的消息)
    log_signal = pyqtSignal(str)

    def __init__(self):
        logging.Handler.__init__(self)
        QObject.__init__(self)

    def emit(self, record):
        try:
            msg = self.format(record)
            self.log_signal.emit(msg)
        except Exception:
            self.handleError(record)


class LoggerManager:
    """日志管理器 (单例模式推荐)"""
    _instance = None
    _signal_handler = None

    @classmethod
    def setup_logger(cls):
        """配置全局 Logger"""
        if cls._instance:
            return cls._instance

        # 创建根 Logger
        root_logger = logging.getLogger()
        level_name = getattr(config, "LOG_LEVEL", "INFO")
        level = getattr(logging, str(level_name).upper(), logging.INFO)
        root_logger.setLevel(level)
        root_logger.handlers = []  # 清除旧 handler，防止重复输出

        # 1. 格式化器
        formatter = logging.Formatter(config.LOG_FORMAT, datefmt=config.LOG_DATETIME_FORMAT)

        # 2. 文件 Handler (按文件大小轮转，最大 5MB，保留 5 个备份)
        log_file = config.LOG_DIR / "tk_ops_runtime.log"
        time_file_handler = RotatingFileHandler(
            log_file, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8'
        )
        time_file_handler.setFormatter(formatter)
        root_logger.addHandler(time_file_handler)

        # 3. 控制台 Handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        # 4. Qt Signal Handler (UI显示)
        cls._signal_handler = QtSignalHandler()
        cls._signal_handler.setFormatter(formatter)
        root_logger.addHandler(cls._signal_handler)

        cls._instance = root_logger
        return root_logger

    @classmethod
    def get_signal_handler(cls):
        """获取信号 Handler 实例，以便连接槽函数"""
        if not cls._signal_handler:
            cls.setup_logger()
        return cls._signal_handler


# 兼容旧代码接口
class LegacyLogger:
    def __init__(self):
        self.logger = logging.getLogger("tk_ops")
        # 确保初始化
        LoggerManager.setup_logger()
        
    @property
    def log_signal(self):
        # 代理到 QtSignalHandler 的信号
        return LoggerManager.get_signal_handler().log_signal

    def emit(self, level: str, message: str):
        if level.upper() == "INFO": self.logger.info(message)
        elif level.upper() == "ERROR": self.logger.error(message)
        elif level.upper() == "WARNING": self.logger.warning(message)
        elif level.upper() == "DEBUG": self.logger.debug(message)
        else: self.logger.info(f"[{level}] {message}")

    def info(self, msg): self.logger.info(msg)
    def warning(self, msg): self.logger.warning(msg)
    def error(self, msg): self.logger.error(msg)
    def debug(self, msg): self.logger.debug(msg)
    
    def success(self, msg): self.logger.info(f"✅ {msg}")
    def highlight(self, msg): self.logger.info(f"*** {msg} ***")


# 全局实例，替代旧的 LogEmitter
logger = LegacyLogger()
