from pathlib import Path
from typing import AsyncIterator
import pdfplumber

from src.config import settings
from src.parsers.base import BaseParser, ParsedChunk, ParsedContent


class PdfParser(BaseParser):
    
    @property
    def supported_extensions(self) -> list[str]:
        return [".pdf"]
    
    async def parse(self, filepath: Path) -> ParsedContent:
        text_parts = []
        metadata = {"path": str(filepath), "pages": 0}
        errors = []
        
        try:
            with pdfplumber.open(filepath) as pdf:
                metadata["pages"] = len(pdf.pages)
                
                for page_num, page in enumerate(pdf.pages, 1):
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(f"[Страница {page_num}]\n{page_text}")
                    
                    if page_num == 1 and pdf.metadata:
                        metadata.update({
                            "author": pdf.metadata.get("Author"),
                            "title": pdf.metadata.get("Title"),
                            "subject": pdf.metadata.get("Subject"),
                            "creator": pdf.metadata.get("Creator"),
                        })
        
        except Exception as e:
            errors.append(f"PDF parse error: {e}")

            try:
                import PyPDF2
                with open(filepath, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        text = page.extract_text()
                        if text:
                            text_parts.append(text)
            except:
                pass
        
        full_text = "\n\n".join(text_parts)
        
        return ParsedContent(
            text=full_text,
            metadata=metadata,
            errors=errors,
            word_count=len(full_text.split()),
            char_count=len(full_text),
        )

    async def parse_chunks(
        self,
        filepath: Path,
        file_hash: str | None = None,
    ) -> AsyncIterator[ParsedChunk]:
        """
        Потоковая дробня PDF:
        - извлекаем текст постранично
        - каждую страницу режем на чанки с overlap
        - сохраняем глобальные смещения, чтобы потом агрегировать детекции по файлу
        """

        chunk_size = settings.CHUNK_SIZE_CHARS
        overlap = settings.CHUNK_OVERLAP_CHARS
        metadata_base = {"path": str(filepath), "pages": 0}
        chunk_id = 0
        global_offset = 0
        pending_chunk: ParsedChunk | None = None

        if chunk_size <= 0:
            raise ValueError("CHUNK_SIZE_CHARS must be > 0")
        if overlap < 0:
            raise ValueError("CHUNK_OVERLAP_CHARS must be >= 0")

        with pdfplumber.open(filepath) as pdf:
            metadata_base["pages"] = len(pdf.pages)

            if pdf.metadata:
                metadata_base.update(
                    {
                        "author": pdf.metadata.get("Author"),
                        "title": pdf.metadata.get("Title"),
                        "subject": pdf.metadata.get("Subject"),
                        "creator": pdf.metadata.get("Creator"),
                    }
                )

            for page_num, page in enumerate(pdf.pages, 1):
                page_text = page.extract_text() or ""
                if not page_text.strip():
                    continue

                page_payload = f"[Страница {page_num}]\n{page_text}"

                emitted_for_page = False
                for chunk_text, start, end in self._iter_text_chunks(
                    page_payload,
                    chunk_size=chunk_size,
                    overlap=overlap,
                    base_offset=global_offset,
                ):
                    emitted_for_page = True
                    current_chunk = ParsedChunk(
                        file_path=str(filepath),
                        file_hash=file_hash,
                        chunk_id=chunk_id,
                        offset_start=start,
                        offset_end=end,
                        text=chunk_text,
                        page_num=page_num,
                        is_last=False,
                        metadata={
                            **metadata_base,
                            "page_num": page_num,
                        },
                    )

                    # Чтобы корректно проставить is_last, держим один chunk в буфере.
                    if pending_chunk is not None:
                        yield pending_chunk
                    pending_chunk = current_chunk
                    chunk_id += 1

                # Сдвигаем глобальный offset на длину исходной page-последовательности.
                if emitted_for_page:
                    global_offset += len(page_payload)

        # Если у PDF вообще нет извлеченного текста, отдаём пустой финальный chunk
        # с ошибкой в metadata — downstream сможет корректно пометить файл как empty.
        if chunk_id == 0:
            yield ParsedChunk(
                file_path=str(filepath),
                file_hash=file_hash,
                chunk_id=0,
                offset_start=0,
                offset_end=0,
                text="",
                is_last=True,
                metadata=metadata_base,
                errors=["PDF contains no extractable text"],
            )
            return

        if pending_chunk is not None:
            pending_chunk.is_last = True
            yield pending_chunk