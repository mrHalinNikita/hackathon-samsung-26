from abc import ABC, abstractmethod
from pathlib import Path
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional


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


@dataclass
class ParsedChunk:
    """
    Унифицированная единица обработки для chunk-пайплайна.

    На Этапе 1 это "контракт" для следующего шага:
    пока большинство парсеров будет отдавать один chunk на файл
    (через fallback-реализацию в BaseParser.parse_chunks),
    а позже специализированные парсеры перейдут на stream/chunk режим.
    """

    file_path: str
    text: str
    chunk_id: int
    offset_start: int
    offset_end: int
    is_last: bool
    file_hash: str | None = None
    page_num: int | None = None
    metadata: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    @property
    def char_count(self) -> int:
        return len(self.text)


class BaseParser(ABC):
    
    @property
    @abstractmethod
    def supported_extensions(self) -> list[str]:
        pass
    
    @abstractmethod
    async def parse(self, filepath: Path) -> ParsedContent:
        pass
    
    async def parse_chunks(
        self,
        filepath: Path,
        file_hash: str | None = None,
    ) -> AsyncIterator[ParsedChunk]:
        """
        Базовый fallback для совместимости.

        Пока парсер не реализовал потоковую обработку, мы сохраняем текущее поведение:
        читаем файл через parse() и возвращаем один chunk.
        Штука нужна чтобы внедрять chunk-пайплайн поэтапно, не ломая существующий код.
        """

        parsed = await self.parse(filepath)
        metadata = dict(parsed.metadata or {})
        page_num = metadata.get("page_num")

        yield ParsedChunk(
            file_path=str(filepath),
            file_hash=file_hash,
            chunk_id=0,
            offset_start=0,
            offset_end=len(parsed.text),
            text=parsed.text,
            page_num=page_num if isinstance(page_num, int) else None,
            is_last=True,
            metadata=metadata,
            errors=list(parsed.errors or []),
        )
        
    def _read_file_bytes(self, filepath: Path) -> bytes:

        with open(filepath, "rb") as f:
            return f.read()
    
    def _read_file_text(self, filepath: Path, encoding: str = "utf-8") -> str:

        with open(filepath, "r", encoding=encoding, errors="replace") as f:
            return f.read()
        
    def _iter_text_chunks(
        self,
        text: str,
        chunk_size: int,
        overlap: int,
        *,
        base_offset: int = 0,
    ) -> Iterator[tuple[str, int, int]]:
        """
        Разбивает строку на чанки с overlap.

        Возвращает последовательность кортежей:
        (chunk_text, global_start_offset, global_end_offset)
        """

        if chunk_size <= 0:
            raise ValueError("chunk_size must be > 0")

        if overlap < 0:
            raise ValueError("overlap must be >= 0")

        # overlap должен быть меньше размера чанка, иначе окно не сдвигается.
        effective_overlap = min(overlap, chunk_size - 1) if chunk_size > 1 else 0
        step = chunk_size - effective_overlap

        if not text:
            return

        start = 0
        text_len = len(text)
        while start < text_len:
            end = min(start + chunk_size, text_len)
            chunk_text = text[start:end]
            yield chunk_text, base_offset + start, base_offset + end

            if end >= text_len:
                break

            start += step