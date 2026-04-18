import time
import shutil
import tempfile
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, status
from fastapi.responses import JSONResponse
import structlog
import pytesseract

from src.services.ocr.logger import setup_logger, get_logger
from src.services.ocr.config import settings
from src.services.ocr.schemas import OCRResponse, HealthResponse, TaskStatusResponse, OCRMetadata
from src.services.ocr.tasks import process_image_task, celery_app
from src.services.ocr.ocr_engine import ocr_engine

setup_logger()
logger = get_logger("ocr_api")


@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info(
        "OCR Service starting",
        version="0.1.0",
        tesseract_path=settings.TESSERACT_PATH or "auto-detect",
        preprocess_enabled=settings.PREPROCESS_ENABLED,
        hybrid_enabled=settings.HYBRID_ENABLED,
    )
    
    try:
        version = pytesseract.get_tesseract_version()
        langs = pytesseract.get_languages()
        logger.info(
            "Tesseract available",
            version=str(version).strip(),
            languages=langs or [],
        )
    except pytesseract.TesseractNotFoundError as e:
        logger.error("Tesseract binary not found", error=str(e))
    except Exception as e:
        logger.error("Tesseract initialization warning", error=str(e))
    
    yield
    
    logger.info("OCR Service shutting down")


app = FastAPI(
    title="PD Scanner OCR Service",
    description="Microservice for text recognition in images with Tesseract OCR",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
    lifespan=lifespan,
)


def _normalize_language(language: Optional[str], default: str) -> str:

    if not language or not language.strip():
        return default

    return language.replace(",", "+").replace(" ", "+").strip()


def _validate_and_save_upload(
    file: UploadFile,
    max_size_mb: float,
    allowed_extensions: Optional[set[str]] = None,
) -> Path:

    if allowed_extensions is None:
        allowed_extensions = {".jpg", ".jpeg", ".png", ".tiff", ".bmp", ".gif"}
    
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is missing")
    
    file_suffix = Path(file.filename).suffix.lower()
    if file_suffix not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: '{file_suffix}'. Allowed: {', '.join(sorted(allowed_extensions))}"
        )
    
    max_size_bytes = max_size_mb * 1024 * 1024
    content = file.file.read()
    
    if len(content) > max_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File too large: {len(content) / 1024 / 1024:.2f}MB > {max_size_mb}MB"
        )
    
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="File is empty")
    
    temp_dir = Path(tempfile.gettempdir()) / "ocr_uploads"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    with tempfile.NamedTemporaryFile(dir=temp_dir, delete=False, suffix=file_suffix) as tmp:
        tmp.write(content)
        temp_path = Path(tmp.name)
    
    logger.debug("File validated and saved", filename=file.filename, temp_path=str(temp_path), size_kb=len(content)/1024)
    return temp_path


def _cleanup_temp_file(temp_path: Optional[str | Path]) -> None:
    if temp_path:
        try:
            path = Path(temp_path)
            if path.exists():
                path.unlink()
                logger.debug("Temp file cleaned", path=str(path))
        except OSError as e:
            logger.warning("Failed to cleanup temp file", path=str(temp_path), error=str(e))
        except Exception as e:
            logger.error("Unexpected error during cleanup", path=str(temp_path), error=str(e))


@app.get("/health", response_model=HealthResponse, tags=["Health"], status_code=status.HTTP_200_OK)
async def health_check():

    try:
        version = pytesseract.get_tesseract_version()
        langs = pytesseract.get_languages()
        
        return HealthResponse(
            status="healthy",
            tesseract_version=str(version).strip(),
            languages_available=langs or [],
            preprocessing_enabled=settings.PREPROCESS_ENABLED,
            hybrid_enabled=settings.HYBRID_ENABLED,
        )
        
    except pytesseract.TesseractNotFoundError as e:
        logger.error("Tesseract binary not found", error=str(e))
        raise HTTPException(
            status_code=503,
            detail="Tesseract OCR engine not installed or not found in PATH"
        )
        
    except Exception as e:
        logger.error("Health check failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=503,
            detail=f"OCR service unhealthy: {type(e).__name__}"
        )


