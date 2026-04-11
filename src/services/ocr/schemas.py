from pydantic import BaseModel, Field, field_validator
from pathlib import Path
from typing import Optional


class OCRRequest(BaseModel):
    
    file_path: str = Field(..., min_length=1)
    language: Optional[str] = Field(default=None)
    preprocess: bool = Field(default=True)
    
    @field_validator("file_path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        path = Path(v)
        if not path.suffix.lower() in [".jpg", ".jpeg", ".png", ".tiff", ".bmp", ".gif"]:
            raise ValueError("Unsupported image format")
        return v


class OCRResponse(BaseModel):
    
    text: str
    confidence: float = Field(..., ge=0, le=100)
    language_detected: Optional[str] = None
    processing_time_ms: float
    metadata: dict = Field(default_factory=dict)


class HealthResponse(BaseModel):
    
    status: str
    tesseract_version: Optional[str] = None
    languages_available: list[str] = Field(default_factory=list)