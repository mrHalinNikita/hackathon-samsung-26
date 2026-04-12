import pytesseract
from PIL import Image
import cv2
import numpy as np
from pathlib import Path
from typing import Optional

from src.services.ocr.config import settings
from src.services.ocr.logger import get_logger

logger = get_logger("ocr_engine")


class OCREngine:
    
    def __init__(self):
        if settings.TESSERACT_PATH:
            pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_PATH
        
        self.default_lang = settings.TESSERACT_LANGS
        self.min_confidence = settings.MIN_CONFIDENCE
        
        logger.debug("OCREngine initialized", langs=self.default_lang)
    
    def _preprocess_image(self, image_path: Path) -> Image.Image:

        img = cv2.imread(str(image_path))
        if img is None:
            raise ValueError(f"Cannot read image: {image_path}")
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        _, binary = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        
        kernel = np.ones((1, 1), np.uint8)
        cleaned = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel)
        
        pil_image = Image.fromarray(cleaned)
        
        return pil_image
    
    def extract_text(self, image_path: Path, language: Optional[str] = None, preprocess: bool = True,) -> dict:

        lang = language or self.default_lang
        
        file_size_mb = image_path.stat().st_size / 1024 / 1024
        if file_size_mb > settings.MAX_IMAGE_SIZE_MB:
            raise ValueError(
                f"Image too large: {file_size_mb:.2f}MB > {settings.MAX_IMAGE_SIZE_MB}MB"
            )
        
        if preprocess:
            image = self._preprocess_image(image_path)
        else:
            image = Image.open(image_path)
        
        config = f"--oem 3 --psm 6 -l {lang}"
        
        data = pytesseract.image_to_data(
            image,
            config=config,
            output_type=pytesseract.Output.DICT,
        )
        
        texts = []
        confidences = []
        
        for i, text in enumerate(data["text"]):
            text = text.strip()
            conf = float(data["conf"][i])
            
            if text and conf >= self.min_confidence:
                texts.append(text)
                confidences.append(conf)
        
        extracted_text = " ".join(texts)
        avg_confidence = np.mean(confidences) if confidences else 0.0
        
        lang_detected = self._detect_language(extracted_text)
        
        return {
            "text": extracted_text,
            "confidence": round(avg_confidence, 2),
            "language_detected": lang_detected,
            "metadata": {
                "blocks_found": len(texts),
                "image_size": f"{image.width}x{image.height}",
                "preprocessed": preprocess,
            },
        }
    
    def _detect_language(self, text: str) -> Optional[str]:

        if not text:
            return None
        
        cyrillic = sum(1 for c in text if '\u0400' <= c <= '\u04FF')
        latin = sum(1 for c in text if c.isascii() and c.isalpha())
        
        total = cyrillic + latin
        if total == 0:
            return None
        
        if cyrillic / total > 0.7:
            return "rus"
        elif latin / total > 0.7:
            return "eng"
        
        return None


ocr_engine = OCREngine()