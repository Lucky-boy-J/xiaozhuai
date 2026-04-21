from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QSizePolicy, QFrame, QTextBrowser
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QImage, QFont, QFontMetrics
import base64

# 文件顶部新增导入
try:
    from shiboken6 import isValid
except ImportError:
    def isValid(obj): return True   # 兜底，避免 import 失败导致崩溃


def _md_to_html(text: str) -> str:
    try:
        import mistune
        try:
            md = mistune.create_markdown(
                plugins=['strikethrough', 'table', 'url']
            )
        except Exception:
            md = mistune.create_markdown()
        return md(text)
    except ImportError:
        html = (text.replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                    .replace("\n", "<br>"))
        return html


def _calc_bubble_max_w(parent_widget: QWidget) -> int:
    """
    计算气泡最大像素宽度：
    - 基准：27 个汉字宽度 + 左右内边距 28px
    - 上限：父容器可用宽度 × 0.78
    - 下限：280px
    """
    font = QFont("Microsoft YaHei", 14)
    fm = QFontMetrics(font)
    char_w = fm.horizontalAdvance("中")
    content_w = char_w * 27 + 28

    # 向上找到有效宽度的祖先
    w = parent_widget
    parent_w = 0
    while w is not None:
        if w.width() > 100:
            parent_w = w.width()
            break
        w = w.parent()

    if parent_w <= 0:
        parent_w = 800  # 兜底

    return min(content_w, max(280, int(parent_w * 0.78)))


class MessageBubble(QWidget):
    def __init__(self, text: str, role: str = "user",
                 image_b64: str = None, parent=None):
        super().__init__(parent)
        self.role = role
        self._raw_text = text
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._setup_ui(image_b64)
        if text:
            self._set_content(text)

    def _setup_ui(self, image_b64: str = None):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(12, 3, 12, 3)
        outer.setSpacing(0)

        self._frame = QFrame()
        self._frame.setObjectName(
            "bubble_user" if self.role == "user" else "bubble_assistant"
        )
        # frame 本身不限制宽度，由内部 label 的固定宽度撑开
        self._frame.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

        inner = QVBoxLayout(self._frame)
        inner.setContentsMargins(14, 10, 14, 10)
        inner.setSpacing(6)

        # 图片
        if image_b64:
            img_label = QLabel()
            img_label.setFixedSize(240, 180)
            img_label.setScaledContents(False)
            img_label.setAlignment(Qt.AlignCenter)
            try:
                data = base64.b64decode(image_b64)
                qimg = QImage.fromData(data)
                pix = QPixmap.fromImage(qimg).scaled(
                    240, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                img_label.setPixmap(pix)
            except Exception:
                img_label.setText("[图片]")
            inner.addWidget(img_label)

        # 文字
        if self.role == "user":
            self._label = QLabel()
            self._label.setWordWrap(True)
            self._label.setTextFormat(Qt.RichText)
            self._label.setTextInteractionFlags(
                Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse
            )
            self._label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
            self._label.setObjectName("bubble_user_text")
            inner.addWidget(self._label)
        else:
            self._label = QTextBrowser()
            self._label.setObjectName("bubble_assistant_text")
            self._label.setOpenExternalLinks(True)
            self._label.setReadOnly(True)
            self._label.setFrameShape(QTextBrowser.NoFrame)
            self._label.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self._label.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self._label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
            self._label.document().setDocumentMargin(0)
            self._label.document().contentsChanged.connect(self._adjust_text_height)
            inner.addWidget(self._label)

        if self.role == "user":
            outer.addStretch(1)
            outer.addWidget(self._frame, 0)
        else:
            outer.addWidget(self._frame, 0)
            outer.addStretch(1)

    # ── 宽度控制 ──────────────────────────────────────────

    def _apply_max_width(self):
        max_w = _calc_bubble_max_w(self)
        label_w = max_w - 28   # 减去左右内边距 14+14

        if self.role == "user":
            self._label.setMaximumWidth(label_w)
        else:
            # QTextBrowser 用 setFixedWidth 才能真正生效
            self._label.setFixedWidth(label_w)
            self._adjust_text_height()

        self._frame.setMaximumWidth(max_w)
        self._frame.updateGeometry()

    def showEvent(self, event):
        """首次显示时宽度已确定，此时计算最准确"""
        super().showEvent(event)
        # 延迟一帧确保父容器宽度已更新
        QTimer.singleShot(0, self._apply_max_width)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._apply_max_width)

    # ── 高度自适应 ────────────────────────────────────────

    def _adjust_text_height(self):
        if self.role != "user":
            if not isValid(self._label):
                return
            doc_h = int(self._label.document().size().height())
            self._label.setFixedHeight(max(doc_h + 4, 24))

    # ── 内容渲染 ──────────────────────────────────────────

    def _set_content(self, text: str):
        if self.role == "user":
            if not isValid(self._label):
                return
            safe = (text.replace("&", "&amp;")
                        .replace("<", "&lt;")
                        .replace(">", "&gt;")
                        .replace("\n", "<br>"))
            self._label.setText(safe)
        else:
            html = _md_to_html(text)
            self._label.setHtml(self._wrap_html(html))
            self._adjust_text_height()

    def _wrap_html(self, html: str) -> str:
        return (
            "<html><body style=\""
            "font-family:'Microsoft YaHei','PingFang SC',sans-serif;"
            "font-size:14px;"
            "color:#1a1a1a;"
            "line-height:1.7;"
            "margin:0;padding:0;"
            f"\">{html}</body></html>"
        )

    # ── 流式接口 ──────────────────────────────────────────

    def append_text(self, token: str):
        if not isValid(self._label):
            return
        self._raw_text += token
        self._set_content(self._raw_text)

    def finalize(self):
        if not isValid(self._label):
            return
        self._set_content(self._raw_text)

    @property
    def full_text(self) -> str:
        return self._raw_text
