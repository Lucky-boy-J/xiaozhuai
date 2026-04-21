import logging
from pathlib import Path

logger = logging.getLogger("rag.parser")


class FileParser:

    SUPPORTED = {".pdf", ".docx", ".txt", ".md"}

    @classmethod
    def parse(cls, file_path: str) -> str:
        """解析文件，返回纯文本"""
        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix not in cls.SUPPORTED:
            raise ValueError(f"不支持的文件类型：{suffix}，支持：{cls.SUPPORTED}")

        if suffix == ".pdf":
            return cls._parse_pdf(path)
        elif suffix == ".docx":
            return cls._parse_docx(path)
        elif suffix in {".txt", ".md"}:
            return cls._parse_text(path)

    @staticmethod
    def _parse_pdf(path: Path) -> str:
        import fitz  # pymupdf
        doc = fitz.open(str(path))
        texts = []
        for page in doc:
            text = page.get_text("text")
            if text.strip():
                texts.append(text)
        doc.close()
        logger.info(f"PDF 解析完成：{path.name}，共 {len(texts)} 页有效内容")
        return "\n\n".join(texts)

    @staticmethod
    def _parse_docx(path: Path) -> str:
        from docx import Document
        doc = Document(str(path))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        logger.info(f"Word 解析完成：{path.name}，共 {len(paragraphs)} 段")
        return "\n\n".join(paragraphs)

    @staticmethod
    def _parse_text(path: Path) -> str:
        # 自动检测编码
        for encoding in ("utf-8", "gbk", "utf-16"):
            try:
                text = path.read_text(encoding=encoding)
                logger.info(f"文本解析完成：{path.name}，编码：{encoding}")
                return text
            except UnicodeDecodeError:
                continue
        raise RuntimeError(f"无法解析文件编码：{path.name}")
