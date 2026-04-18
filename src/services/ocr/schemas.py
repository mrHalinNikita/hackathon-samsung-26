from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class WordData(BaseModel):
    text: str
    confidence: float = Field(..., ge=0, le=100)
    bbox: Dict[str, int] = Field(..., description="Bounding box: {x, y, width, height}")
    line_num: int
    word_num: int
    page_num: int = 0


class OCRMetadata(BaseModel):
    image_size: str
    preprocessed: bool
    psm: int
    oem: int
    language_config: str
    blocks_found: int
    words_found: int = 0
    hybrid_applied: Optional[bool] = None
    hybrid_reason: Optional[str] = None


class OCRResponse(BaseModel):
    text: str
    confidence: float = Field(..., ge=0, le=100)
    language_detected: Optional[str] = None
    processing_time_ms: float
    metadata: OCRMetadata
    words: Optional[List[WordData]] = None


class HealthResponse(BaseModel):
    status: str
    tesseract_version: Optional[str] = None
    languages_available: list[str] = Field(default_factory=list)
    preprocessing_enabled: bool = True
    hybrid_enabled: bool = False


class TaskStatusResponse(OCRResponse):
    task_id: str
    status: str = "completed"
    error: Optional[str] = None