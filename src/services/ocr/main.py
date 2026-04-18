import time
import shutil
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form, status
from fastapi.responses import JSONResponse
import structlog
import pytesseract

from src.services.ocr.logger import setup_logger, get_logger
from src.services.ocr.config import settings
from src.services.ocr.schemas import OCRResponse, HealthResponse, TaskStatusResponse
from src.services.ocr.tasks import process_image_task
from src.services.ocr.ocr_engine import ocr_engine

setup_logger()
logger = get_logger("ocr_api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("OCR Service starting", version="0.1.0", tesseract_path=settings.TESSERACT_PATH)
    try:
        version = pytesseract.get_tesseract_version()
        logger.info("Tesseract available", version=str(version).strip())
    except Exception as e:
        logger.error("Tesseract not found", error=str(e))
    yield
    logger.info("OCR Service shutting down")


app = FastAPI(
    title="PD Scanner OCR Service",
    description="Microservice for text recognition in images",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
    lifespan=lifespan,
)


def _validate_file(file: UploadFile, max_size_mb: float) -> tuple[bytes, Path]:
    allowed_extensions = {".jpg", ".jpeg", ".png", ".tiff", ".bmp", ".gif"}
    
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is missing")
    
    file_suffix = Path(file.filename).suffix.lower()
    if file_suffix not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file_suffix}. Allowed: {', '.join(allowed_extensions)}"
        )
    
    max_size_bytes = max_size_mb * 1024 * 1024
    content = file.file.read()
    if len(content) > max_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File too large: {len(content) / 1024 / 1024:.2f}MB > {max_size_mb}MB"
        )
    
    temp_dir = Path(settings.TEMP_DIR) if hasattr(settings, 'TEMP_DIR') else Path(tempfile.gettempdir())
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    import tempfile
    with tempfile.NamedTemporaryFile(dir=temp_dir, delete=False, suffix=file_suffix) as tmp:
        tmp.write(content)
        temp_path = Path(tmp.name)
    
    return content, temp_path


def _cleanup_temp_file(temp_path: Optional[str | Path]) -> None:
    if temp_path:
        try:
            Path(temp_path).unlink(missing_ok=True)
            logger.debug("Temp file cleaned", path=str(temp_path))
        except OSError as e:
            logger.warning("Failed to cleanup temp file", path=str(temp_path), error=str(e))


def _normalize_language(language: Optional[str], default: str) -> str:
    if not language or language.strip() == "":
        return default
    return language.replace(",", "+").replace(" ", "+").strip()


