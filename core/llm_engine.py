import subprocess
import requests
import json
import time
import logging
import socket
import yaml
from pathlib import Path

logger = logging.getLogger("llm")

class LLMEngine:
    def __init__(self, config: dict):
        self.config = config
        self.process = None
        self.host = config["host"]
        self.port = config["port"]
        self.base_url = f"http://{self.host}:{self.port}"
        self.thinking = config.get("thinking", False)
        # 项目根目录（main.py 所在目录）
        self._root = Path(__file__).parent.parent.resolve()

    def start(self):
        if self._is_port_in_use():
            logger.warning(f"Port {self.port} already in use, skipping start")
            return

        # 用绝对路径定位 llama-server.exe
        server_exe = self._root / "llama" / "llama-server.exe"
        if not server_exe.exists():
            # 兜底：在 PATH 里找
            import shutil
            found = shutil.which("llama-server")
            if found:
                server_exe = Path(found)
            else:
                raise FileNotFoundError(
                    f"找不到 llama-server.exe，请确认文件在 {server_exe}"
                )

        model_path = (self._root / self.config["model"]).resolve()
        mmproj_path = (self._root / self.config["mmproj"]).resolve()

        if not model_path.exists():
            raise FileNotFoundError(f"模型文件不存在: {model_path}")

        thinking_str = "true" if self.thinking else "false"

        cmd = [
            str(server_exe),
            "--model",    str(model_path),
            "--mmproj",   str(mmproj_path),
            "--host",     self.host,
            "--port",     str(self.port),
            "--ctx-size", str(self.config["ctx_size"]),
            "--n-gpu-layers", str(self.config.get("n_gpu_layers", 99)),
            "--chat-template-kwargs",
            f'{{"enable_thinking":{thinking_str}}}',
        ]

        logger.info(f"Starting llama-server: {' '.join(cmd)}")

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=str(self._root),           # 强制 cwd 为项目根目录
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        logger.info(f"llama-server started, pid={self.process.pid}")
        health_timeout = self.config.get("health_timeout", 60)
        self._wait_until_ready(timeout=health_timeout)

    def _wait_until_ready(self, timeout=60):
        start = time.time()
        while time.time() - start < timeout:
            try:
                r = requests.get(f"{self.base_url}/health", timeout=2)
                if r.status_code == 200:
                    logger.info("llama-server is ready")
                    return
            except Exception:
                pass
            time.sleep(1)
        raise TimeoutError("llama-server failed to start within timeout")

    def _is_port_in_use(self) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex((self.host, self.port)) == 0

    def restart(self, thinking: bool):
        self.thinking = thinking
        self.stop()
        time.sleep(1)
        self.start()

    def stop(self):
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
            logger.info("llama-server stopped")

    def chat_stream(self, messages: list, thinking: bool = False):
        params = self.config["params_thinking"] if thinking else self.config["params_normal"]
        
        payload = {"messages": messages, "stream": True, **params}
        request_timeout = self.config.get("request_timeout", 180)

        with requests.post(
            f"{self.base_url}/v1/chat/completions",
            json=payload,
            stream=True,
            timeout=request_timeout,
        ) as resp:
            for line in resp.iter_lines():
                if not line:
                    continue
                line = line.decode("utf-8")
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0]["delta"]
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except Exception:
                        continue

