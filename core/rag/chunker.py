from langchain_text_splitters import RecursiveCharacterTextSplitter


class Chunker:
    """
    将长文本切成带重叠的小块，保证语义连贯。
    chunk_size=500  中文约 500 字一块
    chunk_overlap=50  相邻块重叠 50 字，避免截断语义
    """

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", "。", "！", "？", "；", " ", ""],
        )

    def split(self, text: str, source: str = "") -> list[dict]:
        """
        返回 chunk 列表，每个 chunk 格式：
        {"text": "...", "source": "filename.pdf", "chunk_id": 0}
        """
        chunks = self._splitter.split_text(text)
        return [
            {"text": c, "source": source, "chunk_id": i}
            for i, c in enumerate(chunks)
        ]
