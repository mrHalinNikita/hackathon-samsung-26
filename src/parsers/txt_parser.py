from pathlib import Path
import chardet

from src.parsers.base import BaseParser, ParsedContent


class TxtParser(BaseParser):
    
    @property
    def supported_extensions(self) -> list[str]:
        return [".txt", ".log", ".tmp", ".md", ".rst"]
    
    async def parse(self, filepath: Path) -> ParsedContent:

        raw = self._read_file_bytes(filepath)
        result = chardet.detect(raw)
        encoding = result["encoding"] or "utf-8"
        
        text = self._read_file_text(filepath, encoding=encoding)
        
        return ParsedContent(
            text=text,
            metadata={
                "path": str(filepath),
                "encoding": encoding,
                "detected_encoding_confidence": result.get("confidence", 0),
            },
            word_count=len(text.split()),
            char_count=len(text),
        )