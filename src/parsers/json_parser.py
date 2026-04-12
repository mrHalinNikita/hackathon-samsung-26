import json
from pathlib import Path

from src.parsers.base import BaseParser, ParsedContent


class JsonParser(BaseParser):
    
    @property
    def supported_extensions(self) -> list[str]:
        return [".json"]
    
    async def parse(self, filepath: Path) -> ParsedContent:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            def extract_strings(obj) -> list[str]:
                strings = []
                if isinstance(obj, str):
                    strings.append(obj)
                elif isinstance(obj, dict):
                    for v in obj.values():
                        strings.extend(extract_strings(v))
                elif isinstance(obj, list):
                    for item in obj:
                        strings.extend(extract_strings(item))
                return strings
            
            strings = extract_strings(data)
            text = "\n".join(strings)
            
            return ParsedContent(
                text=text,
                metadata={
                    "path": str(filepath),
                    "json_keys_count": len(data) if isinstance(data, dict) else 0,
                    "is_array": isinstance(data, list),
                },
                word_count=len(text.split()),
                char_count=len(text),
            )
        
        except json.JSONDecodeError as e:
            return ParsedContent(text="", metadata={"path": str(filepath)}, errors=[f"JSON decode error: {e}"],)