import csv
from pathlib import Path

from src.parsers.base import BaseParser, ParsedContent


class CsvParser(BaseParser):
    @property
    def supported_extensions(self) -> list[str]:
        return [".csv"]

    async def parse(self, filepath: Path) -> ParsedContent:
        lines: list[str] = []
        metadata = {"path": str(filepath), "rows": 0, "columns": 0, "parser_mode": "structured"}

        try:
            with open(filepath, "r", encoding="utf-8", errors="replace", newline="") as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames or []
                metadata["columns"] = len(headers)

                for row_idx, row in enumerate(reader, start=1):
                    if not row:
                        continue
                    pairs = []
                    for key, value in row.items():
                        if key is None:
                            continue
                        cell = (value or "").strip()
                        if not cell:
                            continue
                        pairs.append(f"{key.strip()}: {cell}")
                    if pairs:
                        lines.append(f"ROW[{row_idx}] | " + " | ".join(pairs))
                metadata["rows"] = row_idx if "row_idx" in locals() else 0
        except Exception as e:
            return ParsedContent(text="", metadata=metadata, errors=[f"CSV parse error: {e}"])

        full_text = "\n".join(lines)
        return ParsedContent(text=full_text, metadata=metadata, word_count=len(full_text.split()), char_count=len(full_text))
