import logging
import threading
import re
import os
from pathlib import Path
from queue import Queue, Empty

logger = logging.getLogger("tts")

_MD_CLEAN = re.compile(
    r"```.*?```|`[^`]*`|#{1,6}\s|[*_~>|]|$$([^$$]+)\]$[^)]+$",
    re.DOTALL
)

def strip_markdown(text: str) -> str:
    text = _MD_CLEAN.sub(r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


class TTSEngine:
    def __init__(self, config: dict):
        self.config = config
        self.engine = None
        self.stream = None
        self._play_queue = Queue()
        self._stop_event = threading.Event()
        self._player_thread = None
        self.muted = False
    def mute(self):        
        """静音：清空队列，后续合成跳过"""        
        self.muted = True        
        self.interrupt()        
        logger.info("TTS muted")

    def unmute(self):        
        """取消静音"""        
        self.muted = False        
        logger.info("TTS unmuted")

    def load(self):
        from qwen3_tts_gguf.inference.engine import TTSEngine as _TTSEngine

        self.engine = _TTSEngine(
            model_dir=self.config["model_dir"],
            onnx_provider="CUDA",   # ONNX Decoder/Encoder 走 CUDA
            verbose=True,
        )

        if not self.engine.ready:
            raise RuntimeError("TTSEngine 初始化失败，请检查模型文件是否完整")

        self.stream = self.engine.create_stream()

        # 加载或生成默认音色
        voice_path = self.config.get("default_voice", "")
        if voice_path and Path(voice_path).exists():
            result = self.stream.set_voice(voice_path)
            if result:
                logger.info(f"Default voice loaded: {voice_path}")
            else:
                logger.warning("Default voice load failed, will generate on first use")
        else:
            logger.info("No default voice, will generate on first speak")

        self._player_thread = threading.Thread(
            target=self._player_loop, daemon=True
        )
        self._player_thread.start()
        logger.info("TTS engine loaded")

    def speak(self, text: str):
        if self.muted:              # ← 静音时直接返回            
            return
        clean = strip_markdown(text)
        if not clean:
            return
        for sent in self._split_sentences(clean):
            if sent.strip():
                self._play_queue.put(sent)

    def interrupt(self):
        with self._play_queue.mutex:
            self._play_queue.queue.clear()
        self._stop_event.set()
        logger.info("TTS interrupted")

    def _player_loop(self):
        while True:
            try:
                sentence = self._play_queue.get(timeout=0.5)
            except Empty:
                continue
            self._stop_event.clear()
            if not self._stop_event.is_set()and not self.muted:
                self._synthesize_and_play(sentence)

    def _synthesize_and_play(self, text: str):
        from qwen3_tts_gguf.inference.config import TTSConfig

        cfg = TTSConfig(
            temperature=self.config.get("temperature", 0.8),
            sub_temperature=self.config.get("sub_temperature", 0.8),
            seed=self.config.get("seed", 42),
            sub_seed=self.config.get("sub_seed", 45),
            streaming=self.config.get("streaming", True),
        )
        try:
            logger.info(f"TTS synthesizing: {text[:40]}...")

            # 首次无音色：用 design 模式生成并持久化
            if self.stream.voice is None:
                logger.info("No voice anchor, generating default voice...")
                init_cfg = TTSConfig(
                    temperature=0.8,
                    sub_temperature=0.8,
                    seed=42,
                    sub_seed=45,
                    streaming=False,   # 生成音色锚点时不流式，确保完整保存
                )
                anchor = self.stream.design(
                    text="你好，我是小猪AI，很高兴为你服务。",
                    instruct="自然清晰的普通话男声，语速适中，亲切友好",
                    config=init_cfg,
                )
                if anchor:
                    os.makedirs("assets/voices", exist_ok=True)
                    anchor.save("assets/voices/default.json")
                    self.stream.set_voice("assets/voices/default.json")
                    logger.info("Default voice generated → assets/voices/default.json")
                else:
                    logger.error("Failed to generate default voice")
                    return

            result = self.stream.clone(text, config=cfg)

            if result is None:
                logger.warning("TTS clone returned None")
                return

            # 等待本句播放完毕
            join_timeout = self.config.get("join_timeout", 60)
            self.stream.join(timeout=join_timeout)

        except Exception as e:
            logger.error(f"TTS synthesis error: {e}", exc_info=True)

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        parts = re.split(r'(?<=[。！？!?\n])', text)
        return [p for p in parts if p.strip()]

    def shutdown(self):
        self.interrupt()
        if self.engine:
            self.engine.shutdown()
        logger.info("TTS engine shutdown")
