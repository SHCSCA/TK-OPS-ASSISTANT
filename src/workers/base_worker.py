"""QThread Worker 基类

统一约定：
- 子类优先实现 `_run_impl()`，由基类 `run()` 做异常兜底与结束信号收口
- 通过 `emit_log/emit_error/emit_progress/emit_finished` 与 UI 通信

兼容性：
- 保留历史信号 `log_signal/progress_signal/error_signal/finished_signal`
- 新增 `data_signal/done_signal` 用于更结构化的结果回传
"""
from PyQt5.QtCore import QThread, pyqtSignal
import logging

# worker 专用 logger（写文件日志 + 控制台；UI 展示由信号负责）
worker_logger = logging.getLogger("tk_ops.worker")


class BaseWorker(QThread):
    """
    QThread 基类
    负责处理所有后台任务的通用信号和生命周期管理。
    """
    
    # 定义通用信号
    log_signal = pyqtSignal(str)      # 发送日志消息到 UI (Legacy support)
    progress_signal = pyqtSignal(int)  # 发送进度 (0-100)
    error_signal = pyqtSignal(str)     # 发送错误消息
    finished_signal = pyqtSignal()     # 任务完成信号

    # 新增：统一结果与完成信号（不破坏旧接口）
    data_signal = pyqtSignal(object)   # 统一结果载荷（list/dict/str 皆可）
    done_signal = pyqtSignal(bool, str)  # (ok, message)
    
    def __init__(self):
        super().__init__()
        self.is_running = True
        self.current_progress = 0
        self._finished_emitted = False
    
    def run(self):
        """统一 run 入口：子类实现 _run_impl()，这里负责异常兜底。"""
        try:
            impl = getattr(self, "_run_impl", None)
            if callable(impl):
                impl()
            else:
                # 兼容：如果子类仍然重写了 run，这里不会执行到。
                self.emit_error("Worker 未实现 _run_impl()")
                self.emit_finished(False, "Worker 未实现 _run_impl()")
        except Exception as e:
            self.emit_error(f"后台任务异常：{e}")
            self.emit_finished(False, f"后台任务异常：{e}")

    def should_stop(self) -> bool:
        """统一的停止判定（兼容 is_running 与 requestInterruption）。"""
        try:
            if self.isInterruptionRequested():
                return True
        except Exception:
            pass
        return not bool(self.is_running)
    
    def stop(self):
        """优雅停止线程"""
        self.is_running = False
        try:
            self.requestInterruption()
        except Exception:
            pass

        worker_logger.info(f"{self.__class__.__name__} 收到停止信号")

        # 给线程一个合理的退出窗口，避免 UI 永久卡住
        try:
            self.wait(3000)
        except Exception:
            try:
                self.wait()
            except Exception:
                pass
    
    def emit_log(self, message: str) -> None:
        """
        发送日志消息
        同时发送给 UI 信号和文件日志
        """
        if self.should_stop():
            return
        try:
            self.log_signal.emit(message)
        except Exception:
            # UI 可能已销毁，避免线程异常退出
            pass
        worker_logger.info(message)
    
    def emit_error(self, message: str) -> None:
        """发送错误消息并记录日志（UI + 文件）。"""
        if self.should_stop():
            return
        try:
            self.error_signal.emit(message)
            self.log_signal.emit(f"❌ {message}")
        except Exception:
            pass
        worker_logger.error(message)

    def emit_progress(self, progress: int) -> None:
        """
        Emit progress update safely
        
        Args:
            progress: Progress percentage (0-100)
        """
        if self.should_stop():
            return
        self.current_progress = max(0, min(100, progress))
        try:
            self.progress_signal.emit(self.current_progress)
        except Exception:
            pass
    
    def emit_finished(self, ok: bool = True, message: str = "") -> None:
        """统一结束信号。

        - done_signal(ok, message)
        - finished_signal()（兼容旧 UI）
        """
        if self._finished_emitted:
            return
        self._finished_emitted = True
        try:
            self.done_signal.emit(bool(ok), str(message or ""))
        except Exception:
            pass
        try:
            self.finished_signal.emit()
        except Exception:
            pass
