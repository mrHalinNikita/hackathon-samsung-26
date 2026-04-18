from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Literal, Optional


class OCRSettings(BaseSettings):
    
    model_config = SettingsConfigDict(
        env_prefix="OCR_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # SERVER
    HOST: str
    PORT: int
    LOG_LEVEL: str
    
    # REDIS (Celery)
    REDIS_URL: str
    
    # TESSERACT
    TESSERACT_LANGS: str = "rus+eng"
    TESSERACT_PATH: str | None = None
    TESSERACT_DATA_PATH: str | None = None
    
    # PROCESSING
    MAX_IMAGE_SIZE_MB: int = 20
    MIN_CONFIDENCE: int = 50
    
    # PREPROCESSING PIPELINE
    PREPROCESS_ENABLED: bool = True
    PREPROCESS_DENOISE: bool = True
    PREPROCESS_ADAPTIVE_THRESH: bool = True
    PREPROCESS_DESKEW: bool = True
    PREPROCESS_SCALE_DPI: bool = True
    PREPROCESS_TARGET_DPI: float = 300.0
    
    # OCR MODES
    DEFAULT_PSM: int = 3
    DEFAULT_OEM: int = 3
    WORD_LEVEL_EXTRACTION: bool = False
    
    # HYBRID MODE
    HYBRID_ENABLED: bool = False
    HYBRID_CONFIDENCE_THRESHOLD: float = 60.0
    
    # CACHE & CELERY
    CACHE_TTL_SECONDS: int = 3600
    WORKER_CONCURRENCY: int = 4
    
    @property
    def celery_broker_url(self) -> str:
        return self.REDIS_URL
    
    @property
    def celery_result_backend(self) -> str:
        return self.REDIS_URL


settings = OCRSettings()