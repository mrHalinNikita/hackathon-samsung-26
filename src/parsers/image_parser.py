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
            "parser": "image_ocr",
        }
        
        ocr_url = f"http://{settings.OCR_HOST}:{settings.OCR_PORT}/api/v1/ocr/extract"
        
        try:
            async with aiohttp.ClientSession() as session:

                with open(filepath, "rb") as f:
                    file_bytes = f.read()
                
                form = aiohttp.FormData()
                form.add_field(
                    "file",
                    file_bytes,
                    filename=filepath.name,
                    content_type=f"image/{filepath.suffix.lstrip('.')}"
                )
                form.add_field("language", settings.OCR_TESSERACT_LANGS)
                form.add_field("preprocess", "true")
                
                async with session.post(
                    ocr_url,
                    data=form,
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        return ParsedContent(
                            text=data["text"],
                            metadata={
                                **metadata,
                                "confidence": data["confidence"],
                                "language_detected": data["language_detected"],
                                "processing_time_ms": data["processing_time_ms"],
                            },
                            word_count=len(data["text"].split()),
                            char_count=len(data["text"]),
                        )
                    else:
                        error_text = await resp.text()
                        raise RuntimeError(f"OCR service error {resp.status}: {error_text}")
        
        except FileNotFoundError:
            logger.error("File not found for OCR", path=str(filepath))
            return ParsedContent(
                text="",
                metadata=metadata,
                errors=["File not found"],
            )
        except aiohttp.ClientError as e:
            logger.warning(
                "OCR service unavailable, skipping text extraction",
                path=str(filepath),
                error=str(e),
            )
            return ParsedContent(
                text="",
                metadata=metadata,
                errors=["OCR service connection failed"],
            )
        except Exception as e:
            logger.error(
                "Unexpected error during OCR",
                path=str(filepath),
                error=str(e),
                error_type=type(e).__name__,
            )
            return ParsedContent(
                text="",
                metadata=metadata,
                errors=[f"OCR error: {type(e).__name__}: {e}"],
            )