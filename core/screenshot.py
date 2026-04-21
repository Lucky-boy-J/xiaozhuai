import base64
import logging
from datetime import datetime
from pathlib import Path
from typing import Tuple

import cv2
import numpy as np

logger = logging.getLogger("screenshot")


class ScreenshotEngine:

    def __init__(self, save_dir: str = "screenshots"):
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(exist_ok=True)

    def capture_region(self, left: int, top: int, width: int, height: int) -> Tuple[np.ndarray, str]:
        """截取指定区域，返回 (BGR ndarray, 保存路径)"""
        import mss
        with mss.mss() as sct:
            monitor = {"left": left, "top": top, "width": width, "height": height}
            shot = sct.grab(monitor)
            img_bgra = np.array(shot)
        img_bgr = img_bgra[:, :, :3]
        path = self._save(img_bgr)
        logger.info(f"截图已保存：{path}")
        return img_bgr, path

    def capture_fullscreen(self) -> Tuple[np.ndarray, str]:
        """截取主屏全屏"""
        import mss
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            shot = sct.grab(monitor)
            img_bgra = np.array(shot)
        img_bgr = img_bgra[:, :, :3]
        path = self._save(img_bgr)
        return img_bgr, path

    def _save(self, img_bgr: np.ndarray) -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
        path = self.save_dir / f"screenshot_{ts}.png"
        cv2.imwrite(str(path), img_bgr)
        return str(path)

    @staticmethod
    def resize_for_llm(img_bgr: np.ndarray, max_side: int = 1920) -> np.ndarray:
        """等比缩放，最长边不超过 max_side"""
        h, w = img_bgr.shape[:2]
        scale = min(max_side / max(h, w), 1.0)
        if scale < 1.0:
            new_w, new_h = int(w * scale), int(h * scale)
            img_bgr = cv2.resize(img_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)
        return img_bgr

    @staticmethod
    def to_b64(img_bgr: np.ndarray, quality: int = 85) -> str:
        """BGR ndarray → base64 JPEG 字符串（供 LLM vision 接口使用）"""
        img_bgr = ScreenshotEngine.resize_for_llm(img_bgr)
        ok, buf = cv2.imencode(".jpg", img_bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if not ok:
            raise RuntimeError("图像编码失败")
        return base64.b64encode(buf.tobytes()).decode("utf-8")

    @staticmethod
    def bgr_to_qpixmap(img_bgr: np.ndarray):
        """BGR ndarray → QPixmap，供 GUI 预览"""
        from PySide6.QtGui import QImage, QPixmap
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        h, w, ch = img_rgb.shape
        qimg = QImage(img_rgb.data.tobytes(), w, h, w * ch, QImage.Format_RGB888)
        return QPixmap.fromImage(qimg)
