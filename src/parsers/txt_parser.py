from pathlib import Path
from typing import AsyncIterator
import chardet

from src.config import settings
from src.parsers.base import BaseParser, ParsedChunk, ParsedContent

class TxtParser(BaseParser):
    
    @property
    def supported_extensions(self) -> list[str]:
        return [".txt", ".log", ".tmp", ".md", ".rst"]
    

    def _detect_encoding(self, filepath: Path) -> tuple[str, float]:
        """
        Определяем кодировку по сэмплу, а не по всему файлу,
        чтобы не загружать большие файлы целиком в память.
        """

        sample_size = settings.CHUNK_DETECT_ENCODING_SAMPLE_BYTES
        with open(filepath, "rb") as f:
            sample = f.read(sample_size)

        detected = chardet.detect(sample)
        encoding = detected.get("encoding") or "utf-8"
        confidence = float(detected.get("confidence") or 0.0)
        return encoding, confidence

    async def parse(self, filepath: Path) -> ParsedContent:

        encoding, confidence = self._detect_encoding(filepath)
        
        text = self._read_file_text(filepath, encoding=encoding)
        
        return ParsedContent(
            text=text,
            metadata={
                "path": str(filepath),
                "encoding": encoding,
                "detected_encoding_confidence": confidence,
            },
            word_count=len(text.split()),
            char_count=len(text),
        )

    async def parse_chunks(
        self,
        filepath: Path,
        file_hash: str | None = None,
    ) -> AsyncIterator[ParsedChunk]:
        """
        Потоковая дробня TXT/LOG/MD файлов:
        читаем файл построчно и выдаем чанки фиксированного размера.
        """

        encoding, confidence = self._detect_encoding(filepath)
        chunk_size = settings.CHUNK_SIZE_CHARS
        overlap = settings.CHUNK_OVERLAP_CHARS

        # Тут защита от некорректной конфигурации.
        if chunk_size <= 0:
            raise ValueError("CHUNK_SIZE_CHARS must be > 0")
        if overlap < 0:
            raise ValueError("CHUNK_OVERLAP_CHARS must be >= 0")
        if overlap >= chunk_size:
            overlap = chunk_size - 1

        buffer = ""
        offset_cursor = 0
        chunk_id = 0

        with open(filepath, "r", encoding=encoding, errors="replace") as f:
            for line in f:
                buffer += line

                while len(buffer) >= chunk_size:
                    chunk_text = buffer[:chunk_size]
                    yield ParsedChunk(
                        file_path=str(filepath),
                        file_hash=file_hash,
                        chunk_id=chunk_id,
                        offset_start=offset_cursor,
                        offset_end=offset_cursor + len(chunk_text),
                        text=chunk_text,
                        is_last=False,
                        metadata={
                            "path": str(filepath),
                            "encoding": encoding,
                            "detected_encoding_confidence": confidence,
                        },
                    )
                    chunk_id += 1

                    step = chunk_size - overlap
                    offset_cursor += step
                    buffer = buffer[step:]

        # Последний chunk (остаток + overlap-хвост).
        if buffer:
            yield ParsedChunk(
                file_path=str(filepath),
                file_hash=file_hash,
                chunk_id=chunk_id,
                offset_start=offset_cursor,
                offset_end=offset_cursor + len(buffer),
                text=buffer,
                is_last=True,
                metadata={
                    "path": str(filepath),
                    "encoding": encoding,
                    "detected_encoding_confidence": confidence,
                },
            )