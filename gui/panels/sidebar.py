import json
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget,
    QListWidgetItem, QPushButton, QLabel, QMenu
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QAction


HISTORY_FILE = "chat_history.json"


class Sidebar(QWidget):
    session_selected = Signal(str)
    new_session_requested = Signal()
    session_deleted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(210)
        self.setObjectName("sidebar")
        self._sessions = {}
        self._setup_ui()
        self._load_history()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(8)

        title = QLabel("小猪 AI")
        title.setObjectName("sidebar_title")
        layout.addWidget(title)

        self.new_btn = QPushButton("+ 新对话")
        self.new_btn.setObjectName("new_session_btn")
        self.new_btn.clicked.connect(self.new_session_requested.emit)
        layout.addWidget(self.new_btn)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("session_list")
        self.list_widget.itemClicked.connect(
            lambda item: self.session_selected.emit(item.data(Qt.UserRole))
        )
        # 右键菜单
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.list_widget)

    def _show_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item:
            return
        session_id = item.data(Qt.UserRole)
        menu = QMenu(self)
        menu.setObjectName("context_menu")
        delete_action = QAction("删除对话", self)
        delete_action.triggered.connect(lambda: self._delete_session(session_id))
        menu.addAction(delete_action)
        menu.exec(self.list_widget.mapToGlobal(pos))

    def _delete_session(self, session_id: str):
        # 从列表中移除
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item and item.data(Qt.UserRole) == session_id:
                self.list_widget.takeItem(i)
                break
        # 从数据中移除
        self._sessions.pop(session_id, None)
        self._save_history()
        self.session_deleted.emit(session_id)

    def add_session(self, session_id: str, title: str):
        """仅新增，不更新已有 session"""
        if session_id in self._sessions:
            return
        self._sessions[session_id] = {"title": title, "messages": []}
        item = QListWidgetItem(
            title[:22] + ("..." if len(title) > 22 else "")
        )
        item.setData(Qt.UserRole, session_id)
        self.list_widget.insertItem(0, item)
        self.list_widget.setCurrentItem(item)
        self._save_history()

    def update_session_title(self, session_id: str, title: str):
        """首次有消息时更新标题"""
        if session_id not in self._sessions:
            return
        self._sessions[session_id]["title"] = title
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item and item.data(Qt.UserRole) == session_id:
                item.setText(title[:22] + ("..." if len(title) > 22 else ""))
                break
        self._save_history()

    def update_session_messages(self, session_id: str, messages: list):
        if session_id in self._sessions:
            self._sessions[session_id]["messages"] = messages
            self._save_history()

    def get_messages(self, session_id: str) -> list:
        return self._sessions.get(session_id, {}).get("messages", [])

    def session_exists(self, session_id: str) -> bool:
        return session_id in self._sessions

    def _load_history(self):
        if not os.path.exists(HISTORY_FILE):
            return
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                self._sessions = {}
                return
            self._sessions = data
            for sid, info in reversed(list(data.items())):
                title = info.get("title", "未命名对话")
                item = QListWidgetItem(title[:22])
                item.setData(Qt.UserRole, sid)
                self.list_widget.addItem(item)
        except Exception:
            self._sessions = {}

    def _save_history(self):
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self._sessions, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
