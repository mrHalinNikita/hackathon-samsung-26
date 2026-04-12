import csv
from pathlib import Path
from io import StringIO

from src.parsers.base import BaseParser, ParsedContent


class CsvParser(BaseParser):
    
    @property
    def supported_extensions(self) -> list[str]:
        return [".csv"]
    
    async def parse(self, filepath: Path) -> ParsedContent:
        text_content = []
        metadata = {"path": str(filepath), "rows": 0, "columns": 0}
        
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace", newline="") as f:
                reader = csv.reader(f)
                rows = list(reader)
                
                if rows:
                    metadata["columns"] = len(rows[0])
                    metadata["rows"] = len(rows)
                    text_content = ["\t".join(row) for row in rows]
        
        except Exception as e:
            return ParsedContent(text="", metadata=metadata, errors=[f"CSV parse error: {e}"],)
        
        full_text = "\n".join(text_content)
        
        return ParsedContent(text=full_text, metadata=metadata, word_count=len(full_text.split()), char_count=len(full_text),)