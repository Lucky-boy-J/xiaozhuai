from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt
from gui.chat_widget import ChatWidget


class ChatPanel(QWidget):
    def __init__(self, signals, parent=None):
        super().__init__(parent)
        self.signals = signals
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 顶部栏
        self.topbar = self._build_topbar()
        layout.addWidget(self.topbar)

        # 聊天区
        self.chat_widget = ChatWidget(self)
        layout.addWidget(self.chat_widget)

    def _build_topbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(52)
        bar.setObjectName("topbar")
        h = QHBoxLayout(bar)
        h.setContentsMargins(20, 0, 20, 0)

        self.title_label = QLabel("小猪 AI")
        self.title_label.setObjectName("topbar_title")

        self.think_btn = QPushButton("✦ 深度思考")
        self.think_btn.setCheckable(True)
        self.think_btn.setObjectName("think_btn")
        self.think_btn.setFixedWidth(108)

        # 在 think_btn 旁边加
        self.mute_btn = QPushButton("🔊")
        self.mute_btn.setCheckable(True)
        self.mute_btn.setObjectName("tool_btn_top")
        self.mute_btn.setFixedSize(36, 36)
        self.mute_btn.setToolTip("静音 / 取消静音")
        self.mute_btn.setFocusPolicy(Qt.NoFocus)
        self.mute_btn.toggled.connect(self._on_mute_toggle)

        h.addWidget(self.mute_btn)


        self.status_label = QLabel("加载中...")
        self.status_label.setObjectName("status_label")
        self.status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        h.addWidget(self.title_label)
        h.addStretch()
        h.addWidget(self.think_btn)
        h.addSpacing(16)
        h.addWidget(self.status_label)
        return bar

    def _on_mute_toggle(self, muted: bool):
        self.mute_btn.setText("🔇" if muted else "🔊")
        if self._mute_callback:
            self._mute_callback(muted)

    def set_mute_callback(self, callback):
        self._mute_callback = callback


    def _connect_signals(self):
        self.signals.loading_done.connect(
            lambda: self.status_label.setText("就绪")
        )
        self.signals.loading_progress.connect(
            lambda msg: self.status_label.setText(msg)
        )
        self.signals.loading_error.connect(
            lambda msg: self.status_label.setText(f"错误: {msg}")
        )
        self.signals.llm_done.connect(
            lambda: self.status_label.setText("就绪")
        )

    def set_thinking_callback(self, callback):
        """由 main_window 注入思考模式切换回调"""
        self.think_btn.toggled.connect(lambda checked: (
            self.think_btn.setText(f"深度思考  {'ON' if checked else 'OFF'}"),
            callback(checked)
        ))

    def set_status(self, text: str):
        self.status_label.setText(text)
