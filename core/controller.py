import logging
import threading
import yaml
from typing import Optional
from core.llm_engine import LLMEngine
from core.asr_engine import ASREngine
from core.tts_engine import TTSEngine
from core.memory import should_compress, compress_history

from core.config import ConfigManager

logger = logging.getLogger("controller")

class Controller:
    def __init__(self, config_path="config.yaml"):
        self.cfg = ConfigManager(config_path)

        self.llm = LLMEngine(self.cfg["llm"])
        self.asr = ASREngine(self.cfg["asr"])
        self.tts = TTSEngine(self.cfg["tts"])

        # 搜索引擎（轻量，不需要加载线程）
        from core.search_engine import SearchEngine
        self.search = SearchEngine(self.cfg.get("search", {}))
        from core.rag.rag_engine import RAGEngine
        self.rag_engine = RAGEngine()


        self.chat_history = []
        self.on_token = None
        self.on_llm_done = None
        self.on_asr_result = None
        self.on_error = None
        self.on_ready = None
        self.on_search_start = None    # 新增：搜索开始回调
        self.on_search_done = None     # 新增：搜索完成回调
        
        self.on_rag_loading = None
        self.on_rag_files_updated = None
        self.on_loading_progress = None

    def add_knowledge_file_async(self, path: str):
        import os, threading
        filename = os.path.basename(path)
        
        def safe_call(fn, *args):
            if fn is None: return
            try: fn(*args)
            except RuntimeError: pass

        safe_call(self.on_rag_loading, True, filename)

        def _worker():
            try:
                self.rag_engine.add_file(path)
                files = self.rag_engine.list_files()
                safe_call(self.on_rag_files_updated, files)
                safe_call(self.on_loading_progress, f"✅ 已入库：{filename}")
            except Exception as e:
                logger.error(f"RAG add error: {e}", exc_info=True)
                safe_call(self.on_error, f"知识库添加失败: {str(e)[:40]}")
            finally:
                safe_call(self.on_rag_loading, False, "")

        threading.Thread(target=_worker, daemon=True).start()

    def delete_knowledge_file_async(self, filename: str):
        import threading
        
        def safe_call(fn, *args):
            if fn is None: return
            try: fn(*args)
            except RuntimeError: pass

        def _worker():
            try:
                self.rag_engine.delete_file(filename)
                files = self.rag_engine.list_files()
                safe_call(self.on_rag_files_updated, files)
            except Exception as e:
                logger.error(f"RAG delete error: {e}", exc_info=True)
                safe_call(self.on_error, f"知识库删除失败: {str(e)[:40]}")

        threading.Thread(target=_worker, daemon=True).start()

    def send_message(self, text: str, image_b64: str = None,
                    search_query: str = None, doc_text: str = None):
        self.tts.interrupt()

        if image_b64:
            content = [
                {"type": "text", "text": text},
                {"type": "image_url", "image_url": {
                    "url": f"data:image/jpeg;base64,{image_b64}"
                }},
            ]
        else:
            content = text

        self.chat_history.append({"role": "user", "content": content})

        import threading
        threading.Thread(
            target=self._stream_worker,
            args=(search_query, doc_text),
            daemon=True
        ).start()

    def _stream_worker(self, search_query=None, doc_text=None):
        full_response = ""
        sentence_buf = ""

        # 统一的安全 emit 工具，避免对象已销毁时崩溃
        def safe_call(fn, *args):
            if fn is None:
                return
            try:
                fn(*args)
            except RuntimeError:
                pass  # Signal source has been deleted，静默忽略

        try:
            # ── 1. 取出用户问题文本 ──────────────────────────────────
            last_user = self.chat_history[-1]["content"]
            user_text = (
                last_user if isinstance(last_user, str)
                else next((p["text"] for p in last_user if p.get("type") == "text"), "")
            )

            rag_context = None
            search_context = None

            # ── 2. 场景A：文件对话，直接注入全文 ────────────────────
            if doc_text:
                pass # 已移至 PromptBuilder 处理

            # ── 3. 场景B：向量知识库检索 ─────────────────────────────
            if self.rag_engine and self.rag_engine.store.total > 0:
                top_k = self.cfg.get("rag", {}).get("top_k", 5)
                rag_context = self.rag_engine.build_context(user_text, top_k=top_k)
                if rag_context:
                    logger.info("RAG 命中，准备注入上下文")

            # ── 4. 联网搜索注入 ──────────────────────────────────────
            if search_query:
                safe_call(self.on_search_start, search_query)
                search_results = self.search.search(search_query)
                search_context = self.search.format_results_as_context(search_results, search_query)
                safe_call(self.on_search_done, len(search_results))

                    # ── 5. 记忆压缩（历史过长时自动触发）────────────────────
            if should_compress(self.chat_history):
                params = self.cfg["llm"].get("params_normal", {})
                self.chat_history = compress_history(
                    self.chat_history,
                    self.llm.base_url,
                    params
                )
                logger.info("对话历史已触发压缩")

            # ── 6. 使用 PromptBuilder 拼装 messages ─────────────────────────────────────
            from core.prompt_builder import PromptBuilder
            base_prompt = self.cfg["llm"].get("system_prompt", "你是小猪AI，一个本地运行的智能助手。")
            max_doc_length = self.cfg["llm"]["doc_max_length"]
            
            messages = PromptBuilder.build_messages(
                chat_history=self.chat_history,
                base_system_prompt=base_prompt,
                doc_text=doc_text,
                rag_context=rag_context,
                search_context=search_context,
                max_doc_length=max_doc_length
            )
            
            # ── 7. 流式生成 ──────────────────────────────────────────
            thinking = self.cfg["llm"].get("thinking", False)
            for token in self.llm.chat_stream(messages, thinking):
                full_response += token
                sentence_buf += token
                safe_call(self.on_token, token)          # ← 用 safe_call 包裹
                if any(c in sentence_buf for c in "。！？!?"):
                    self.tts.speak(sentence_buf)
                    sentence_buf = ""

            if sentence_buf.strip():
                self.tts.speak(sentence_buf)

            self.chat_history.append({"role": "assistant", "content": full_response})
            if search_query and search_results:
                sources_md = self.search.format_results_as_sources(search_results, search_query)
                if sources_md:
                    full_response += sources_md
                    safe_call(self.on_token, sources_md)
        except Exception as e:
            logger.error(f"Stream worker error: {e}", exc_info=True)
            safe_call(self.on_error, str(e))             # ← 用 safe_call 包裹
        finally:
            safe_call(self.on_llm_done)                  # ← 用 safe_call 包裹



    def load_all(self):
        """加载三引擎，TTS 单独顺序加载避免 Windows multiprocessing 问题"""
        import threading
        errors = []

        # LLM 和 ASR 并行加载
        def load_llm():
            try:
                self.llm.start()
            except Exception as e:
                errors.append(f"LLM: {e}")

        def load_asr():
            try:
                self.asr.load()
            except Exception as e:
                errors.append(f"ASR: {e}")

        threads = [
            threading.Thread(target=load_llm),
            threading.Thread(target=load_asr),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # TTS 单独加载（内部有 multiprocessing，需要在独立线程但保证 spawn 安全）
        try:
            self.tts.load()
        except Exception as e:
            errors.append(f"TTS: {e}")

        if errors:
            if self.on_error:
                self.on_error("\n".join(errors))
        else:
            if self.on_ready:
                self.on_ready()


    def start_recording(self):
        self.tts.interrupt()
        self.asr.start_recording()

    def stop_recording(self):
        text = self.asr.stop_recording_and_transcribe()
        if text and self.on_asr_result:
            self.on_asr_result(text)
        return text

    def set_thinking(self, enabled: bool):
        """切换 thinking 模式，需要重启 llama-server"""
        self.cfg["llm"]["thinking"] = enabled
        threading.Thread(
            target=self.llm.restart,
            args=(enabled,),
            daemon=True
        ).start()

    def shutdown(self):
        self.tts.shutdown()
        self.asr.shutdown()
        self.llm.stop()
        logger.info("All engines shutdown")




