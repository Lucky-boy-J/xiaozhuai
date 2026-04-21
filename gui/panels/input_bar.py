from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout,
    QTextEdit, QPushButton, QSizePolicy,
    QLabel, QFrame, QFileDialog
)
from PySide6.QtCore import Qt, Signal, QSize, QPoint
from PySide6.QtGui import QKeyEvent, QDragEnterEvent, QDropEvent

from gui.components.waveform import WaveformWidget
from gui.components.image_preview import ImagePreviewBar
from gui.components.command_palette import CommandPalette, SHORTCUT_MAP


class InputBar(QWidget):
    send_requested = Signal(str, list, str, str)   # (text, images, search_query)

    record_started = Signal()
    record_stopped = Signal()
    screenshot_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._images_b64 = []
        self._recording = False
        self._active_template = ""
        self._command_mode = False
        self.setAcceptDrops(True)
        self._setup_ui()
        self._setup_palette()
        self._images_b64: list[str] = []
        self._attached_doc_text = ""   # 当前附加的文档全文
        self._attached_doc_name = ""   # 文件名，用于显示
        self._use_attached_doc = False


    # ── UI 构建 ──────────────────────────────────────────

    def _setup_ui(self):
        self.setObjectName("input_bar_widget")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 6, 16, 16)
        outer.setSpacing(0)

        self._frame = QFrame()
        self._frame.setObjectName("input_frame")
        frame_layout = QVBoxLayout(self._frame)
        frame_layout.setContentsMargins(12, 8, 12, 8)
        frame_layout.setSpacing(4)

        # 图片预览条
        self.preview_bar = ImagePreviewBar(self)
        self.preview_bar.image_removed.connect(self._on_image_removed)
        frame_layout.addWidget(self.preview_bar)

        self._doc_bar = QFrame()
        self._doc_bar.setObjectName("doc_attachment_bar")
        doc_layout = QHBoxLayout(self._doc_bar)
        doc_layout.setContentsMargins(8, 4, 8, 4)
        doc_layout.setSpacing(8)
 
        self._doc_label = QLabel("")
        self._doc_label.setObjectName("doc_attachment_label")
        self._doc_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
 
        self._doc_ref_btn = QPushButton("引用")
        self._doc_ref_btn.setObjectName("doc_attachment_btn")
        self._doc_ref_btn.setCheckable(True)
        self._doc_ref_btn.setChecked(True)
        self._doc_ref_btn.setFocusPolicy(Qt.NoFocus)
        self._doc_ref_btn.clicked.connect(self._on_doc_ref_toggle)
 
        self._doc_remove_btn = QPushButton("×")
        self._doc_remove_btn.setObjectName("doc_attachment_remove")
        self._doc_remove_btn.setFixedSize(22, 22)
        self._doc_remove_btn.setFocusPolicy(Qt.NoFocus)
        self._doc_remove_btn.clicked.connect(self.clear_doc)
 
        doc_layout.addWidget(self._doc_label, 1)
        doc_layout.addStretch()
        doc_layout.addWidget(self._doc_ref_btn)
        doc_layout.addWidget(self._doc_remove_btn)
        self._doc_bar.hide()
        frame_layout.addWidget(self._doc_bar)
 
        # 文本输入
        self.input_edit = _SmartTextEdit(self)
        self.input_edit.setObjectName("input_edit")
        self.input_edit.setPlaceholderText(
            "发消息（Enter发送 · Shift+Enter换行 · 输入/显示快捷指令）"
        )
        self.input_edit.setMinimumHeight(28)
        self.input_edit.setMaximumHeight(140)
        self.input_edit.setFrameShape(QTextEdit.NoFrame)
        self.input_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        # 所有按键事件由 InputBar 统一处理
        self.input_edit.key_pressed.connect(self._handle_key)
        self.input_edit.textChanged.connect(self._on_text_changed)
        self.input_edit.paste_image_requested.connect(self._paste_image)
        frame_layout.addWidget(self.input_edit)

        # 底部工具栏
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 2, 0, 0)
        toolbar.setSpacing(4)

        self.record_btn = QPushButton("🎤")
        self.record_btn.setObjectName("tool_btn")
        self.record_btn.setFixedSize(32, 32)
        self.record_btn.setToolTip("按住录音")
        self.record_btn.setFocusPolicy(Qt.NoFocus)
        self.record_btn.pressed.connect(self._on_record_start)
        self.record_btn.released.connect(self._on_record_stop)

        self.upload_btn = QPushButton("🖼")
        self.upload_btn.setObjectName("tool_btn")
        self.upload_btn.setFixedSize(32, 32)
        self.upload_btn.setToolTip("上传图片")
        self.upload_btn.setFocusPolicy(Qt.NoFocus)
        self.upload_btn.clicked.connect(self._open_file_dialog)

        self.waveform = WaveformWidget(self)
        self.waveform.setFixedSize(48, 28)
        self.waveform.hide()

        toolbar.addWidget(self.record_btn)
        toolbar.addWidget(self.upload_btn)
        toolbar.addWidget(self.waveform)
        toolbar.addStretch()

        self.doc_btn = QPushButton("📄")
        self.doc_btn.setObjectName("tool_btn")
        self.doc_btn.setFixedSize(32, 32)
        self.doc_btn.setToolTip("附加文档（PDF/Word/TXT/MD）")
        self.doc_btn.setFocusPolicy(Qt.NoFocus)
        self.doc_btn.clicked.connect(self._open_doc_dialog)
        toolbar.addWidget(self.doc_btn)


        self.screenshot_btn = QPushButton("📸")
        self.screenshot_btn.setObjectName("tool_btn")
        self.screenshot_btn.setFixedSize(32, 32)
        self.screenshot_btn.setToolTip("区域截图  Ctrl+Shift+S")
        self.screenshot_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.screenshot_btn.clicked.connect(self.screenshot_requested.emit)
        toolbar.addWidget(self.screenshot_btn)

        self._char_count = QLabel("0")
        self._char_count.setObjectName("char_count")
        toolbar.addWidget(self._char_count)

        self.send_btn = QPushButton("发送")
        self.send_btn.setObjectName("send_btn")
        self.send_btn.setFixedSize(72, 32)
        self.send_btn.setFocusPolicy(Qt.NoFocus)
        self.send_btn.clicked.connect(self._on_send)
        toolbar.addWidget(self.send_btn)

        frame_layout.addLayout(toolbar)
        outer.addWidget(self._frame)

    def _open_doc_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择文档", "",
            "支持的文档 (*.pdf *.docx *.txt *.md)"
        )
        if path:
            self._attach_doc(path)

    def _attach_doc(self, path: str):
        """解析文档全文并附加到本次对话"""
        import os
        from core.rag.file_parser import FileParser
        try:
            text = FileParser.parse(path)
            self._attached_doc_text = text
            self._attached_doc_name = os.path.basename(path)
            self._use_attached_doc = True
            self._doc_label.setText(f"📄 {self._attached_doc_name}")
            self._doc_ref_btn.setChecked(True)
            self._doc_ref_btn.setText("引用")
            self._doc_bar.show()
            self.input_edit.setPlaceholderText(
                "发消息（Enter发送 · Shift+Enter换行 · 输入/显示快捷指令）"
            )
        except Exception as e:
            print(f"文档读取失败: {e}")

    def _on_doc_ref_toggle(self):
        self._use_attached_doc = self._doc_ref_btn.isChecked()
        self._doc_ref_btn.setText("引用" if self._use_attached_doc else "不引用")
 
    def clear_doc(self):
        self._attached_doc_text = ""
        self._attached_doc_name = ""
        self._use_attached_doc = False
        self._doc_label.setText("")
        self._doc_ref_btn.setChecked(True)
        self._doc_ref_btn.setText("引用")
        self._doc_bar.hide()
        self.input_edit.setPlaceholderText(
            "发消息（Enter发送 · Shift+Enter换行 · 输入/显示快捷指令）"
        )

    
    def attach_screenshot(self, pixmap, b64: str):    
        self.preview_bar.add_image(pixmap)    
        self._images_b64.append(b64)    
        self.input_edit.setFocus()    
        self.input_edit.setPlaceholderText("📎 截图已附加，输入问题后发送…")
    # get_images_b64 / clear_images 保持原来逻辑
    def get_images_b64(self) -> list[str]:    
        return list(self._images_b64)
    def clear_images(self):    
        self._images_b64.clear()    
        self.input_edit.setPlaceholderText("输入消息…")

    def _setup_palette(self):
        from gui.components.command_palette import CommandPalette
        # parent 设为 None，后续在 _reposition_palette 里动态挂到主窗口
        self._palette = CommandPalette(None)
        self._palette.command_selected.connect(self._on_command_selected)
        self._palette.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self._palette.setAttribute(Qt.WA_ShowWithoutActivating)  # 显示时不抢焦点
        self._palette.hide()


    # ── 按键统一处理 ─────────────────────────────────────

    def _handle_key(self, event: QKeyEvent):
        """所有按键由此处统一分发，palette 可见时优先处理"""
        key = event.key()
        mods = event.modifiers()

        if self._palette.isVisible():
            if key == Qt.Key_Up:
                self._palette.move_up()
                return
            elif key == Qt.Key_Down:
                self._palette.move_down()
                return
            elif key in (Qt.Key_Return, Qt.Key_Enter):
                if not (mods & Qt.ShiftModifier):
                    self._palette.confirm()
                    return
            elif key == Qt.Key_Escape:
                self._palette.hide()
                self._exit_command_mode()
                return
            elif key == Qt.Key_Tab:
                self._palette.confirm()
                return

        # palette 不可见时的正常处理
        if key in (Qt.Key_Return, Qt.Key_Enter):
            if mods & Qt.ShiftModifier:
                self.input_edit.insertPlainText("\n")
            else:
                self._on_send()
        elif key == Qt.Key_Escape:
            if self._active_template:
                self._exit_command_mode()

    # ── 文本变化监听 ─────────────────────────────────────

    def _on_text_changed(self):
        text = self.input_edit.toPlainText()
        self._char_count.setText(str(len(text)))
        self._auto_resize()

        if self._active_template:
            # 已选中指令，不再触发 palette
            return

        if text.startswith("/"):
            after_slash = text[1:]

            # 检测快捷别名：/s 空格 → 直接触发
            parts = after_slash.split(" ", 1)
            shortcut = parts[0].lower()
            if len(parts) > 1 and shortcut in SHORTCUT_MAP:
                # /s 后有空格，直接激活对应指令
                remaining = parts[1]
                cmd = SHORTCUT_MAP[shortcut]
                self._palette.hide()
                self._activate_command(cmd["prompt"], remaining)
                return

            # 普通过滤模式
            self._command_mode = True
            has_results = self._palette.filter(after_slash)
            if has_results:
                self._reposition_palette()
                self._palette.show()
                self._palette.raise_()
            else:
                self._palette.hide()
        else:
            self._command_mode = False
            self._palette.hide()

    def _reposition_palette(self):
        """将 palette 定位到光标正上方，使用屏幕全局坐标"""
        cursor_rect = self.input_edit.cursorRect()

        # 光标左上角的全局屏幕坐标
        cursor_global = self.input_edit.mapToGlobal(cursor_rect.topLeft())

        palette_h = self._palette.sizeHint().height()
        palette_w = self._palette.width()

        # 显示在光标上方，留 8px 间距
        x = cursor_global.x()
        y = cursor_global.y() - palette_h - 8

        # 防止超出屏幕左边
        from PySide6.QtWidgets import QApplication
        screen = QApplication.screenAt(cursor_global)
        if screen:
            screen_rect = screen.availableGeometry()
            # 防止超出右边
            if x + palette_w > screen_rect.right():
                x = screen_rect.right() - palette_w - 4
            # 防止超出左边
            x = max(screen_rect.left(), x)
            # 上方空间不足时改为显示在光标下方
            if y < screen_rect.top():
                y = cursor_global.y() + cursor_rect.height() + 8

        self._palette.move(x, y)


    # ── 指令激活 ─────────────────────────────────────────

    def _on_command_selected(self, prompt_template: str):
        """从 palette 选中指令"""
        self._activate_command(prompt_template, "")

    def _activate_command(self, prompt_template: str, remaining_text: str):
        """激活一条指令，清空输入框等待用户输入内容"""
        self._active_template = prompt_template
        self._command_mode = False

        # 提取指令名用于显示
        cmd_name = next(
            (c["name"] for c in __import__(
                'gui.components.command_palette',
                fromlist=['COMMANDS']
            ).COMMANDS if c["prompt"] == prompt_template),
            "指令"
        )

        self.input_edit.blockSignals(True)
        self.input_edit.setPlainText(remaining_text)
        self.input_edit.blockSignals(False)

        # 光标移到末尾
        cursor = self.input_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.input_edit.setTextCursor(cursor)

        self.input_edit.setPlaceholderText(
            f"【{cmd_name}】输入内容后发送，留空直接执行 · Esc 取消"
        )
        self._char_count.setText(str(len(remaining_text)))

    def _exit_command_mode(self):
        """取消指令模式"""
        self._active_template = ""
        self._command_mode = False
        self.input_edit.blockSignals(True)
        self.input_edit.setPlainText("")
        self.input_edit.blockSignals(False)
        self.input_edit.setPlaceholderText(
            "发消息（Enter发送 · Shift+Enter换行 · 输入/显示快捷指令）"
        )
        self._char_count.setText("0")

    # ── 发送 ─────────────────────────────────────────────

    def _on_send(self):
        text = self.input_edit.toPlainText().strip()
        search_query = None

        if self._active_template:
            if self._active_template.startswith("__SEARCH__:"):
                # 联网搜索指令：query 就是用户输入的文本
                search_query = text if text else self._active_template[11:]
                final_text = f"请根据搜索结果回答：{search_query}"
            elif "{text}" in self._active_template:
                final_text = self._active_template.replace("{text}", text)
            else:
                final_text = self._active_template + (f"{text}" if text else "")

            self._active_template = ""
            self.input_edit.setPlaceholderText(
                "发消息（Enter发送 · Shift+Enter换行 · 输入/显示快捷指令）"
            )
        else:
            final_text = text

        if not final_text and not self._images_b64:
            return

        image_b64 = self._images_b64[0] if self._images_b64 else None
        doc_text = self._attached_doc_text if self._use_attached_doc else ""
        self.send_requested.emit(final_text, list(self._images_b64), search_query or "", doc_text)
        self.input_edit.setPlaceholderText("发消息（Enter发送 · Shift+Enter换行 · 输入/显示快捷指令）")

        # 把 search_query 单独存起来供 main_window 读取
        self._pending_search_query = search_query

        self.input_edit.blockSignals(True)
        self.input_edit.clear()
        self.input_edit.blockSignals(False)
        self._images_b64.clear()
        self.preview_bar.clear()
        self._char_count.setText("0")
        self._palette.hide()


    # ── 图片处理 ─────────────────────────────────────────

    def _add_image_from_file(self, path: str):
        try:
            from core.vision_utils import file_to_b64
            b64, pixmap = file_to_b64(path)
            self._images_b64.append(b64)
            self.preview_bar.add_image(pixmap)
        except Exception as e:
            print(f"图片加载失败: {e}")

    def _paste_image(self):
        from PySide6.QtWidgets import QApplication
        from core.vision_utils import qimage_to_b64
        qimage = QApplication.clipboard().image()
        if not qimage.isNull():
            try:
                b64, pixmap = qimage_to_b64(qimage)
                self._images_b64.append(b64)
                self.preview_bar.add_image(pixmap)
            except Exception as e:
                print(f"粘贴图片失败: {e}")

    def _open_file_dialog(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择图片", "",
            "图片文件 (*.jpg *.jpeg *.png *.bmp *.webp *.tiff *.gif)"
        )
        for p in paths:
            self._add_image_from_file(p)

    def _on_image_removed(self, idx: int):
        if 0 <= idx < len(self._images_b64):
            self._images_b64.pop(idx)

    # ── 拖拽 ─────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls() or event.mimeData().hasImage():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        mime = event.mimeData()
        if mime.hasUrls():
            for url in mime.urls():
                path = url.toLocalFile()
                if path.lower().endswith(
                    ('.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff', '.gif')
                ):
                    self._add_image_from_file(path)
        elif mime.hasImage():
            from core.vision_utils import qimage_to_b64
            from PySide6.QtGui import QImage
            qimage = mime.imageData()
            if isinstance(qimage, QImage) and not qimage.isNull():
                try:
                    b64, pixmap = qimage_to_b64(qimage)
                    self._images_b64.append(b64)
                    self.preview_bar.add_image(pixmap)
                except Exception as e:
                    print(f"拖拽图片失败: {e}")
        event.acceptProposedAction()

    # ── 辅助 ─────────────────────────────────────────────

    def _auto_resize(self):
        doc_h = int(self.input_edit.document().size().height())
        self.input_edit.setFixedHeight(min(max(doc_h + 4, 28), 140))

    def _on_record_start(self):
        self._recording = True
        self.waveform.show()
        self.waveform.start()
        self.record_started.emit()

    def _on_record_stop(self):
        self._recording = False
        self.waveform.stop()
        self.waveform.hide()
        self.record_stopped.emit()

    def set_sending_state(self, sending: bool):
        self.send_btn.setText("停止 ■" if sending else "发送")
        self.send_btn.setObjectName("stop_btn" if sending else "send_btn")
        self.send_btn.style().unpolish(self.send_btn)
        self.send_btn.style().polish(self.send_btn)

    def fill_text(self, text: str):
        self.input_edit.setPlainText(text)
        cursor = self.input_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.input_edit.setTextCursor(cursor)


class _SmartTextEdit(QTextEdit):
    """
    输入框：所有按键事件通过 key_pressed 信号上报给 InputBar，
    自身不做任何逻辑判断，保证焦点始终在输入框。
    """
    key_pressed = Signal(object)          # QKeyEvent
    paste_image_requested = Signal()

    def keyPressEvent(self, event: QKeyEvent):
        # Ctrl+V 先检查是否是图片
        if (event.key() == Qt.Key_V
                and event.modifiers() & Qt.ControlModifier):
            from PySide6.QtWidgets import QApplication
            if not QApplication.clipboard().image().isNull():
                self.paste_image_requested.emit()
                return
            # 是文字，走默认粘贴
            super().keyPressEvent(event)
            return

        # Enter / 方向键 / Esc → 上报给 InputBar 处理
        if event.key() in (
            Qt.Key_Return, Qt.Key_Enter,
            Qt.Key_Up, Qt.Key_Down,
            Qt.Key_Escape, Qt.Key_Tab
        ):
            self.key_pressed.emit(event)
            return

        # 其他键正常处理，保证能打字
        super().keyPressEvent(event)

    def sizeHint(self) -> QSize:
        return QSize(400, 44)