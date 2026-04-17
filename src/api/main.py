from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.config import settings
from src.api.health import run_all_checks
from src.api.schemas import HealthCheckResponse

from src.api.health import (
    check_postgres,
    check_redis,
    check_kafka,
    check_spark_master,
    check_ocr,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(f"Health API started on port {settings.PORT}")
    yield
    # Shutdown
    print("Health API stopped")


app = FastAPI(
    title="PD Scanner Health API",
    description="Health check endpoints for infrastructure services",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Health"])
async def root_health() -> dict[str, str]:
    return {"status": "ok", "service": "health-api"}


@app.get("/api/v1/health", response_model=HealthCheckResponse, tags=["Health"])
async def health_check() -> HealthCheckResponse:
    return await run_all_checks()


@app.get("/api/v1/health/{service_name}", tags=["Health"])
async def health_check_service(service_name: str) -> dict:
    checks = {
        "postgres": check_postgres,
        "redis": check_redis,
        "kafka": check_kafka,
        "spark-master": check_spark_master,
        "ocr": check_ocr,
    }
    
    if service_name not in checks:
        return {"error": f"Unknown service: {service_name}"}, 404
    
    result = await checks[service_name]()
    return result.model_dump()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host=settings.HOST,
        port=settings.PORT,
        log_level=settings.LOG_LEVEL.lower(),
        reload=True,
    )