@app.get("/health", response_model=HealthResponse, tags=["Health"], status_code=status.HTTP_200_OK)
async def health_check():
    try:
        version = pytesseract.get_tesseract_version()
        langs = pytesseract.get_languages()
        
        return HealthResponse(
            status="healthy",
            tesseract_version=str(version).strip(),
            languages_available=langs or [],
        )
    except pytesseract.TesseractNotFoundError as e:
        logger.error("Tesseract binary not found", error=str(e))
        raise HTTPException(status_code=503, detail="Tesseract not installed")
    except Exception as e:
        logger.error("Health check failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=503, detail=f"OCR service unhealthy: {str(e)}")


@app.post("/api/v1/ocr/extract", response_model=OCRResponse, tags=["OCR"])
async def extract_text(
    file: UploadFile = File(..., description="Image file for OCR processing"),
    language: Optional[str] = Form(default=None, description="Language code(s), e.g., 'rus', 'eng', 'rus+eng'"),
    preprocess: bool = Form(default=True, description="Apply image preprocessing pipeline"),
    psm: Optional[int] = Form(default=None, ge=0, le=14, description="Tesseract PSM mode (0-14)"),
):

    start_time = time.perf_counter()
    
    try:
        _, temp_path = _validate_file(file, settings.MAX_IMAGE_SIZE_MB)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("File validation failed", filename=file.filename, error=str(e))
        raise HTTPException(status_code=400, detail="Invalid file upload")
    
    try:
        normalized_lang = _normalize_language(language, settings.TESSERACT_LANGS)
        
        result = ocr_engine.extract_text(
            image_path=temp_path,
            language=normalized_lang,
            preprocess=preprocess,
            psm=psm,
        )
        
        processing_time_ms = (time.perf_counter() - start_time) * 1000
        
        logger.info(
            "OCR completed",
            filename=file.filename,
            processing_time_ms=round(processing_time_ms, 2),
            confidence=result["confidence"],
            blocks_found=result["metadata"]["blocks_found"],
            lang_used=normalized_lang,
        )
        
        return OCRResponse(
            text=result["text"],
            confidence=result["confidence"],
            language_detected=result["language_detected"],
            processing_time_ms=round(processing_time_ms, 2),
            metadata=result["metadata"],
        )
        
    except ValueError as e:
        logger.warning("OCR validation error", filename=file.filename, error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except pytesseract.TesseractError as e:
        logger.error("Tesseract processing error", filename=file.filename, error=str(e))
        raise HTTPException(status_code=422, detail=f"Tesseract error: {str(e)}")
    except Exception as e:
        logger.error("OCR extraction failed", filename=file.filename, error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Internal OCR processing error")
    finally:
        _cleanup_temp_file(temp_path if 'temp_path' in locals() else None)


@app.post("/api/v1/ocr/extract/async", tags=["OCR"], status_code=status.HTTP_202_ACCEPTED)
async def extract_text_async(
    file: UploadFile = File(..., description="Image file for async OCR"),
    language: Optional[str] = Form(default=None, description="Language code(s)"),
    preprocess: bool = Form(default=True, description="Apply preprocessing"),
    psm: Optional[int] = Form(default=None, ge=0, le=14, description="PSM mode"),
):

    try:
        _, temp_path = _validate_file(file, settings.MAX_IMAGE_SIZE_MB)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Async upload validation failed", filename=file.filename, error=str(e))
        raise HTTPException(status_code=400, detail="Invalid file upload")
    
    try:
        normalized_lang = _normalize_language(language, settings.TESSERACT_LANGS)
        
        task = process_image_task.delay(
            file_path=str(temp_path),
            language=normalized_lang,
            preprocess=preprocess,
            psm=psm,
        )
        
        logger.info("OCR task queued", task_id=task.id, filename=file.filename)
        
        return {
            "task_id": task.id,
            "status": "queued",
            "filename": file.filename,
            "estimated_wait_sec": settings.CELERY_TASK_TIMEOUT if hasattr(settings, 'CELERY_TASK_TIMEOUT') else 30
        }
        
    except Exception as e:
        logger.error("Failed to queue OCR task", filename=file.filename, error=str(e), exc_info=True)
        _cleanup_temp_file(temp_path)
        raise HTTPException(status_code=500, detail="Failed to queue task for processing")


@app.get("/api/v1/ocr/task/{task_id}", response_model=TaskStatusResponse, tags=["OCR"])
async def get_task_result(task_id: str):
    from celery.result import AsyncResult
    
    task_result = AsyncResult(task_id, app=process_image_task.app)
    
    if task_result.state == "PENDING":
        return TaskStatusResponse(task_id=task_id, status="pending", message="Task waiting in queue")
    
    elif task_result.state == "STARTED":
        return TaskStatusResponse(task_id=task_id, status="processing", message="Task is being processed")
    
    elif task_result.state == "SUCCESS":
        result_data = task_result.result
        if isinstance(result_data, dict) and result_data.get("temp_path"):
            _cleanup_temp_file(result_data["temp_path"])
        
        return TaskStatusResponse(
            task_id=task_id,
            status="completed",
            result=result_data,
            message="OCR processing completed successfully"
        )
    
    elif task_result.state == "FAILURE":
        logger.error("Celery task failed", task_id=task_id, error=str(task_result.result))
        return TaskStatusResponse(
            task_id=task_id,
            status="failed",
            error=str(task_result.result) if task_result.result else "Unknown error",
            message="Task processing failed"
        )
    
    elif task_result.state == "RETRY":
        return TaskStatusResponse(task_id=task_id, status="retrying", message="Task retry in progress")
    
    else:
        logger.warning("Unknown task state", task_id=task_id, state=task_result.state)
        return TaskStatusResponse(task_id=task_id, status="unknown", message=f"Unexpected state: {task_result.state}")

@app.on_event("shutdown")
async def shutdown_cleanup():
    temp_dir = Path(settings.TEMP_DIR) if hasattr(settings, 'TEMP_DIR') else Path("/tmp")
    if temp_dir.exists():
        import glob
        for f in glob.glob(str(temp_dir / "tmp_*.tmp")):
            try:
                Path(f).unlink()
                logger.debug("Cleaned orphaned temp file", path=f)
            except OSError:
                pass