from abc import ABC, abstractmethod
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ParsedContent:
    
    text: str
    metadata: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    word_count: int = 0
    char_count: int = 0
    
    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


class BaseParser(ABC):
    
    @property
    @abstractmethod
    def supported_extensions(self) -> list[str]:
        pass
    
    @abstractmethod
    async def parse(self, filepath: Path) -> ParsedContent:
        pass
    
    def _read_file_bytes(self, filepath: Path) -> bytes:

        with open(filepath, "rb") as f:
            return f.read()
    
    def _read_file_text(self, filepath: Path, encoding: str = "utf-8") -> str:

        with open(filepath, "r", encoding=encoding, errors="replace") as f:
            return f.read()