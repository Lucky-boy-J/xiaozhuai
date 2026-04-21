import json
import logging
import pickle
from pathlib import Path

import faiss
import numpy as np

logger = logging.getLogger("rag.vector_store")


class VectorStore:
    """
    FAISS 向量库，支持：
    - 增量添加文档
    - 持久化 / 加载
    - top-k 相似检索
    """

    def __init__(self, dim: int, index_dir: str = "knowledge_base/index"):
        self.dim = dim
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)

        self._index = faiss.IndexFlatIP(dim)   # 内积（归一化后等价余弦）
        self._chunks: list[dict] = []          # 元数据列表，与向量行一一对应

    # ── 写入 ──────────────────────────────────────────────────────────

    def add(self, vectors: np.ndarray, chunks: list[dict]):
        """添加向量和对应 chunk 元数据"""
        assert vectors.shape[0] == len(chunks), "向量数量与 chunk 数量不匹配"
        self._index.add(vectors)
        self._chunks.extend(chunks)
        logger.info(f"已添加 {len(chunks)} 条，总计 {len(self._chunks)} 条")

    def save(self, name: str = "default"):
        """持久化到磁盘"""
        faiss.write_index(self._index, str(self.index_dir / f"{name}.faiss"))
        with open(self.index_dir / f"{name}.meta.pkl", "wb") as f:
            pickle.dump(self._chunks, f)
        logger.info(f"向量库已保存：{name}")

    def load(self, name: str = "default") -> bool:
        """从磁盘加载，返回是否成功"""
        idx_path = self.index_dir / f"{name}.faiss"
        meta_path = self.index_dir / f"{name}.meta.pkl"
        if not idx_path.exists():
            return False
        self._index = faiss.read_index(str(idx_path))
        with open(meta_path, "rb") as f:
            self._chunks = pickle.load(f)
        logger.info(f"向量库已加载：{name}，共 {len(self._chunks)} 条")
        return True

    def remove_source(self, source: str):
        """删除某个文件的所有 chunk（重建索引）"""
        keep = [c for c in self._chunks if c["source"] != source]
        if len(keep) == len(self._chunks):
            return  # 没有匹配项
        keep_ids = [i for i, c in enumerate(self._chunks) if c["source"] != source]
        # FAISS FlatIP 不支持直接删除，重建
        old_vectors = self._index.reconstruct_n(0, self._index.ntotal)
        new_vectors = old_vectors[keep_ids]
        self._index = faiss.IndexFlatIP(self.dim)
        if len(new_vectors) > 0:
            self._index.add(new_vectors)
        self._chunks = keep
        logger.info(f"已删除来源：{source}，剩余 {len(self._chunks)} 条")

    # ── 检索 ──────────────────────────────────────────────────────────

    def search(self, query_vec: np.ndarray, top_k: int = 5) -> list[dict]:
        """
        返回 top-k 最相关 chunk，每条附带 score
        """
        if self._index.ntotal == 0:
            return []
        k = min(top_k, self._index.ntotal)
        scores, indices = self._index.search(query_vec, k)
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            chunk = dict(self._chunks[idx])
            chunk["score"] = float(score)
            results.append(chunk)
        return results

    @property
    def total(self) -> int:
        return len(self._chunks)

    def list_sources(self) -> list[str]:
        """列出所有已入库的文件名"""
        return list(dict.fromkeys(c["source"] for c in self._chunks))
