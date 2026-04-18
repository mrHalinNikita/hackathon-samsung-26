import cv2
import numpy as np
from PIL import Image
import pytesseract
from pathlib import Path
from typing import Optional, Dict, List
import math

from src.services.ocr.config import settings
from src.services.ocr.logger import get_logger

logger = get_logger("ocr_engine")


class OCREngine:
    def __init__(self):
        if settings.TESSERACT_PATH:
            pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_PATH
        
        self.default_lang = settings.TESSERACT_LANGS
        self.min_confidence = settings.MIN_CONFIDENCE
        self.target_dpi = 300
        logger.debug("OCREngine initialized", langs=self.default_lang)

    def _preprocess_image(self, image_path: Path) -> Image.Image:
        img = cv2.imread(str(image_path))
        if img is None:
            raise ValueError(f"Cannot read image: {image_path}")

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        denoised = cv2.fastNlMeansDenoising(gray, None, h=10, templateWindowSize=7, searchWindowSize=21)

        thresh = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, blockSize=15, C=2
        )

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel, iterations=1)

        angle = self._get_skew_angle(cleaned)
        if abs(angle) > 0.5:
            h, w = cleaned.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            cleaned = cv2.warpAffine(
                cleaned, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
            )

        h, w = cleaned.shape
        if h < 600:
            scale = self.target_dpi / 150
            new_w, new_h = int(w * scale), int(h * scale)
            cleaned = cv2.resize(cleaned, (new_w, new_h), interpolation=cv2.INTER_CUBIC)

        return Image.fromarray(cleaned)

    @staticmethod
    def _get_skew_angle(img: np.ndarray) -> float:

        edges = cv2.Canny(img, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(
            edges, rho=1, theta=np.pi / 180, threshold=100, minLineLength=100, maxLineGap=10
        )
        if lines is None:
            return 0.0

        angles = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
            if -45 < angle < 45:
                angles.append(angle)

        return float(np.median(angles)) if angles else 0.0

    def extract_text(
        self, 
        image_path: Path, 
        language: Optional[str] = None, 
        preprocess: bool = True,
        psm: Optional[int] = None
    ) -> Dict:
        lang = language or self.default_lang
        lang = lang.replace(",", "+").replace(" ", "+")

        file_size_mb = image_path.stat().st_size / 1024 / 1024
        if file_size_mb > settings.MAX_IMAGE_SIZE_MB:
            raise ValueError(f"Image too large: {file_size_mb:.2f}MB > {settings.MAX_IMAGE_SIZE_MB}MB")

        image = self._preprocess_image(image_path) if preprocess else Image.open(image_path)

        effective_psm = psm if psm is not None else 3
        config = f"--oem 3 --psm {effective_psm} -l {lang}"

        data = pytesseract.image_to_data(
            image, config=config, output_type=pytesseract.Output.DICT
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
        avg_confidence = float(np.mean(confidences)) if confidences else 0.0

        lang_detected = self._detect_language(extracted_text) or lang

        return {
            "text": extracted_text,
            "confidence": round(avg_confidence, 2),
            "language_detected": lang_detected,
            "metadata": {
                "blocks_found": len(texts),
                "image_size": f"{image.width}x{image.height}",
                "preprocessed": preprocess,
                "psm": effective_psm,
                "lang_config": lang,
            },
        }

    @staticmethod
    def _detect_language(text: str) -> Optional[str]:
        if not text:
            return None
        cyrillic = sum(1 for c in text if '\u0400' <= c <= '\u04FF')
        latin = sum(1 for c in text if c.isascii() and c.isalpha())
        total = cyrillic + latin
        if total == 0:
            return None
        ratio_cyr = cyrillic / total
        if ratio_cyr > 0.6:
            return "rus"
        elif (1 - ratio_cyr) > 0.6:
            return "eng"
        return "mixed"


ocr_engine = OCREngine()