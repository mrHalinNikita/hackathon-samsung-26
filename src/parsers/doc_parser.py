from pathlib import Path

from src.parsers.base import BaseParser, ParsedContent


class DocParser(BaseParser):
    @property
    def supported_extensions(self) -> list[str]:
        return [".doc"]

    async def parse(self, filepath: Path) -> ParsedContent:
        try:
            raw = self._read_file_bytes(filepath)
            text = raw.decode("cp1251", errors="ignore")
            return ParsedContent(text=text, metadata={"path": str(filepath)}, word_count=len(text.split()), char_count=len(text))
        except Exception as e:
            return ParsedContent(text="", metadata={"path": str(filepath)}, errors=[f"DOC parse error: {e}"])
