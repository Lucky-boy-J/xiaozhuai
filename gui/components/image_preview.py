from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap


class ImagePreviewBar(QWidget):
    """输入栏上方的图片预览条，支持多张图，点 × 删除"""
    image_removed = Signal(int)   # 移除第 index 张图

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("image_preview_bar")
        self.hide()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        self._scroll = QScrollArea()
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setFixedHeight(88)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        self._scroll.setWidgetResizable(True)

        self._container = QWidget()
        self._container_layout = QHBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(8)
        self._container_layout.addStretch()
        self._scroll.setWidget(self._container)

        layout.addWidget(self._scroll)
        self._thumbs = []

    def add_image(self, pixmap: QPixmap) -> int:
        """添加一张图，返回 index"""
        idx = len(self._thumbs)
        thumb = _ImageThumb(pixmap, idx, self)
        thumb.remove_clicked.connect(self._on_remove)
        self._container_layout.insertWidget(
            self._container_layout.count() - 1, thumb
        )
        self._thumbs.append(thumb)
        self.show()
        return idx

    def _on_remove(self, idx: int):
        if 0 <= idx < len(self._thumbs):
            thumb = self._thumbs[idx]
            self._container_layout.removeWidget(thumb)
            thumb.deleteLater()
            self._thumbs.pop(idx)
            # 重新编号
            for i, t in enumerate(self._thumbs):
                t.index = i
            self.image_removed.emit(idx)
        if not self._thumbs:
            self.hide()

    def clear(self):
        for thumb in self._thumbs:
            self._container_layout.removeWidget(thumb)
            thumb.deleteLater()
        self._thumbs.clear()
        self.hide()

    @property
    def count(self) -> int:
        return len(self._thumbs)


class _ImageThumb(QWidget):
    remove_clicked = Signal(int)

    def __init__(self, pixmap: QPixmap, index: int, parent=None):
        super().__init__(parent)
        self.index = index
        self.setFixedSize(76, 76)

        # 缩略图
        self._img_label = QLabel(self)
        self._img_label.setFixedSize(76, 76)
        self._img_label.setScaledContents(False)
        self._img_label.setAlignment(Qt.AlignCenter)
        scaled = pixmap.scaled(76, 76, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._img_label.setPixmap(scaled)
        self._img_label.setStyleSheet(
            "border-radius: 8px; background: #e8e8e8;"
        )

        # 删除按钮
        self._del_btn = QPushButton("×", self)
        self._del_btn.setFixedSize(18, 18)
        self._del_btn.move(58, 0)
        self._del_btn.setStyleSheet("""
            QPushButton {
                background: rgba(0,0,0,0.55); color: white;
                border-radius: 9px; border: none;
                font-size: 12px; font-weight: bold;
            }
            QPushButton:hover { background: rgba(200,0,0,0.8); }
        """)
        self._del_btn.clicked.connect(lambda: self.remove_clicked.emit(self.index))
        self._del_btn.setFocusPolicy(Qt.NoFocus)

    def mouseDoubleClickEvent(self, event):
        """双击大图预览"""
        _FullPreview(self._img_label.pixmap().scaled(
            900, 700, Qt.KeepAspectRatio, Qt.SmoothTransformation
        ), self.window()).exec()


class _FullPreview:
    """简易全屏预览对话框"""
    def __init__(self, pixmap: QPixmap, parent=None):
        from PySide6.QtWidgets import QDialog
        self._dlg = QDialog(parent)
        self._dlg.setWindowTitle("图片预览")
        self._dlg.setModal(True)
        layout = QVBoxLayout(self._dlg)
        layout.setContentsMargins(8, 8, 8, 8)
        lbl = QLabel()
        lbl.setPixmap(pixmap)
        lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl)
        # 点任意处关闭
        self._dlg.mousePressEvent = lambda e: self._dlg.accept()

    def exec(self):
        self._dlg.exec()
