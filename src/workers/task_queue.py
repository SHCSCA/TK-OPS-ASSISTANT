"""统一任务队列（当前：预留/未在主流程接入）

用途设想：
- 为下载/素材处理/蓝海监测等任务提供统一队列模型
- 支持并发执行、取消、重试、统计导出

说明：
- 目前主流程仍以“各面板独立 worker”为主；该模块暂未被引用。
- 保留此模块是为了后续把多个任务统一编排到一个任务中心。
"""
from enum import Enum
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, Any, List
import uuid
import time
from pathlib import Path
import json


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"      # 等待中
    RUNNING = "running"      # 运行中
    SUCCESS = "success"      # 成功
    FAILED = "failed"        # 失败
    CANCELLED = "cancelled"  # 已取消


@dataclass
class Task:
    """统一任务模型"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    task_type: str = ""       # video_process / blue_ocean / etc
    status: TaskStatus = TaskStatus.PENDING
    
    # 输入与参数
    input_data: Dict[str, Any] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
    
    # 执行信息
    progress: int = 0          # 0-100
    started_at: float = 0.0
    ended_at: float = 0.0
    elapsed: float = 0.0
    
    # 输出与错误
    output_data: Dict[str, Any] = field(default_factory=dict)
    error_msg: str = ""
    retries_left: int = 0
    
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
