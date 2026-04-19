import re
from pathlib import Path

from src.parsers.base import BaseParser, ParsedContent


class RtfParser(BaseParser):
    @property
    def supported_extensions(self) -> list[str]:
        return [".rtf"]

    async def parse(self, filepath: Path) -> ParsedContent:
        try:
            raw = self._read_file_text(filepath, encoding="utf-8")
            text = re.sub(r"\\[a-zA-Z]+\d* ?", "", raw)
            text = re.sub(r"[{}]", "", text)
            text = re.sub(r"\s+", " ", text).strip()
            return ParsedContent(text=text, metadata={"path": str(filepath)}, word_count=len(text.split()), char_count=len(text))
        except Exception as e:
            return ParsedContent(text="", metadata={"path": str(filepath)}, errors=[f"RTF parse error: {e}"])
