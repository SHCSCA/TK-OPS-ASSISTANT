"""统一任务队列管理器 (Core Upgrade)

功能：
- 管理异步任务 (Asynchronous Task Orchestration)
- UI 线程分离 (Rendering vs Networking isolation)
- 实时状态回调 (Progress & Status signalling)

技术实现：
- 基于 QThreadPool 做各种耗时操作
- 使用 QObject + Signals 进行主线程通信
"""
from enum import Enum
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, Any, List, Callable
import uuid
import time
import logging
import traceback

from PyQt5.QtCore import QObject, pyqtSignal, QRunnable, QThreadPool, QMetaObject, Qt, Q_ARG

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskPayload:
    """任务载荷 (Pure Data)"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "Untitled Task"
    type: str = "generic" 
    status: TaskStatus = TaskStatus.PENDING
    progress: int = 0
    created_at: float = field(default_factory=time.time)
    
    # 执行回调
    target_func: Optional[Callable] = None
    args: tuple = ()
    kwargs: Dict = field(default_factory=dict)
    
    # 结果
    result: Any = None
    error: str = ""

class TaskSignals(QObject):
    """任务信号槽"""
    status_changed = pyqtSignal(str, object) # task_id, NEW_STATUS
    progress_updated = pyqtSignal(str, int)  # task_id, progress
    finished = pyqtSignal(str, object)       # task_id, result_data
    error = pyqtSignal(str, str)             # task_id, error_msg

class StartableTask(QRunnable):
    """可执行任务包装器"""
    def __init__(self, payload: TaskPayload, signals: TaskSignals):
        super().__init__()
        self.payload = payload
        self.signals = signals
        self.setAutoDelete(True)

    def run(self):
        try:
            self._emit_status(TaskStatus.RUNNING)
            if self.payload.target_func:
                # 执行具体业务逻辑
                res = self.payload.target_func(*self.payload.args, **self.payload.kwargs)
                self.payload.result = res
                self._emit_finished(res)
            else:
                # 空任务模拟
                time.sleep(1)
                self._emit_finished(None)
        except Exception as e:
            err_msg = str(e)
            traceback.print_exc()
            self.payload.error = err_msg
            self.signals.error.emit(self.payload.id, err_msg)
            self._emit_status(TaskStatus.FAILED)

    def _emit_status(self, status: TaskStatus):
        self.payload.status = status
        # 注意：QRunnable 在子线程，emit 默认是线程安全的 queued connection
        self.signals.status_changed.emit(self.payload.id, status)

    def _emit_finished(self, result):
        self.payload.status = TaskStatus.SUCCESS
        self.signals.finished.emit(self.payload.id, result)
        self.signals.status_changed.emit(self.payload.id, TaskStatus.SUCCESS)

class TaskManager(QObject):
    """全局任务管理器 (Singleton)"""
    _instance = None
    
    # 对外统一信号
    task_updated = pyqtSignal(str, str) # id, status_str
    
    def __init__(self):
        super().__init__()
        self.pool = QThreadPool.globalInstance()
        # 限制并发数，避免卡死
        self.pool.setMaxThreadCount(4)
        self.top_signals = TaskSignals()
        
        # 串联内部信号
        self.top_signals.status_changed.connect(self._on_status_changed)
        self.tasks: Dict[str, TaskPayload] = {}

    @classmethod
    def instance(cls):
        if not cls._instance:
            cls._instance = TaskManager()
        return cls._instance

    def submit(self, func, name="Task", *args, **kwargs) -> str:
        """提交一个新任务"""
        payload = TaskPayload(
            name=name,
            target_func=func,
            args=args,
            kwargs=kwargs
        )
        self.tasks[payload.id] = payload
        
        runner = StartableTask(payload, self.top_signals)
        self.pool.start(runner)
        
        # 立即返回 ID
        return payload.id

    def _on_status_changed(self, task_id, status):
        # 转发信号给 UI
        self.task_updated.emit(task_id, status.value)

    def get_task(self, task_id) -> Optional[TaskPayload]:
        return self.tasks.get(task_id)


    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:8]
    
    def to_dict(self) -> Dict[str, Any]:
        """转为字典（用于 JSON 导出）"""
        d = asdict(self)
        d['status'] = self.status.value
        return d
    
    def elapsed_seconds(self) -> float:
        """返回已耗时（秒）"""
        if self.status == TaskStatus.RUNNING:
            return time.time() - self.started_at
        return self.elapsed


class TaskQueue:
    """任务队列管理器（支持并发执行、取消、重试）"""
    
    def __init__(self, max_concurrent: int = 1):
        self.max_concurrent = max(1, max_concurrent)
        self.tasks: Dict[str, Task] = {}
        self.running: List[str] = []  # 正在运行的 task_id
        self.should_stop = False
    
    def add_task(self, task: Task) -> str:
        """添加任务到队列"""
        self.tasks[task.id] = task
        return task.id
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return self.tasks.get(task_id)
    
    def list_tasks(self, status: TaskStatus = None) -> List[Task]:
        """列出所有任务（可按状态筛选）"""
        if status is None:
            return list(self.tasks.values())
        return [t for t in self.tasks.values() if t.status == status]
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = self.tasks.get(task_id)
        if not task:
            return False
        if task.status == TaskStatus.RUNNING:
            task.status = TaskStatus.CANCELLED
            self.running.remove(task_id)
            return True
        return False
    
    def update_task_progress(self, task_id: str, progress: int) -> bool:
        """更新进度 0-100"""
        task = self.tasks.get(task_id)
        if task:
            task.progress = max(0, min(100, progress))
            return True
        return False
    
    def mark_success(self, task_id: str, output: Dict[str, Any] = None):
        """标记任务成功"""
        task = self.tasks.get(task_id)
        if task:
            task.status = TaskStatus.SUCCESS
            task.ended_at = time.time()
            task.elapsed = task.ended_at - task.started_at
            task.output_data = output or {}
            if task_id in self.running:
                self.running.remove(task_id)
    
    def mark_failed(self, task_id: str, error_msg: str = "", retry: bool = True):
        """标记任务失败"""
        task = self.tasks.get(task_id)
        if task:
            task.error_msg = error_msg
            task.ended_at = time.time()
            task.elapsed = task.ended_at - task.started_at
            if task_id in self.running:
                self.running.remove(task_id)
            
            if retry and task.retries_left > 0:
                task.retries_left -= 1
                task.status = TaskStatus.PENDING
            else:
                task.status = TaskStatus.FAILED
    
    def export_results(self, output_path: str = None) -> str:
        """导出所有任务结果为 JSON"""
        if output_path is None:
            output_path = f"task_results_{int(time.time())}.json"
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        results = {
            'exported_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'summary': {
                'total': len(self.tasks),
                'success': len(self.list_tasks(TaskStatus.SUCCESS)),
                'failed': len(self.list_tasks(TaskStatus.FAILED)),
                'cancelled': len(self.list_tasks(TaskStatus.CANCELLED)),
                'pending': len(self.list_tasks(TaskStatus.PENDING)),
            },
            'tasks': [t.to_dict() for t in self.tasks.values()]
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        return str(output_path)
    
    def statistics(self) -> Dict[str, Any]:
        """获取队列统计信息"""
        tasks = list(self.tasks.values())
        success_count = len([t for t in tasks if t.status == TaskStatus.SUCCESS])
        failed_count = len([t for t in tasks if t.status == TaskStatus.FAILED])
        
        elapsed_list = [t.elapsed for t in tasks if t.elapsed > 0]
        avg_elapsed = sum(elapsed_list) / len(elapsed_list) if elapsed_list else 0
        
        return {
            'total': len(tasks),
            'success': success_count,
            'failed': failed_count,
            'pending': len([t for t in tasks if t.status == TaskStatus.PENDING]),
            'running': len(self.running),
            'avg_elapsed': avg_elapsed,
        }
