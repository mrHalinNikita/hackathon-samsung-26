from pydantic import BaseModel, Field
from typing import Optional


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