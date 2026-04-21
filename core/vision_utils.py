import base64
import numpy as np
from pathlib import Path
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtCore import QBuffer, QIODevice


def cv2_image_to_b64(img_bgr) -> str:
    """OpenCV BGR 图像 → base64 JPEG，智能缩放保持比例"""
    import cv2
    h, w = img_bgr.shape[:2]
    # 最长边不超过 1920，超过才缩放
    max_side = 1920
    if max(h, w) > max_side:
        scale = max_side / max(h, w)
        new_w, new_h = int(w * scale), int(h * scale)
        img_bgr = cv2.resize(img_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)
    # 根据图像内容动态选择质量：截图类用 90，照片类用 85
    quality = 90
    _, buf = cv2.imencode(".jpg", img_bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return base64.b64encode(buf.tobytes()).decode("utf-8")


def file_to_b64(path: str) -> tuple[str, QPixmap]:
    """
    读取图片文件 → (base64字符串, 预览QPixmap)
    支持 jpg/png/bmp/webp/tiff 等 OpenCV 支持的格式
    """
    import cv2
    img = cv2.imdecode(
        np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR
    )
    if img is None:
        raise ValueError(f"无法读取图片: {path}")
    b64 = cv2_image_to_b64(img)
    pixmap = _cv2_to_pixmap(img)
    return b64, pixmap


def qimage_to_b64(qimage: QImage) -> tuple[str, QPixmap]:
    """
    剪贴板 QImage → (base64字符串, 预览QPixmap)
    """
    import cv2
    # QImage → numpy
    qimage = qimage.convertToFormat(QImage.Format_RGB888)
    w, h = qimage.width(), qimage.height()
    ptr = qimage.bits()
    arr = np.array(ptr, dtype=np.uint8).reshape(h, w, 3)
    img_bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    b64 = cv2_image_to_b64(img_bgr)
    pixmap = _cv2_to_pixmap(img_bgr)
    return b64, pixmap


def _cv2_to_pixmap(img_bgr) -> QPixmap:
    """OpenCV BGR → QPixmap（用于预览，不压缩）"""
    import cv2
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    h, w, ch = img_rgb.shape
    qimg = QImage(img_rgb.data, w, h, w * ch, QImage.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())
