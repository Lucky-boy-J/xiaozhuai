import logging
import tempfile
import threading
import numpy as np
import sounddevice as sd
import soundfile as sf
from pathlib import Path
from collections import deque

logger = logging.getLogger("asr")

class ASREngine:
    def __init__(self, config: dict):
        self.config = config
        self.engine = None
        self._recording = False
        self._audio_buffer = deque()
        self._lock = threading.Lock()
        self.sample_rate = 16000
        self.on_result = None   # callback: fn(text: str)

    def load(self):
        """在加载线程中调用，初始化 ONNX + GGUF 引擎"""
        import os
        # Intel 集显 FP16 溢出保护
        os.environ.setdefault("GGML_VK_DISABLE_F16", "0")

        from qwen_asr_gguf.inference.asr import QwenASREngine, ASREngineConfig

        cfg = self.config
        model_dir = cfg["model_dir"]

        engine_config = ASREngineConfig(
            model_dir=model_dir,
            use_dml=cfg.get("use_dml", True),
            encoder_frontend_fn="qwen3_asr_encoder_frontend.int4.onnx",
            encoder_backend_fn="qwen3_asr_encoder_backend.int4.onnx",
            enable_aligner=cfg.get("enable_aligner", False),
        )
        self.engine = QwenASREngine(config=engine_config)
        logger.info("ASR engine loaded")

    def start_recording(self):
        """开始录音，启动音频采集线程"""
        if self._recording:
            return
        self._recording = True
        self._audio_buffer.clear()
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=4096,
            callback=self._audio_callback,
        )
        self._stream.start()
        logger.info("Recording started")

    def stop_recording_and_transcribe(self) -> str:
        """停止录音，执行转录，返回文本"""
        if not self._recording:
            return ""
        self._recording = False
        self._stream.stop()
        self._stream.close()

        # 拼接音频帧
        with self._lock:
            frames = list(self._audio_buffer)
        if not frames:
            return ""

        audio = np.concatenate(frames, axis=0).flatten()
        min_duration = self.config.get("min_audio_duration", 0.3)
        if len(audio) < self.sample_rate * min_duration:  # 少于 min_duration 秒不处理
            return ""

        # 写入临时 WAV 文件
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_path = f.name
        sf.write(tmp_path, audio, self.sample_rate)

        logger.info(f"Transcribing {len(audio)/self.sample_rate:.1f}s audio...")
        try:
            result = self.engine.transcribe(
                audio_file=tmp_path,
                language=None,   # 自动识别语言
            )
            text = result.text.strip()
            logger.info(f"ASR result: {text}")
            return text
        except Exception as e:
            logger.error(f"ASR transcribe error: {e}")
            return ""
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            logger.warning(f"Audio status: {status}")
        if self._recording:
            with self._lock:
                self._audio_buffer.append(indata.copy())

    def get_volume_rms(self) -> float:
        """给波形动画用的实时音量"""
        with self._lock:
            if not self._audio_buffer:
                return 0.0
            latest = self._audio_buffer[-1]
        return float(np.sqrt(np.mean(latest ** 2)))

    def shutdown(self):
        if self._recording:
            self._recording = False
            self._stream.stop()
            self._stream.close()
        logger.info("ASR engine shutdown")
