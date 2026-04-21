from PySide6.QtCore import Qt, QPoint, QRect,  QTimer,Signal
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QGuiApplication
from PySide6.QtWidgets import QWidget, QApplication


class ScreenSelector(QWidget):
    """
    全屏遮罩选区工具。
    selected(QRect)  — 用户完成选区
    cancelled()      — 用户按 Esc 取消
    """
    selected = Signal(QRect)
    cancelled = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._origin = QPoint()
        self._rect = QRect()
        self._drawing = False

    # ── 显示 ──────────────────────────────────────────────────────────

    def activate(self):
        """覆盖所有屏幕，进入选区模式"""
        # 合并所有屏幕的虚拟桌面矩形
        virtual = QGuiApplication.primaryScreen().virtualGeometry()
        self.setGeometry(virtual)
        self.showFullScreen()
        self.raise_()
        self.activateWindow()

    # ── 绘制 ──────────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # 半透明黑色遮罩
        painter.fillRect(self.rect(), QBrush(QColor(0, 0, 0, 140)))

        if self._rect.isValid():
            # 挖空选区
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(self._rect, Qt.GlobalColor.transparent)

            # 选区边框
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_SourceOver
            )
            pen = QPen(QColor("#4a90e2"), 2)
            painter.setPen(pen)
            painter.drawRect(self._rect)

            # 左上角尺寸提示
            painter.setPen(QColor("#ffffff"))
            label = f" {self._rect.width()} × {self._rect.height()} "
            x = self._rect.left() + 4
            y = self._rect.top() - 6
            if y < 16:
                y = self._rect.top() + 20
            painter.drawText(x, y, label)

    # ── 鼠标事件 ──────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._origin = event.position().toPoint()
            self._rect = QRect()
            self._drawing = True

    def mouseMoveEvent(self, event):
        if self._drawing:
            self._rect = QRect(self._origin, event.position().toPoint()).normalized()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._drawing:
            self._drawing = False
            if self._rect.width() > 4 and self._rect.height() > 4:
                # Widget 局部坐标 → 全局屏幕坐标
                global_rect = QRect(
                    self.mapToGlobal(self._rect.topLeft()),
                    self.mapToGlobal(self._rect.bottomRight())
                )
                # 高 DPI 缩放修正
                screen = QGuiApplication.screenAt(
                    self.mapToGlobal(self._rect.center())
                )
                if screen is None:
                    screen = QGuiApplication.primaryScreen()
                dpr = screen.devicePixelRatio()
                if dpr != 1.0:
                    global_rect = QRect(
                        int(global_rect.left() * dpr),
                        int(global_rect.top() * dpr),
                        int(global_rect.width() * dpr),
                        int(global_rect.height() * dpr),
                    )
                # 先隐藏遮罩（视觉上消失），再发信号，最后延迟销毁
                self.hide()
                QApplication.processEvents()          # 确保遮罩画面已清除
                self.selected.emit(global_rect)       # 发信号（此时对象还活着）
                QTimer.singleShot(0, self.close)      # 下一帧再销毁
            else:
                self.cancelled.emit()
                QTimer.singleShot(0, self.close)



    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._drawing = False
            self.cancelled.emit()
            QTimer.singleShot(0, self.close) 