@app.post(
    "/api/v1/ocr/extract",
    response_model=OCRResponse,
    tags=["OCR"],
    status_code=status.HTTP_200_OK,
    summary="Extract text from image (synchronous)",
)
async def extract_text(
    file: UploadFile = File(..., description="Image file for OCR processing"),
    language: Optional[str] = Form(default=None, description="Language code(s), e.g., 'rus+eng'"),
    preprocess: Optional[bool] = Form(default=None, description="Apply image preprocessing pipeline"),
    psm: Optional[int] = Form(default=None, ge=0, le=14, description="Tesseract PSM mode (0-14)"),
    oem: Optional[int] = Form(default=None, ge=0, le=3, description="Tesseract OEM mode (0-3)"),
    return_words: bool = Form(default=False, description="Return word-level data with coordinates"),
):
    start_time = time.perf_counter()
    temp_path: Optional[Path] = None
    
    try:
        temp_path = _validate_and_save_upload(file, settings.MAX_IMAGE_SIZE_MB)
        
        normalized_lang = _normalize_language(language, settings.TESSERACT_LANGS)
        
        result = ocr_engine.extract_text(
            image_path=temp_path,
            language=normalized_lang,
            preprocess=preprocess,
            psm=psm,
            oem=oem,
            return_words=return_words,
        )
        
        processing_time_ms = (time.perf_counter() - start_time) * 1000
        
        logger.info(
            "OCR completed successfully",
            filename=file.filename,
            processing_time_ms=round(processing_time_ms, 2),
            confidence=result["confidence"],
            blocks_found=result["metadata"]["blocks_found"],
            words_found=result["metadata"]["words_found"],
            lang_used=normalized_lang,
            preprocessed=result["metadata"]["preprocessed"],
        )
        
        response_data = {
            "text": result["text"],
            "confidence": result["confidence"],
            "language_detected": result["language_detected"],
            "processing_time_ms": round(processing_time_ms, 2),
            "metadata": result["metadata"],
        }
        
        if return_words and "words" in result:
            response_data["words"] = result["words"]
        
        return OCRResponse(**response_data)
        
    except HTTPException:
        raise
        
    except ValueError as e:
        logger.warning("OCR validation error", filename=file.filename, error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
        
    except pytesseract.TesseractError as e:
        logger.error(
            "Tesseract processing error",
            filename=file.filename,
            error=str(e),
            lang=_normalize_language(language, settings.TESSERACT_LANGS),
        )
        raise HTTPException(
            status_code=422,
            detail=f"Tesseract OCR error: {str(e)}"
        )
        
    except Exception as e:
        logger.error(
            "OCR extraction failed",
            filename=file.filename,
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error during OCR processing"
        )
        
    finally:
        _cleanup_temp_file(temp_path)


@app.post(
    "/api/v1/ocr/extract/async",
    tags=["OCR"],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Extract text from image (asynchronous)",
)
async def extract_text_async(
    file: UploadFile = File(..., description="Image file for async OCR processing"),
    language: Optional[str] = Form(default=None, description="Language code(s), e.g., 'rus+eng'"),
    preprocess: Optional[bool] = Form(default=None, description="Apply image preprocessing"),
    psm: Optional[int] = Form(default=None, ge=0, le=14, description="Tesseract PSM mode"),
    oem: Optional[int] = Form(default=None, ge=0, le=3, description="Tesseract OEM mode"),
    return_words: bool = Form(default=False, description="Return word-level data"),
):
    temp_path: Optional[Path] = None
    
    try:
        temp_path = _validate_and_save_upload(file, settings.MAX_IMAGE_SIZE_MB)
        
        normalized_lang = _normalize_language(language, settings.TESSERACT_LANGS)
        
        task = process_image_task.delay(
            file_path=str(temp_path),
            language=normalized_lang,
            preprocess=preprocess,
            psm=psm,
            oem=oem,
            return_words=return_words,
        )
        
        logger.info(
            "OCR task queued successfully",
            task_id=task.id,
            filename=file.filename,
            lang=normalized_lang,
        )
        
        return {
            "task_id": task.id,
            "status": "queued",
            "filename": file.filename,
            "message": "Task added to processing queue",
            "status_endpoint": f"/api/v1/ocr/task/{task.id}",
        }
        
    except HTTPException:
        _cleanup_temp_file(temp_path)
        raise
        
    except Exception as e:
        logger.error(
            "Failed to queue OCR task",
            filename=file.filename,
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )

        _cleanup_temp_file(temp_path)
        raise HTTPException(
            status_code=500,
            detail="Failed to queue task for processing"
        )


@app.get(
    "/api/v1/ocr/task/{task_id}",
    response_model=TaskStatusResponse,
    tags=["OCR"],
    summary="Get async task result",
)
async def get_task_result(task_id: str):
    from celery.result import AsyncResult
    
    task_result = AsyncResult(task_id, app=celery_app)
    
    if task_result.state == "PENDING":
        return TaskStatusResponse(
            task_id=task_id,
            status="pending",
            message="Task is waiting in queue"
        )
    
    elif task_result.state == "STARTED":
        return TaskStatusResponse(
            task_id=task_id,
            status="processing",
            message="Task is being processed by worker"
        )
    
    elif task_result.state == "SUCCESS":
        result_data = task_result.result
        
        if isinstance(result_data, dict) and result_data.get("temp_path"):
            _cleanup_temp_file(result_data["temp_path"])
        
        if isinstance(result_data, dict) and "metadata" in result_data:
            if isinstance(result_data["metadata"], dict):
                result_data["metadata"] = OCRMetadata(**result_data["metadata"])
        
        return TaskStatusResponse(
            task_id=task_id,
            status="completed",
            result=result_data,
            message="OCR processing completed successfully"
        )
    
    elif task_result.state == "FAILURE":
        error_msg = str(task_result.result) if task_result.result else "Unknown error"
        logger.error(
            "Celery task failed",
            task_id=task_id,
            error=error_msg,
            traceback=getattr(task_result, "traceback", None),
        )
        return TaskStatusResponse(
            task_id=task_id,
            status="failed",
            error=error_msg,
            message="Task processing failed"
        )
    
    elif task_result.state == "RETRY":
        return TaskStatusResponse(
            task_id=task_id,
            status="retrying",
            message="Task retry in progress after error"
        )
    
    else:
        logger.warning(
            "Unknown Celery task state",
            task_id=task_id,
            state=task_result.state,
            info=str(task_result.info) if hasattr(task_result, "info") else None,
        )
        return TaskStatusResponse(
            task_id=task_id,
            status="unknown",
            message=f"Unexpected task state: {task_result.state}"
        )

@app.on_event("shutdown")
async def shutdown_cleanup():

    temp_dir = Path(tempfile.gettempdir()) / "ocr_uploads"
    if temp_dir.exists():
        import glob
        orphaned = 0
        for f in glob.glob(str(temp_dir / "*.tmp")) + glob.glob(str(temp_dir / "*.jpg")) + glob.glob(str(temp_dir / "*.png")):
            try:
                Path(f).unlink()
                orphaned += 1
            except OSError:
                pass
        if orphaned > 0:
            logger.info("Cleaned up orphaned temp files", count=orphaned, dir=str(temp_dir))


@app.get("/", tags=["Root"], include_in_schema=False)
async def root():

    return {
        "service": "PD Scanner OCR Service",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "sync_ocr": "POST /api/v1/ocr/extract",
            "async_ocr": "POST /api/v1/ocr/extract/async",
            "task_status": "GET /api/v1/ocr/task/{task_id}",
        },
    }