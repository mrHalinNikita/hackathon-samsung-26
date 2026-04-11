import time
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import structlog

from src.services.ocr.logger import setup_logger, get_logger
from src.services.ocr.config import settings
from src.services.ocr.schemas import OCRRequest, OCRResponse, HealthResponse
from src.services.ocr.tasks import process_image_task
from src.services.ocr.ocr_engine import ocr_engine

setup_logger()
logger = get_logger("ocr_api")

app = FastAPI(
    title="PD Scanner OCR Service",
    description="Microservice for text recognition in images",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
)


@app.on_event("startup")
async def startup_event():
    logger.info("OCR Service starting", version="0.1.0")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("OCR Service shutting down")


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    import pytesseract
    
    try:
        version = pytesseract.get_tesseract_version()
        langs = pytesseract.get_languages(config=settings.TESSERACT_PATH)
        
        return HealthResponse(
            status="healthy",
            tesseract_version=str(version).strip(),
            languages_available=langs or [],
        )
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        raise HTTPException(status_code=503, detail="OCR service unhealthy")


@app.post("/api/v1/ocr/extract", response_model=OCRResponse, tags=["OCR"])
async def extract_text(request: OCRRequest):

    start_time = time.time()
    
    file_path = Path(request.file_path)
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        result = ocr_engine.extract_text(
            image_path=file_path,
            language=request.language,
            preprocess=request.preprocess,
        )
        
        processing_time = (time.time() - start_time) * 1000
        
        return OCRResponse(
            text=result["text"],
            confidence=result["confidence"],
            language_detected=result["language_detected"],
            processing_time_ms=round(processing_time, 2),
            metadata=result["metadata"],
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("OCR extraction failed", path=str(file_path), error=str(e))
        raise HTTPException(status_code=500, detail="OCR processing failed")


@app.post("/api/v1/ocr/extract/async", tags=["OCR"])
async def extract_text_async(request: OCRRequest, background_tasks: BackgroundTasks):

    file_path = Path(request.file_path)
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        task = process_image_task.delay(
            file_path=str(file_path),
            language=request.language,
            preprocess=request.preprocess,
        )
        
        return {"task_id": task.id, "status": "queued"}
        
    except Exception as e:
        logger.error("Failed to queue OCR task", path=str(file_path), error=str(e))
        raise HTTPException(status_code=500, detail="Failed to queue task")


@app.get("/api/v1/ocr/task/{task_id}", tags=["OCR"])
async def get_task_result(task_id: str):

    from celery.result import AsyncResult
    
    task_result = AsyncResult(task_id, app=process_image_task.app)
    
    if task_result.state == "PENDING":
        return {"task_id": task_id, "status": "pending"}
    elif task_result.state == "STARTED":
        return {"task_id": task_id, "status": "processing"}
    elif task_result.state == "SUCCESS":
        return {"task_id": task_id, "status": "completed", "result": task_result.result}
    elif task_result.state == "FAILURE":
        return {"task_id": task_id, "status": "failed", "error": str(task_result.result)}
    else:
        return {"task_id": task_id, "status": task_result.state}