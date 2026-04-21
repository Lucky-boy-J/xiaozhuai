import yaml
import os

class ConfigManager:
    def __init__(self, config_path="config.yaml"):
        self.config_path = config_path
        self._config = {}
        self.load()

    def load(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f) or {}
        
        # --- 补全 LLM 配置及魔法数字 ---
        llm = self._config.setdefault("llm", {})
        llm.setdefault("doc_max_length", 12000)
        llm.setdefault("request_timeout", 180)
        llm.setdefault("health_timeout", 60)
        llm.setdefault("thinking", False)
        
        # --- 补全 ASR 配置及魔法数字 ---
        asr = self._config.setdefault("asr", {})
        asr.setdefault("min_audio_duration", 0.3)
        
        # --- 补全 TTS 配置及魔法数字 ---
        tts = self._config.setdefault("tts", {})
        tts.setdefault("default_voice", "assets/voices/default.json")
        tts.setdefault("join_timeout", 60)
        
        # --- 补全 RAG/搜索 配置及魔法数字 ---
        rag = self._config.setdefault("rag", {})
        rag.setdefault("top_k", 5)

        search = self._config.setdefault("search", {})
        search.setdefault("backend", "serper")
        search.setdefault("api_key", "")
        search.setdefault("max_results", 6)
        search.setdefault("timeout", 10)
        search.setdefault("time_window_days", 30)
        search.setdefault("min_credibility", 0.25)
        search.setdefault("trusted_domains", [])
        search.setdefault("blocked_domains", [])
        search.setdefault("allow_unknown_date", True)
        search.setdefault("source_mode", "any")
        search.setdefault("source_domains", [])
    def get(self, key, default=None):
        return self._config.get(key, default)

    def __getitem__(self, key):
        return self._config[key]

    def __setitem__(self, key, value):
        self._config[key] = value
