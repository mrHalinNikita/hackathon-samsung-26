import time
from pathlib import Path
import tempfile
import shutil
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.responses import JSONResponse
import structlog

from src.services.ocr.logger import setup_logger, get_logger
from src.services.ocr.config import settings
from src.services.ocr.schemas import OCRResponse, HealthResponse
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
async def extract_text(
    file: UploadFile = File(..., description="Image file for OCR"),
    language: str = Form(default="rus+eng", description="Language code(s) for Tesseract"),
    preprocess: bool = Form(default=True, description="Apply image preprocessing"),
):
    start_time = time.time()
    
    allowed_extensions = {".jpg", ".jpeg", ".png", ".tiff", ".bmp", ".gif"}
    file_suffix = Path(file.filename).suffix.lower()
    
    if file_suffix not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file_suffix}. Allowed: {allowed_extensions}"
        )
    
    max_size = settings.MAX_IMAGE_SIZE_MB * 1024 * 1024
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large: {len(content) / 1024 / 1024:.2f}MB > {settings.MAX_IMAGE_SIZE_MB}MB"
        )
    
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_suffix) as tmp:
            tmp.write(content)
            temp_path = Path(tmp.name)
        
        result = ocr_engine.extract_text(
            image_path=temp_path,
            language=language if language != "rus+eng" else None,
            preprocess=preprocess,
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
        logger.error("OCR extraction failed", filename=file.filename, error=str(e))
        raise HTTPException(status_code=500, detail="OCR processing failed")
    finally:
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


@app.post("/api/v1/ocr/extract/async", tags=["OCR"])
async def extract_text_async(file: UploadFile = File(...), language: str = Form(default="rus+eng"), preprocess: bool = Form(default=True),):

    allowed_extensions = {".jpg", ".jpeg", ".png", ".tiff", ".bmp", ".gif"}
    file_suffix = Path(file.filename).suffix.lower()
    
    if file_suffix not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file_suffix}"
        )
    
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            temp_path = Path(tmp.name)
        
        task = process_image_task.delay(
            file_path=str(temp_path),
            language=language if language != "rus+eng" else None,
            preprocess=preprocess,
        )
        
        return {"task_id": task.id, "status": "queued", "filename": file.filename}
        
    except Exception as e:
        logger.error("Failed to queue OCR task", filename=file.filename, error=str(e))

        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)
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
        _cleanup_temp_file(task_result.result.get("temp_path"))
        return {"task_id": task_id, "status": "completed", "result": task_result.result}
    elif task_result.state == "FAILURE":
        return {"task_id": task_id, "status": "failed", "error": str(task_result.result)}
    else:
        return {"task_id": task_id, "status": task_result.state}


def _cleanup_temp_file(temp_path: str | None) -> None:

    if temp_path:
        try:
            Path(temp_path).unlink(missing_ok=True)
        except OSError:
            pass