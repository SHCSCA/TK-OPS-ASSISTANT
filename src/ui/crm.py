"""
账号矩阵 CRM (V2.0)
管理多个 TikTok 账号，状态可视化，发布打卡功能
"""
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QPushButton,
    QDialog,
    QLineEdit,
    QFormLayout,
    QComboBox,
    QTextEdit,
    QMessageBox,
    QSizePolicy,
    QFrame,
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QIcon
from datetime import datetime
import sqlite3
import logging
from pathlib import Path

import config
from api.ai_assistant import analyze_comment_lead

logger = logging.getLogger(__name__)


STATUS_LABELS = {
    "active": "正常",
    "shadowban": "限流",
    "suspended": "封禁",
}


def _db_path() -> str:
    try:
        return str(getattr(config, "ASSET_LIBRARY_DIR", Path("AssetLibrary")) / "assets.db")
    except Exception:
        return "AssetLibrary/assets.db"

class AccountItemWidget(QWidget):
    """自定义列表项：展示账号状态和操作"""
    
    def __init__(self, account_data, parent_widget, parent=None):
        super().__init__(parent)
        self.account = account_data
        self.parent_widget = parent_widget
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)
        
        # 状态指示器
        self.lbl_status = QLabel()
        self.lbl_status.setFixedSize(14, 14)
        # 使用全局主题：通过动态属性驱动颜色
        self.lbl_status.setProperty("role", "status-dot")
        self._apply_status_dot()
        
        # 账号信息（拆分字段，避免“全挤在一行”）
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        self.lbl_name = QLabel(f"@{self.account['username']}")
        self.lbl_name.setObjectName("h2")
        self.lbl_name.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(10)

        ip_text = self.account.get('proxy_ip') or '本地'
        status_text = STATUS_LABELS.get(self.account.get("status", "active"), "未知")
        last_post = self.account.get('last_post_date', '从未发布')

        self.lbl_ip = QLabel(f"IP：{ip_text}")
        self.lbl_ip.setProperty("variant", "muted")
        self.lbl_ip.setMinimumWidth(140)

        self.lbl_status_text = QLabel(f"状态：{status_text}")
        self.lbl_status_text.setProperty("variant", "muted")
        self.lbl_status_text.setMinimumWidth(90)

        self.lbl_last = QLabel(f"上次：{last_post}")
        self.lbl_last.setProperty("variant", "muted")
        self.lbl_last.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        meta_row.addWidget(self.lbl_ip)
        meta_row.addWidget(self.lbl_status_text)
        meta_row.addWidget(self.lbl_last, 1)

        info_layout.addWidget(self.lbl_name)
        info_layout.addLayout(meta_row)
        
        # 打卡按钮（避免 emoji 在部分字体下显示成横线）
        self.btn_checkin = QPushButton("今日打卡")
        self.btn_checkin.setMinimumWidth(92)
        # 注意：全局 QSS 默认 padding=10px，会把 30px 高度的按钮文字裁切成“横线”
        self.btn_checkin.setFixedHeight(36)
        self.btn_checkin.setToolTip("打卡：记录今天已发布一次（更新上次发布时间 + 今日发布数）。")
        self.btn_checkin.clicked.connect(self.on_checkin)
        
        # 组装
        layout.addWidget(self.lbl_status)
        layout.addLayout(info_layout)
        layout.addStretch()
        layout.addWidget(self.btn_checkin)
        
    def _apply_status_dot(self) -> None:
        """根据账号状态刷新圆点颜色（走全局 QSS）。"""
        status = self.account.get('status', 'active')
        try:
            self.lbl_status.setProperty("state", status)
            # 避免在初始化时频繁 polish 导致问题，利用 Qt 自动机制
            if self.lbl_status.isVisible():
                self.lbl_status.style().unpolish(self.lbl_status)
                self.lbl_status.style().polish(self.lbl_status)
        except Exception:
            pass

    def on_checkin(self):
        """打卡操作"""
        try:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            with sqlite3.connect(_db_path()) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE accounts 
                    SET last_post_date = ?, today_post_count = today_post_count + 1
                    WHERE id = ?
                """, (now_str, self.account['id']))
                conn.commit()
            
            # 更新 UI
            status_text = STATUS_LABELS.get(self.account.get("status", "active"), "未知")
            try:
                self.lbl_status_text.setText(f"状态：{status_text}")
                self.lbl_last.setText(f"上次：{now_str}")
            except Exception:
                pass
            self.btn_checkin.setText("已打卡")
            self.btn_checkin.setDisabled(True)
            
            logger.info(f"[CRM] 账号 @{self.account['username']} 完成打卡")
            
        except Exception as e:
            logger.error(f"打卡失败: {e}")
            QMessageBox.warning(self, "打卡失败", str(e))


class AddAccountDialog(QDialog):
    """添加账号对话框"""
    
    def __init__(self, parent=None, initial_data: dict | None = None):
        super().__init__(parent)
        self._initial = initial_data or {}
        self._editing_id = self._initial.get("id")
        self.setWindowTitle("编辑 TikTok 账号" if self._editing_id else "添加 TikTok 账号")
        self.setFixedSize(400, 300)
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout(self)
        
        self.input_username = QLineEdit()
        self.input_username.setPlaceholderText("例如: tiktok_shop_us_01")
        
        self.input_proxy = QLineEdit()
        self.input_proxy.setPlaceholderText("例如: 192.168.1.101:7890")
        
        self.combo_status = QComboBox()
        self.combo_status.addItem("正常", "active")
        self.combo_status.addItem("限流（Shadowban）", "shadowban")
        self.combo_status.addItem("封禁/停用", "suspended")
        
        self.input_notes = QTextEdit()
        self.input_notes.setPlaceholderText("备注信息...")
        self.input_notes.setMaximumHeight(80)
        
        layout.addRow("账号名 (@ID):", self.input_username)
        layout.addRow("代理 IP:", self.input_proxy)
        layout.addRow("状态:", self.combo_status)
        layout.addRow("备注:", self.input_notes)

        # 回填（编辑模式）
        try:
            if self._initial.get("username"):
                self.input_username.setText(str(self._initial.get("username")))
            if self._initial.get("proxy_ip"):
                self.input_proxy.setText(str(self._initial.get("proxy_ip")))
            if self._initial.get("status"):
                idx = self.combo_status.findData(self._initial.get("status"))
                if idx >= 0:
                    self.combo_status.setCurrentIndex(idx)
            if self._initial.get("notes"):
                self.input_notes.setPlainText(str(self._initial.get("notes")))
        except Exception:
            pass
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("保存")
        btn_save.clicked.connect(self.accept)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        layout.addRow(btn_layout)

    def get_data(self):
        """返回输入的数据"""
        return {
            'username': self.input_username.text().strip(),
            'proxy_ip': self.input_proxy.text().strip(),
            'status': self.combo_status.currentData() or "active",
            'notes': self.input_notes.toPlainText().strip()
        }


class CRMWidget(QWidget):
    """账号矩阵管理主界面"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        # 延迟加载数据，避免阻塞主界面启动
        QTimer.singleShot(100, self.load_accounts)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题栏
        title_bar = QHBoxLayout()
        title_label = QLabel("账号矩阵")
        title_label.setObjectName("h1")
        
        btn_add = QPushButton("添加账号")
        btn_add.setFixedHeight(35)
        btn_add.setProperty("variant", "primary")
        btn_add.clicked.connect(self.add_account_dialog)

        self.btn_edit = QPushButton("编辑")
        self.btn_edit.setFixedHeight(35)
        self.btn_edit.setEnabled(False)
        self.btn_edit.clicked.connect(self.edit_selected_account)

        self.btn_delete = QPushButton("删除")
        self.btn_delete.setFixedHeight(35)
        self.btn_delete.setProperty("variant", "danger")
        self.btn_delete.setEnabled(False)
        self.btn_delete.clicked.connect(self.delete_selected_account)
        
        btn_refresh = QPushButton("刷新")
        btn_refresh.setFixedHeight(35)
        btn_refresh.clicked.connect(self.load_accounts)
        
        title_bar.addWidget(title_label)
        title_bar.addStretch()
        title_bar.addWidget(btn_add)
        title_bar.addWidget(self.btn_edit)
        title_bar.addWidget(self.btn_delete)
        title_bar.addWidget(btn_refresh)
        
        # 列表
        self.list_widget = QListWidget()
        self.list_widget.setObjectName("ContentList")
        self.list_widget.setSelectionMode(QListWidget.SingleSelection)
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        try:
            self.list_widget.setSpacing(8)
        except Exception:
            pass
        
        layout.addLayout(title_bar)
        layout.addWidget(self.list_widget)

        # 评论监控面板与私信任务面板已移除，迁移至【互动/获客中心】

    def load_accounts(self):
        """从数据库加载账号列表"""
        try:
            dbp = _db_path()
            logger.info(f"[CRM] 使用数据库：{dbp}")
            
            if not Path(dbp).exists():
                logger.warning(f"[CRM] 数据库文件不存在: {dbp}")
                return

            logger.info("[CRM] 正在连接数据库(设置超时5秒)...")
            # 增加 timeout 参数，防止死锁无限等待
            with sqlite3.connect(dbp, timeout=5.0) as conn:
                logger.info("[CRM] API: 连接建立，准备查询...")
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, username, status, proxy_ip, last_post_date, notes
                    FROM accounts
                    ORDER BY created_at DESC
                    """
                )
                accounts = cursor.fetchall()
                logger.info(f"[CRM] 查询成功，获取到 {len(accounts)} 个账号")
            
            self.list_widget.clear()
            if not accounts:
                # 显示空状态提示
                item = QListWidgetItem("暂无账号，点击右上角【添加账号】开始管理")
                item.setFlags(Qt.NoItemFlags)
                self.list_widget.addItem(item)
                return
            
            logger.info("[CRM] 正在渲染列表...")
            # self.list_widget.setUpdatesEnabled(False) # 移除去除优化，排查卡顿
            for i, acc_data in enumerate(accounts):
                # logger.debug(f"[CRM] 渲染第 {i+1} 个账号") 
                acc_dict = {
                    'id': acc_data[0],
                    'username': acc_data[1],
                    'status': acc_data[2],
                    'proxy_ip': acc_data[3],
                    'last_post_date': acc_data[4] or '从未发布',
                    'notes': acc_data[5]
                }
                
                item = QListWidgetItem(self.list_widget)
                item.setSizeHint(QSize(0, 86))
                item.setData(Qt.UserRole, int(acc_dict["id"]))
                widget = AccountItemWidget(acc_dict, self)
                self.list_widget.setItemWidget(item, widget)
            # self.list_widget.setUpdatesEnabled(True)
            logger.info("[CRM] 列表渲染完成")

            self._on_selection_changed()
            logger.info("[CRM] load_accounts 函数执行结束")
                
        except Exception as e:
            logger.error(f"加载账号失败: {e}")
            # QMessageBox.critical(self, "加载失败", f"无法加载账号列表:\n{e}")

    def _init_comment_monitor(self) -> None:
        """初始化评论监控定时器。"""
        self._comment_timer = QTimer(self)
        self._comment_timer.setInterval(5000)
        self._comment_timer.timeout.connect(self._poll_comments)
        self._load_dm_tasks()

    def _toggle_comment_monitor(self) -> None:
        """开关评论监控。"""
        if self._comment_timer.isActive():
            self._comment_timer.stop()
            self.comment_toggle_btn.setText("开始监控")
        else:
            self._comment_timer.start()
            self.comment_toggle_btn.setText("监控中...")

    def _poll_comments(self) -> None:
        """轮询最新评论并进行意向分级。"""
        try:
            dbp = _db_path()
            with sqlite3.connect(dbp) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, author, content, created_at
                    FROM comments
                    WHERE id > ?
                    ORDER BY id ASC
                    LIMIT 50
                    """,
                    (self._last_comment_id,)
                )
                rows = cursor.fetchall()

            if not rows:
                return

            for row in rows:
                cid, author, content, created_at = row
                analysis = analyze_comment_lead(content or "")
                lead_tier = int(analysis.get("lead_tier", 3))
                reply = str(analysis.get("reply", "") or "")

                self._update_comment_tier(cid, lead_tier)
                self._append_comment_alert(author, content, created_at, lead_tier, reply)
                if lead_tier == 1:
                    self._enqueue_dm_task(cid, reply)
                self._last_comment_id = max(self._last_comment_id, int(cid))
        except Exception as e:
            logger.error(f"评论监控失败: {e}")

    def _update_comment_tier(self, comment_id: int, lead_tier: int) -> None:
        """更新评论意向等级。"""
        try:
            dbp = _db_path()
            with sqlite3.connect(dbp) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE comments SET lead_tier = ? WHERE id = ?",
                    (int(lead_tier), int(comment_id)),
                )
                conn.commit()
        except Exception:
            pass

    def _append_comment_alert(self, author: str, content: str, created_at: str, lead_tier: int, reply: str = "") -> None:
        """将评论追加到监控列表。"""
        try:
            tag = "T1" if lead_tier == 1 else "T2" if lead_tier == 2 else "T3"
            display = f"[{tag}] {author or '未知'}：{content} ({created_at})"
            if reply:
                display += f" | 回复建议：{reply}"
            item = QListWidgetItem(display)
            if lead_tier == 1:
                item.setForeground(Qt.red)
            elif lead_tier == 2:
                item.setForeground(Qt.darkYellow)
            self.comment_list.insertItem(0, item)
        except Exception:
            pass

    def _enqueue_dm_task(self, comment_id: int, reply: str = "") -> None:
        """创建私信任务（仅高意向）。"""
        try:
            if not bool(getattr(config, "COMMENT_DM_ENABLED", True)):
                return
            dbp = _db_path()
            with sqlite3.connect(dbp) as conn:
                cursor = conn.cursor()
                self._ensure_dm_tasks_table(cursor)
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO dm_tasks (comment_id, status, message)
                    VALUES (?, 'pending', ?)
                    """,
                    (int(comment_id), (reply or getattr(config, "COMMENT_DM_TEMPLATE", "")).strip()),
                )
                conn.commit()
            self._load_dm_tasks()
        except Exception as e:
            logger.error(f"创建私信任务失败: {e}")

    def _load_dm_tasks(self) -> None:
        """加载私信任务列表。"""
        try:
            self.dm_list.clear()
            dbp = _db_path()
            with sqlite3.connect(dbp) as conn:
                cursor = conn.cursor()
                self._ensure_dm_tasks_table(cursor)
                cursor.execute(
                    """
                    SELECT id, comment_id, status, message, created_at
                    FROM dm_tasks
                    ORDER BY created_at DESC
                    LIMIT 100
                    """
                )
                rows = cursor.fetchall()

            for row in rows:
                tid, cid, status, message, created_at = row
                item = QListWidgetItem(f"#{tid} | 评论ID:{cid} | {status} | {message} | {created_at}")
                item.setData(Qt.UserRole, int(tid))
                if status == "pending":
                    item.setForeground(Qt.red)
                self.dm_list.addItem(item)
        except Exception as e:
            logger.error(f"加载私信任务失败: {e}")

    def _mark_dm_done(self) -> None:
        """标记选中私信任务为已处理。"""
        try:
            item = self.dm_list.currentItem()
            if not item:
                return
            task_id = item.data(Qt.UserRole)
            dbp = _db_path()
            with sqlite3.connect(dbp) as conn:
                cursor = conn.cursor()
                self._ensure_dm_tasks_table(cursor)
                cursor.execute(
                    "UPDATE dm_tasks SET status='done', handled_at=CURRENT_TIMESTAMP WHERE id=?",
                    (int(task_id),),
                )
                conn.commit()
            self._load_dm_tasks()
        except Exception as e:
            logger.error(f"更新私信任务失败: {e}")

    def _ensure_dm_tasks_table(self, cursor) -> None:
        """保证私信任务表存在（防止迁移未执行导致 UI 异常）。"""
        try:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS dm_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    comment_id INTEGER UNIQUE,
                    status TEXT DEFAULT 'pending',
                    message TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    handled_at DATETIME
                )
                """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_dm_tasks_status ON dm_tasks(status)")
        except Exception:
            pass

    def add_account_dialog(self):
        """打开添加账号对话框"""
        dialog = AddAccountDialog(self)
        
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            
            if not data['username']:
                QMessageBox.warning(self, "输入错误", "账号名不能为空")
                return
            
            try:
                with sqlite3.connect(_db_path()) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO accounts (username, status, proxy_ip, notes)
                        VALUES (?, ?, ?, ?)
                    """, (data['username'], data['status'], data['proxy_ip'], data['notes']))
                    conn.commit()
                
                logger.info(f"[CRM] 新增账号: @{data['username']}")
                self.load_accounts()
                
            except sqlite3.IntegrityError:
                QMessageBox.warning(self, "重复账号", "该账号名已存在")
            except Exception as e:
                logger.error(f"添加账号失败: {e}")
                QMessageBox.critical(self, "添加失败", str(e))

    def _selected_account_id(self) -> int | None:
        item = self.list_widget.currentItem()
        if not item:
            return None
        try:
            return int(item.data(Qt.UserRole))
        except Exception:
            return None

    def _fetch_account_by_id(self, account_id: int) -> dict | None:
        try:
            with sqlite3.connect(_db_path()) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, username, status, proxy_ip, last_post_date, notes
                    FROM accounts
                    WHERE id = ?
                    """,
                    (account_id,),
                )
                row = cursor.fetchone()
            if not row:
                return None
            return {
                "id": row[0],
                "username": row[1],
                "status": row[2],
                "proxy_ip": row[3],
                "last_post_date": row[4] or "从未发布",
                "notes": row[5] or "",
            }
        except Exception:
            return None

    def _on_selection_changed(self):
        has_sel = self._selected_account_id() is not None
        try:
            self.btn_edit.setEnabled(has_sel)
            self.btn_delete.setEnabled(has_sel)
        except Exception:
            pass

    def _on_item_double_clicked(self, _item: QListWidgetItem):
        # 双击编辑
        self.edit_selected_account()

    def edit_selected_account(self):
        account_id = self._selected_account_id()
        if account_id is None:
            return

        acc = self._fetch_account_by_id(account_id)
        if not acc:
            QMessageBox.warning(self, "提示", "未找到账号记录，可能已被删除。")
            self.load_accounts()
            return

        dialog = AddAccountDialog(self, initial_data=acc)
        if dialog.exec_() != QDialog.Accepted:
            return

        data = dialog.get_data()
        if not data["username"]:
            QMessageBox.warning(self, "输入错误", "账号名不能为空")
            return

        try:
            with sqlite3.connect(_db_path()) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE accounts
                    SET username = ?, status = ?, proxy_ip = ?, notes = ?
                    WHERE id = ?
                    """,
                    (data["username"], data["status"], data["proxy_ip"], data["notes"], account_id),
                )
                conn.commit()
            logger.info(f"[CRM] 编辑账号: id={account_id} @{data['username']}")
            self.load_accounts()
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "重复账号", "该账号名已存在")
        except Exception as e:
            logger.error(f"编辑账号失败: {e}")
            QMessageBox.critical(self, "编辑失败", str(e))

    def delete_selected_account(self):
        account_id = self._selected_account_id()
        if account_id is None:
            return

        acc = self._fetch_account_by_id(account_id) or {}
        uname = acc.get("username") or ""
        ok = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除账号 @{uname} 吗？\n\n此操作不可撤销。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ok != QMessageBox.Yes:
            return

        try:
            with sqlite3.connect(_db_path()) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
                conn.commit()
            logger.info(f"[CRM] 删除账号: id={account_id} @{uname}")
            self.load_accounts()
        except Exception as e:
            logger.error(f"删除账号失败: {e}")
            QMessageBox.critical(self, "删除失败", str(e))
