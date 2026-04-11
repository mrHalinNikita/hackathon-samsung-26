from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


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
    TESSERACT_LANGS: str
    TESSERACT_PATH: str | None = None
    
    # PROCESSING
    MAX_IMAGE_SIZE_MB: int
    MIN_CONFIDENCE: int
    CACHE_TTL_SECONDS: int
    
    # CELERY
    WORKER_CONCURRENCY: int
    
    @property
    def celery_broker_url(self) -> str:
        return self.REDIS_URL
    
    @property
    def celery_result_backend(self) -> str:
        return self.REDIS_URL


settings = OCRSettings()