import json
from pathlib import Path

from src.parsers.base import BaseParser, ParsedContent


class JsonParser(BaseParser):
    @property
    def supported_extensions(self) -> list[str]:
        return [".json"]

    async def parse(self, filepath: Path) -> ParsedContent:
        metadata = {"path": str(filepath), "parser_mode": "structured"}

        def flatten(obj, prefix: str = "") -> list[str]:
            lines: list[str] = []
            if isinstance(obj, dict):
                for k, v in obj.items():
                    key = f"{prefix}.{k}" if prefix else str(k)
                    lines.extend(flatten(v, key))
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    key = f"{prefix}[{i}]" if prefix else f"[{i}]"
                    lines.extend(flatten(item, key))
            else:
                if obj is not None:
                    lines.append(f"{prefix}: {obj}")
            return lines

        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                data = json.load(f)

            lines = flatten(data)
            text = "\n".join(lines)
            metadata["json_keys_count"] = len(data) if isinstance(data, dict) else 0
            metadata["is_array"] = isinstance(data, list)
            return ParsedContent(text=text, metadata=metadata, word_count=len(text.split()), char_count=len(text))

        except json.JSONDecodeError as e:
            return ParsedContent(text="", metadata=metadata, errors=[f"JSON decode error: {e}"])
