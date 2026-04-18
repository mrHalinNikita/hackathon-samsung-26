import time
import os
import cv2
import numpy as np
from PIL import Image
import pytesseract
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict
import math

from src.services.ocr.config import settings
from src.services.ocr.logger import get_logger
from src.services.ocr.schemas import OCRMetadata

logger = get_logger("ocr.engine")


@dataclass
class WordResult:
    text: str
    confidence: float
    bbox: Dict[str, int]
    line_num: int
    word_num: int
    page_num: int = 0


class ImagePreprocessor:
    
    def __init__(self):
        self.denoise = settings.PREPROCESS_DENOISE
        self.adaptive_thresh = settings.PREPROCESS_ADAPTIVE_THRESH
        self.deskew = settings.PREPROCESS_DESKEW
        self.scale_dpi = settings.PREPROCESS_SCALE_DPI
        self.target_dpi = settings.PREPROCESS_TARGET_DPI
    
    def preprocess(self, image_path: Path) -> Image.Image:
        img = cv2.imread(str(image_path))
        if img is None:
            raise ValueError(f"Cannot read image: {image_path}")
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        if self.denoise:
            gray = cv2.fastNlMeansDenoising(
                gray, h=10, templateWindowSize=7, searchWindowSize=21
            )
        
        if self.adaptive_thresh:
            binary = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, blockSize=15, C=2
            )
        else:
            _, binary = cv2.threshold(
                gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
            )
        
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        cleaned = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel, iterations=1)
        
        if self.deskew:
            angle = self._estimate_skew_angle(cleaned)
            if abs(angle) > 0.5:
                cleaned = self._rotate_image(cleaned, angle)
        
        if self.scale_dpi:
            cleaned = self._scale_to_dpi(cleaned)
        
        return Image.fromarray(cleaned)
    
    @staticmethod
    def _estimate_skew_angle(img: np.ndarray) -> float:
        edges = cv2.Canny(img, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(
            edges, rho=1, theta=np.pi/180, threshold=100,
            minLineLength=100, maxLineGap=10
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
    
    @staticmethod
    def _rotate_image(img: np.ndarray, angle: float) -> np.ndarray:
        h, w = img.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        return cv2.warpAffine(
            img, M, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE
        )
    
    def _scale_to_dpi(self, img: np.ndarray) -> np.ndarray:
        h, w = img.shape
        if h < 600:
            scale = self.target_dpi / 150
            new_w, new_h = int(w * scale), int(h * scale)
            return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        return img


class OCREngine:
    
    def __init__(self):
        if settings.TESSERACT_PATH:
            pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_PATH
        
        if settings.TESSERACT_DATA_PATH:
            os.environ['TESSDATA_PREFIX'] = settings.TESSERACT_DATA_PATH
        
        self.default_lang = self._normalize_lang(settings.TESSERACT_LANGS)
        self.min_confidence = settings.MIN_CONFIDENCE
        self.default_psm = settings.DEFAULT_PSM
        self.default_oem = settings.DEFAULT_OEM
        self.word_level = settings.WORD_LEVEL_EXTRACTION
        
        self.preprocessor = ImagePreprocessor() if settings.PREPROCESS_ENABLED else None
        
        self.hybrid_enabled = settings.HYBRID_ENABLED
        self.hybrid_threshold = settings.HYBRID_CONFIDENCE_THRESHOLD
        
        logger.info(
            "OCREngine initialized",
            langs=self.default_lang,
            hybrid=self.hybrid_enabled,
            word_level=self.word_level,
            preprocess=settings.PREPROCESS_ENABLED
        )
    
    @staticmethod
    def _normalize_lang(lang: str) -> str:
        if not lang:
            return "eng"
        return lang.replace(",", "+").replace(" ", "+").strip()
    
    def extract_text(
        self,
        image_path: Path,
        language: Optional[str] = None,
        preprocess: Optional[bool] = None,
        psm: Optional[int] = None,
        oem: Optional[int] = None,
        return_words: bool = False,
    ) -> Dict:

        start_time = time.perf_counter()
        
        lang = self._normalize_lang(language) if language else self.default_lang
        use_preprocess = preprocess if preprocess is not None else settings.PREPROCESS_ENABLED
        effective_psm = psm if psm is not None else self.default_psm
        effective_oem = oem if oem is not None else self.default_oem
        
        self._validate_file(image_path)
        
        image = self._load_image(image_path, use_preprocess)
        
        config = f"--oem {effective_oem} --psm {effective_psm} -l {lang}"
        
        if return_words or self.word_level:
            result = self._extract_with_words(image, config)
        else:
            result = self._extract_plain_text(image, config)
        
        if self.hybrid_enabled and result["confidence"] < self.hybrid_threshold:
            result = self._hybrid_fallback(result, image_path, lang)
        
        processing_time_ms = (time.perf_counter() - start_time) * 1000
        
        metadata = OCRMetadata(
            image_size=f"{image.width}x{image.height}",
            preprocessed=use_preprocess,
            psm=effective_psm,
            oem=effective_oem,
            language_config=lang,
            blocks_found=result.get("blocks_count", 0),
            words_found=len(result.get("words", [])),
            hybrid_applied=result.get("hybrid_applied"),
            hybrid_reason=result.get("hybrid_reason"),
        )
        
        response = {
            "text": result["text"],
            "confidence": round(result["confidence"], 2),
            "language_detected": self._detect_language(result["text"]) or lang.split("+")[0],
            "processing_time_ms": round(processing_time_ms, 2),
            "metadata": metadata.model_dump(),
        }
        
        if return_words or self.word_level:
            response["words"] = result.get("words", [])
        
        return response
    
    def _validate_file(self, path: Path) -> None:
        if not path.exists():
            raise ValueError(f"File not found: {path}")
        
        size_mb = path.stat().st_size / 1024 / 1024
        if size_mb > settings.MAX_IMAGE_SIZE_MB:
            raise ValueError(
                f"Image too large: {size_mb:.2f}MB > {settings.MAX_IMAGE_SIZE_MB}MB"
            )
    
    def _load_image(self, path: Path, preprocess: bool) -> Image.Image:
        if preprocess and self.preprocessor:
            return self.preprocessor.preprocess(path)
        return Image.open(path)
    
    def _extract_plain_text(self, image: Image.Image, config: str) -> Dict:
        text = pytesseract.image_to_string(image, config=config).strip()
        
        data = pytesseract.image_to_data(
            image, config=config, output_type=pytesseract.Output.DICT
        )
        confidences = [
            float(c) for i, c in enumerate(data["conf"])
            if c != "-1" and data["text"][i].strip()
        ]
        avg_conf = float(np.mean(confidences)) if confidences else 0.0
        
        return {
            "text": text,
            "confidence": avg_conf,
            "blocks_count": len([t for t in data["text"] if t.strip()]),
        }
    
    def _extract_with_words(self, image: Image.Image, config: str) -> Dict:

        data = pytesseract.image_to_data(
            image, config=config, output_type=pytesseract.Output.DICT
        )
        
        words: List[WordResult] = []
        valid_confs = []
        
        for i in range(len(data["text"])):
            text = data["text"][i].strip()
            conf = float(data["conf"][i])
            
            if text and conf != -1:
                if conf >= self.min_confidence:
                    valid_confs.append(conf)
                    words.append(WordResult(
                        text=text,
                        confidence=conf,
                        bbox={
                            "x": int(data["left"][i]),
                            "y": int(data["top"][i]),
                            "w": int(data["width"][i]),
                            "h": int(data["height"][i]),
                        },
                        line_num=int(data["line_num"][i]),
                        word_num=int(data["word_num"][i]),
                        page_num=int(data.get("page_num", [0]*len(data["text"]))[i]),
                    ))
        
        avg_conf = float(np.mean(valid_confs)) if valid_confs else 0.0
        full_text = " ".join(w.text for w in words)
        
        return {
            "text": full_text,
            "confidence": avg_conf,
            "words": [asdict(w) for w in words],
            "blocks_count": len(words),
        }
    
    def _hybrid_fallback(self, result: Dict, image_path: Path, lang: str) -> Dict:

        logger.warning(
            "Low confidence detected, hybrid fallback triggered",
            confidence=result["confidence"],
            threshold=self.hybrid_threshold,
            image=str(image_path)
        )
        
        result["hybrid_applied"] = True
        result["hybrid_reason"] = f"confidence {result['confidence']:.1f} < {self.hybrid_threshold}"
        
        return result
    
    @staticmethod
    def _detect_language(text: str) -> Optional[str]:
        if not text:
            return None
        
        cyrillic = sum(1 for c in text if '\u0400' <= c <= '\u04FF')
        latin = sum(1 for c in text if c.isascii() and c.isalpha())
        total = cyrillic + latin
        
        if total == 0:
            return None
        
        ratio = cyrillic / total
        if ratio > 0.7:
            return "rus"
        elif ratio < 0.3:
            return "eng"
        return "mixed"
    
    def batch_extract(
        self,
        image_paths: List[Path],
        **kwargs
    ) -> List[Dict]:
        results = []
        for path in image_paths:
            try:
                result = self.extract_text(path, **kwargs)
                result["status"] = "success"
                result["source"] = str(path)
            except Exception as e:
                logger.error("Batch OCR failed", path=str(path), error=str(e))
                result = {
                    "status": "error",
                    "source": str(path),
                    "error": str(e),
                    "text": "",
                    "confidence": 0.0,
                }
            results.append(result)
        return results


ocr_engine = OCREngine()