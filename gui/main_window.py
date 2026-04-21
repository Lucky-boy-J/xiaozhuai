import uuid
from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QSplitter, QVBoxLayout, QApplication
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence

from gui.panels.bridge import Signals, LoaderThread
from gui.panels.chat_panel import ChatPanel
from gui.panels.input_bar import InputBar
from gui.panels.sidebar import Sidebar
from core.controller import Controller
from gui.panels.knowledge_panel import KnowledgePanel


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("小猪 AI")
        self.resize(1060, 720)
        self.setMinimumSize(760, 520)

        self.signals = Signals(self)
        self.controller = Controller()
        self._current_session_id = str(uuid.uuid4())
        self._is_generating = False
        self._session_has_message = False   # 本轮是否已有消息

        self._setup_ui()
        self._connect_signals()
        self._apply_style()
        self._start_loading()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── 左侧：会话列表 + 知识库面板（垂直分割）──
        self.sidebar = Sidebar(self)
        self.knowledge_panel = KnowledgePanel(self)  # ← 新增

        left_splitter = QSplitter(Qt.Vertical)       # ← 新增
        left_splitter.addWidget(self.sidebar)         # ← 新增
        left_splitter.addWidget(self.knowledge_panel) # ← 新增
        left_splitter.setSizes([400, 300])            # ← 新增，可按需调整比例
        left_splitter.setFixedWidth(210)              # ← 保持与原 sidebar 宽度一致
        left_splitter.handle(1).setFocusPolicy(Qt.NoFocus)  # ← 新增

        # ── 右侧：聊天区 + 输入框 ──
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        self.chat_panel = ChatPanel(self.signals, self)
        self.input_bar = InputBar(self)
        right_layout.addWidget(self.chat_panel)
        right_layout.addWidget(self.input_bar)

        # ── 主水平分割器 ──
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_splitter)  # ← 原来是 self.sidebar，现在换成 left_splitter
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([210, 850])
        splitter.handle(1).setFocusPolicy(Qt.NoFocus)
        main_layout.addWidget(splitter)


    def _connect_signals(self):
        self.signals.loading_done.connect(self._on_loading_done)
        self.signals.loading_error.connect(
            lambda msg: self.chat_panel.chat_widget.add_user_message(f"⚠️ 加载失败：{msg}")
        )
        self.signals.token_received.connect(self.chat_panel.chat_widget.append_token)
        self.signals.llm_done.connect(self._on_llm_done)
        self.signals.asr_result.connect(self.input_bar.fill_text)
        self.signals.error.connect(
            lambda msg: self.chat_panel.set_status(f"错误: {msg[:30]}")
        )

        self.chat_panel.set_mute_callback(
            lambda muted: self.controller.tts.mute()
            if muted else self.controller.tts.unmute()
        )

        self.input_bar.screenshot_requested.connect(self._start_screenshot)

        self.controller.on_search_start = lambda q: self.signals.loading_progress.emit(f"🔎 正在搜索「{q[:15]}」...")
        self.controller.on_search_done = lambda n: self.signals.loading_progress.emit(f"✅ 找到 {n} 条结果，正在分析...")



        self.input_bar.send_requested.connect(self._on_send)
        self.input_bar.record_started.connect(self._on_record_start)
        self.input_bar.record_stopped.connect(self._on_record_stop)

        self.sidebar.new_session_requested.connect(self._on_new_session)
        self.sidebar.session_selected.connect(self._on_session_selected)
        self.sidebar.session_deleted.connect(self._on_session_deleted)

        self.chat_panel.set_thinking_callback(self._on_thinking_toggle)

        # _connect_signals 末尾，确保是这两行（替换之前写的版本）：
        self.knowledge_panel.file_added.connect(self._on_knowledge_file_added)
        self.knowledge_panel.file_deleted.connect(self._on_knowledge_file_deleted)
        # RAG 后台线程 → 主线程 UI 更新（通过 Qt 信号，线程安全）
        self.signals.rag_files_updated.connect(self.knowledge_panel.refresh_files)
        self.signals.rag_loading.connect(self.knowledge_panel.set_loading)

        self.controller.on_token = lambda t: self.signals.token_received.emit(t)
        self.controller.on_llm_done = lambda: self.signals.llm_done.emit()
        self.controller.on_asr_result = lambda t: self.signals.asr_result.emit(t)
        self.controller.on_error = lambda m: self.signals.error.emit(m)
        self.controller.on_rag_loading = lambda b, m: self.signals.rag_loading.emit(b, m)
        self.controller.on_rag_files_updated = lambda f: self.signals.rag_files_updated.emit(f)
        self.controller.on_loading_progress = lambda m: self.signals.loading_progress.emit(m)

        from PySide6.QtGui import QShortcut, QKeySequence
        QShortcut(QKeySequence("Ctrl+Shift+S"), self).activated.connect(self._start_screenshot)

    def _on_knowledge_file_added(self, path: str):
        self.controller.add_knowledge_file_async(path)

    def _on_knowledge_file_deleted(self, filename: str):
        self.controller.delete_knowledge_file_async(filename)


    # ── 截图方法 ──────────────────────────────────────────────────────────

    def _start_screenshot(self):
        """隐藏主窗口 → 显示选区 → 截图 → 恢复"""
        from gui.components.screen_selector import ScreenSelector

        self.hide()                         # 先隐藏主窗口，避免截到自己
        QApplication.processEvents()
        
        def _show_selector():
            self._selector = ScreenSelector()
            self._selector.selected.connect(self._on_region_selected)
            self._selector.cancelled.connect(self._on_screenshot_cancelled)
            self._selector.activate()
        QTimer.singleShot(300, _show_selector)   # ← 等 300ms 让窗口真正消失

    def _on_region_selected(self, rect):
        """先截图，再恢复主窗口"""
        from core.screenshot import ScreenshotEngine
        engine = ScreenshotEngine()
        img_bgr, path = engine.capture_region(
            rect.left(), rect.top(), rect.width(), rect.height()
        )
        b64 = engine.to_b64(img_bgr)
        pixmap = engine.bgr_to_qpixmap(img_bgr)
        self.input_bar.attach_screenshot(pixmap, b64)
        self.show()                          # ← 截完图再恢复窗口
        QTimer.singleShot(100, self.input_bar.input_edit.setFocus)


    def _on_screenshot_cancelled(self):
        self.show()



    def _on_loading_done(self):
        self.input_bar.setEnabled(True)
        # 加载完成后焦点直接给输入框，防止按钮抢焦点导致空格误触
        QTimer.singleShot(100, self.input_bar.input_edit.setFocus)

    def _on_send(self, text: str, images: list, search_query: str, doc_text: str = ""):
        if self._is_generating:
            self.controller.tts.interrupt()
            self._is_generating = False
            self.input_bar.set_sending_state(False)
            self.chat_panel.chat_widget.finalize_assistant_message()
            return

        if not text and not images:
            return

        if not self._session_has_message:
            self._session_has_message = True
            title = text[:20] if text else "图片对话"
            self.sidebar.add_session(self._current_session_id, title)

        self._is_generating = True
        self.input_bar.set_sending_state(True)

        image_b64 = images[0] if images else None
        self.chat_panel.chat_widget.add_user_message(text, image_b64)
        self.chat_panel.chat_widget.start_assistant_message()

        self.controller.send_message(
            text,
            image_b64,
            search_query=search_query or None,
            doc_text=doc_text or None
        )



    def _on_llm_done(self):
        self._is_generating = False
        self.input_bar.set_sending_state(False)
        self.chat_panel.chat_widget.finalize_assistant_message()
        self.sidebar.update_session_messages(
            self._current_session_id,
            self.controller.chat_history
        )
        # 回复完成后焦点回到输入框
        self.input_bar.input_edit.setFocus()

    def _on_record_start(self):
        self.controller.start_recording()

    def _on_record_stop(self):
        self.controller.stop_recording()

    def _on_new_session(self):
        # 如果正在生成，先强制停止
        if self._is_generating:
            self.controller.tts.interrupt()
            self._is_generating = False
            self.input_bar.set_sending_state(False)

        self._current_session_id = str(uuid.uuid4())
        self._session_has_message = False
        self.controller.chat_history = []
        self.chat_panel.chat_widget.clear()
        QTimer.singleShot(50, self.input_bar.input_edit.setFocus)

    def _on_session_selected(self, session_id: str):
        # 如果正在生成，先强制停止
        if self._is_generating:
            self.controller.tts.interrupt()
            self._is_generating = False
            self.input_bar.set_sending_state(False)

        messages = self.sidebar.get_messages(session_id)
        self.controller.chat_history = messages
        self._current_session_id = session_id
        self._session_has_message = True
        self.chat_panel.chat_widget.clear()
        for msg in messages:
            if msg["role"] == "user":
                content = msg["content"]
                text = content if isinstance(content, str) \
                    else content[0].get("text", "")
                self.chat_panel.chat_widget.add_user_message(text)
            elif msg["role"] == "assistant":
                bubble = self.chat_panel.chat_widget.start_assistant_message()
                bubble.append_text(msg.get("content", ""))
                bubble.finalize()
        QTimer.singleShot(50, self.input_bar.input_edit.setFocus)


    def _on_session_deleted(self, session_id: str):
        # 如果删除的是当前 session，新建一个空白对话
        if session_id == self._current_session_id:
            self._on_new_session()

    def _on_thinking_toggle(self, enabled: bool):
        self.chat_panel.set_status("切换思考模式中...")
        self.controller.set_thinking(enabled)
        QTimer.singleShot(5000, lambda: self.chat_panel.set_status("就绪"))

    


    def _start_loading(self):
        self.input_bar.setEnabled(False)
        self.loader = LoaderThread(self.controller, self.signals)
        self.loader.start()

    def closeEvent(self, event):
        self.controller.shutdown()
        event.accept()

    def _apply_style(self):
        import os
        style_path = os.path.join(os.path.dirname(__file__), "..", "assets", "styles", "theme.qss")
        if os.path.exists(style_path):
            with open(style_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        else:
            print(f"Warning: stylesheet not found at {style_path}")
