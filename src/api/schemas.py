from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, Any


class ServiceStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    ERROR = "error"
    UNKNOWN = "unknown"


class ServiceHealth(BaseModel):
    name: str
    status: ServiceStatus
    message: str
    response_time_ms: Optional[float] = None
    details: Optional[dict[str, Any]] = None


class HealthCheckResponse(BaseModel):
    status: ServiceStatus = Field(...)
    timestamp: str = Field(...)
    services: list[ServiceHealth] = Field(...)