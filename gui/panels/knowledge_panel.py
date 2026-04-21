from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QListWidget, QListWidgetItem, QLabel,
    QFileDialog, QProgressBar, QSizePolicy
)

SUPPORTED_EXTS = {".pdf", ".docx", ".txt", ".md"}


class KnowledgePanel(QWidget):
    """
    知识库管理面板，支持：
    - 点击"添加文件"按钮
    - 拖拽文件到面板
    - 删除已入库文件
    """
    file_added = Signal(str)    # 发出文件绝对路径
    file_deleted = Signal(str)  # 发出文件名（source）

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)          # 开启拖拽
        self._setup_ui()
        self._apply_style()

    # ── UI ───────────────────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # 标题行
        title_row = QHBoxLayout()
        title = QLabel("📚 知识库")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.count_label = QLabel("0 个文件")
        self.count_label.setStyleSheet("color: #888; font-size: 12px;")
        title_row.addWidget(title)
        title_row.addStretch()
        title_row.addWidget(self.count_label)
        layout.addLayout(title_row)

        # 拖拽提示区（文件列表为空时显示）
        self.drop_hint = QLabel("将文件拖拽到此处\n或点击下方按钮添加\n\n支持 PDF / Word / TXT / MD")
        self.drop_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_hint.setStyleSheet("""
            color: #aaa;
            font-size: 12px;
            border: 2px dashed #ddd;
            border-radius: 8px;
            padding: 20px;
        """)
        self.drop_hint.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        layout.addWidget(self.drop_hint)

        # 文件列表（有文件时显示，默认隐藏）
        self.file_list = QListWidget()
        self.file_list.setVisible(False)
        layout.addWidget(self.file_list)

        # 进度条
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(4)
        self.progress.setRange(0, 0)
        layout.addWidget(self.progress)

        # 状态提示
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #888; font-size: 11px;")
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)

        # 按钮行
        btn_row = QHBoxLayout()
        self.add_btn = QPushButton("+ 添加文件")
        self.add_btn.setFixedHeight(32)
        self.add_btn.clicked.connect(self._on_add_clicked)

        self.del_btn = QPushButton("删除选中")
        self.del_btn.setFixedHeight(32)
        self.del_btn.clicked.connect(self._on_delete_clicked)

        btn_row.addWidget(self.add_btn)
        btn_row.addWidget(self.del_btn)
        layout.addLayout(btn_row)

    def _apply_style(self):
        self.setStyleSheet("""
            QListWidget {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 6px 8px;
            }
            QListWidget::item:selected {
                background: #e8f0fe;
                color: #1a1a1a;
            }
            QPushButton {
                border-radius: 6px;
                background: #f0f0f0;
                font-size: 12px;
                padding: 0 12px;
            }
            QPushButton:hover { background: #e0e0e0; }
            QPushButton:disabled { color: #bbb; }
        """)

    # ── 拖拽事件 ─────────────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            # 检查是否有支持的文件类型
            urls = event.mimeData().urls()
            if any(
                Path(u.toLocalFile()).suffix.lower() in SUPPORTED_EXTS
                for u in urls
            ):
                event.acceptProposedAction()
                self.drop_hint.setStyleSheet("""
                    color: #4a90e2;
                    font-size: 12px;
                    border: 2px dashed #4a90e2;
                    border-radius: 8px;
                    padding: 20px;
                    background: #f0f5ff;
                """)
                return
        event.ignore()

    def dragLeaveEvent(self, event):
        self._reset_drop_hint_style()

    def dropEvent(self, event: QDropEvent):
        self._reset_drop_hint_style()
        urls = event.mimeData().urls()
        for url in urls:
            path = url.toLocalFile()
            if Path(path).suffix.lower() in SUPPORTED_EXTS:
                self.file_added.emit(path)
        event.acceptProposedAction()

    def _reset_drop_hint_style(self):
        self.drop_hint.setStyleSheet("""
            color: #aaa;
            font-size: 12px;
            border: 2px dashed #ddd;
            border-radius: 8px;
            padding: 20px;
        """)

    # ── 按钮事件 ─────────────────────────────────────────────────────

    def _on_add_clicked(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择文件", "",
            "支持的文件 (*.pdf *.docx *.txt *.md)"
        )
        for path in paths:
            self.file_added.emit(path)

    def _on_delete_clicked(self):
        item = self.file_list.currentItem()
        if item:
            self.file_deleted.emit(item.text())

    # ── 外部调用 ─────────────────────────────────────────────────────

    def refresh_files(self, file_list: list[str]):
        """刷新文件列表显示"""
        self.file_list.clear()
        for name in file_list:
            self.file_list.addItem(QListWidgetItem(name))

        has_files = len(file_list) > 0
        self.file_list.setVisible(has_files)
        self.drop_hint.setVisible(not has_files)
        self.count_label.setText(f"{len(file_list)} 个文件")

    def set_loading(self, loading: bool, filename: str = ""):
        """入库进度状态"""
        self.progress.setVisible(loading)
        self.add_btn.setEnabled(not loading)
        if loading and filename:
            self.status_label.setText(f"正在处理：{filename}…")
            self.status_label.setVisible(True)
        else:
            self.status_label.setVisible(False)
