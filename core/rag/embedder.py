import logging
import numpy as np

logger = logging.getLogger("rag.embedder")

# 推荐模型：中英双语，384 维，速度快，显存占用低
DEFAULT_MODEL = "BAAI/bge-small-zh-v1.5"


class Embedder:

    def __init__(self, model_name: str = DEFAULT_MODEL):
        logger.info(f"加载 Embedding 模型：{model_name}")
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name, device="cuda")
        self.dim = self.model.get_embedding_dimension()
        logger.info(f"Embedding 维度：{self.dim}")

    def encode(self, texts: list[str], batch_size: int = 64) -> np.ndarray:
        """批量编码，返回 float32 ndarray，shape=(N, dim)"""
        vectors = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=len(texts) > 100,
            normalize_embeddings=True,   # 归一化后用内积代替余弦，更快
            convert_to_numpy=True,
        )
        return vectors.astype(np.float32)

    def encode_query(self, query: str) -> np.ndarray:
        """单条查询编码，shape=(1, dim)"""
        # BGE 模型查询时需要加前缀
        prefixed = f"为这个句子生成表示以用于检索相关文章：{query}"
        vec = self.model.encode(
            [prefixed],
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return vec.astype(np.float32)
