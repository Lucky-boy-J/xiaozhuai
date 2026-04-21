import logging
from PySide6.QtCore import QThread, Signal, QObject

logger = logging.getLogger("bridge")


class Signals(QObject):
    """所有跨线程信号的统一定义"""
    def __init__(self, parent=None):   # ← 添加 parent 参数
        super().__init__(parent)
    # 加载阶段
    loading_progress = Signal(str)       # 加载状态文字
    loading_done = Signal()              # 全部引擎就绪
    loading_error = Signal(str)          # 加载失败

    # LLM 流式输出
    token_received = Signal(str)         # 每个 token
    llm_done = Signal()                  # 本轮生成结束
    llm_interrupted = Signal()           # 被打断

    # ASR
    asr_result = Signal(str)             # 识别结果文本

    # TTS
    tts_started = Signal()               # 开始播放
    tts_done = Signal()                  # 播放结束

    # 通用
    error = Signal(str)                  # 错误提示

    search_started = Signal(str)   # 搜索关键词
    search_done = Signal()

    # ↓ 新增：RAG 知识库专用    
    rag_files_updated = Signal(list)   # 子线程完成后传回文件列表    
    rag_loading = Signal(bool, str)    # (是否加载中, 文件名)



class LoaderThread(QThread):
    """启动时并行加载三引擎的后台线程"""

    def __init__(self, controller, signals: Signals):
        super().__init__()
        self.controller = controller
        self.signals = signals

    def run(self):
        try:
            self.signals.loading_progress.emit("正在启动 LLM 引擎...")
            # controller.load_all() 内部并行，会阻塞直到全部完成
            self.controller.on_error = lambda msg: self.signals.loading_error.emit(msg)
            self.controller.on_ready = lambda: self.signals.loading_done.emit()
            self.controller.load_all()
        except Exception as e:
            logger.error(f"LoaderThread error: {e}", exc_info=True)
            self.signals.loading_error.emit(str(e))
