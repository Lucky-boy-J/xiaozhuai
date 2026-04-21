import logging
from pathlib import Path

from .chunker import Chunker
from .embedder import Embedder
from .file_parser import FileParser
from .vector_store import VectorStore

logger = logging.getLogger("rag")

INDEX_NAME = "default"


class RAGEngine:

    def __init__(self, index_dir: str = "knowledge_base/index"):
        self.embedder = Embedder()
        self.store = VectorStore(dim=self.embedder.dim, index_dir=index_dir)
        self.chunker = Chunker()
        self.store.load(INDEX_NAME)   # 启动时加载已有索引

    # ── 文件入库 ──────────────────────────────────────────────────────

    def add_file(self, file_path: str) -> int:
        """解析文件 → 分块 → Embedding → 入库，返回新增 chunk 数"""
        source = Path(file_path).name

        # 已入库则先删除旧版本（支持重新导入）
        if source in self.store.list_sources():
            logger.info(f"文件已存在，先删除旧版本：{source}")
            self.store.remove_source(source)

        text = FileParser.parse(file_path)
        chunks = self.chunker.split(text, source=source)
        if not chunks:
            raise ValueError(f"文件内容为空：{source}")

        texts = [c["text"] for c in chunks]
        vectors = self.embedder.encode(texts)
        self.store.add(vectors, chunks)
        self.store.save(INDEX_NAME)

        logger.info(f"文件入库完成：{source}，{len(chunks)} 个 chunk")
        return len(chunks)

    # ── 检索 ──────────────────────────────────────────────────────────

    def query(self, question: str, top_k: int = 5) -> list[dict]:
        """检索最相关的 top_k 个 chunk"""
        if self.store.total == 0:
            return []
        query_vec = self.embedder.encode_query(question)
        return self.store.search(query_vec, top_k=top_k)

    def build_context(self, question: str, top_k: int = 5, score_threshold: float = 0.3) -> str:
        """
        检索并拼接为 prompt 上下文字符串。
        score 低于阈值的 chunk 丢弃，避免引入噪声。
        """
        results = self.query(question, top_k=top_k)
        filtered = [r for r in results if r["score"] >= score_threshold]
        if not filtered:
            return ""

        parts = []
        for i, r in enumerate(filtered, 1):
            parts.append(
                f"【参考片段 {i}】来源：{r['source']}\n{r['text']}"
            )
        return "\n\n---\n\n".join(parts)

    # ── 管理 ──────────────────────────────────────────────────────────

    def delete_file(self, source: str):
        self.store.remove_source(source)
        self.store.save(INDEX_NAME)

    def list_files(self) -> list[str]:
        return self.store.list_sources()
