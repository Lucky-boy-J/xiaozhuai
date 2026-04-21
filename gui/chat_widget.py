from PySide6.QtWidgets import QScrollArea, QWidget, QVBoxLayout
from PySide6.QtCore import Qt, QTimer
from gui.components.bubble import MessageBubble


class ChatWidget(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QScrollArea.NoFrame)
        self.setObjectName("chat_scroll")

        self._container = QWidget()
        self._container.setObjectName("chat_container")
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(0, 16, 0, 16)
        self._layout.setSpacing(4)
        self._layout.addStretch()
        self.setWidget(self._container)

        self._current_bubble: MessageBubble | None = None

    def add_user_message(self, text: str, image_b64: str = None):
        bubble = MessageBubble(text, role="user", image_b64=image_b64)
        self._layout.insertWidget(self._layout.count() - 1, bubble)
        self._scroll_to_bottom()

    def start_assistant_message(self) -> MessageBubble:
        bubble = MessageBubble("", role="assistant")
        self._layout.insertWidget(self._layout.count() - 1, bubble)
        self._current_bubble = bubble
        self._scroll_to_bottom()
        return bubble

    def append_token(self, token: str):
        if self._current_bubble:
            self._current_bubble.append_text(token)
        # 每 3 个 token 滚动一次，避免频繁触发影响性能
            if not hasattr(self, '_token_count'):
                self._token_count = 0
            self._token_count += 1
            if self._token_count % 3 == 0:
                self._scroll_to_bottom()

    def finalize_assistant_message(self):
        if self._current_bubble:
            self._current_bubble.finalize()
            self._current_bubble = None
            self._token_count = 0
            self._scroll_to_bottom()


    def clear(self):
        self._current_bubble = None          # ← 先断开引用
        self._token_count = 0
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _scroll_to_bottom(self):
        QTimer.singleShot(30, lambda: self.verticalScrollBar().setValue(
            self.verticalScrollBar().maximum()
        ))
