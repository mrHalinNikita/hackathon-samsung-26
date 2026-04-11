from pathlib import Path
import aiohttp
import structlog

from src.config import settings
from src.parsers.base import BaseParser, ParsedContent

logger = structlog.get_logger("image_parser")


class ImageParser(BaseParser):
    
    @property
    def supported_extensions(self) -> list[str]:
        return [".jpg", ".jpeg", ".png", ".tiff", ".bmp", ".gif"]
    
    async def parse(self, filepath: Path) -> ParsedContent:

        metadata = {
            "path": str(filepath),
            "size_bytes": filepath.stat().st_size,
            "parser": "image_ocr_stub",
        }
        
        # OCR-server
    
        logger.warning(
            "OCR server not available, skipping text extraction",
            path=str(filepath),
        )
        
        return ParsedContent(
            text="",
            metadata=metadata,
            errors=["OCR server not implemented yet"],
        )