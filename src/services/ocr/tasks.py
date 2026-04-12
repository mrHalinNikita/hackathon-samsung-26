from celery import Celery
from pathlib import Path
import time

from src.services.ocr.config import settings
from src.services.ocr.ocr_engine import ocr_engine
from src.services.ocr.schemas import OCRResponse
from src.services.ocr.logger import get_logger

logger = get_logger("ocr_tasks")

celery_app = Celery(
    "ocr_service",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,
    worker_prefetch_multiplier=1,
)


@celery_app.task(bind=True, name="ocr.process_image")
def process_image_task(self, file_path: str, language: str | None = None, preprocess: bool = True,) -> dict:

    start_time = time.time()
    
    logger.info("Starting OCR task", task_id=self.request.id, file_path=file_path,language=language,)
    
    try:
        result = ocr_engine.extract_text(
            image_path=Path(file_path),
            language=language,
            preprocess=preprocess,
        )
        
        processing_time = (time.time() - start_time) * 1000
        
        logger.info("OCR task completed", task_id=self.request.id, confidence=result["confidence"], processing_time_ms=processing_time,)
        
        return {**result, "processing_time_ms": round(processing_time, 2), "task_id": self.request.id,}
        
    except Exception as e:
        logger.error("OCR task failed", task_id=self.request.id, error=str(e), error_type=type(e).__name__,)
        raise