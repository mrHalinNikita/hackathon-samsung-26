import asyncio
import time
from datetime import datetime

import aiohttp
import asyncpg
import redis.asyncio as aioredis

from src.api.config import settings
from src.api.schemas import ServiceHealth, ServiceStatus, HealthCheckResponse


async def check_postgres() -> ServiceHealth:
    start = time.time()
    try:
        conn = await asyncpg.connect(
            host=settings.HEALTH_POSTGRES_HOST,
            port=settings.HEALTH_POSTGRES_PORT,
            database=settings.POSTGRES_DB,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            timeout=settings.CHECK_TIMEOUT,
        )
        await conn.fetchval("SELECT 1")
        await conn.close()
        return ServiceHealth(
            name="postgres",
            status=ServiceStatus.OK,
            message="Connection successful",
            response_time_ms=round((time.time() - start) * 1000, 2),
        )
    except Exception as e:
        return ServiceHealth(
            name="postgres",
            status=ServiceStatus.ERROR,
            message=str(e),
            response_time_ms=round((time.time() - start) * 1000, 2),
        )


async def check_redis() -> ServiceHealth:
    start = time.time()
    try:
        client = await aioredis.from_url(
            f"redis://{settings.HEALTH_REDIS_HOST}:{settings.HEALTH_REDIS_PORT}",
            password=settings.REDIS_PASSWORD,
            socket_timeout=settings.CHECK_TIMEOUT,
        )
        await client.ping()
        await client.close()
        return ServiceHealth(
            name="redis",
            status=ServiceStatus.OK,
            message="PONG received",
            response_time_ms=round((time.time() - start) * 1000, 2),
        )
    except Exception as e:
        return ServiceHealth(
            name="redis",
            status=ServiceStatus.ERROR,
            message=str(e),
            response_time_ms=round((time.time() - start) * 1000, 2),
        )


async def check_kafka() -> ServiceHealth:
    import socket
    start = time.time()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(settings.CHECK_TIMEOUT)
        result = sock.connect_ex((settings.HEALTH_KAFKA_HOST, settings.KAFKA_PORT))
        sock.close()
        
        if result == 0:
            return ServiceHealth(
                name="kafka",
                status=ServiceStatus.OK,
                message="Broker port reachable",
                response_time_ms=round((time.time() - start) * 1000, 2),
            )
        else:
            return ServiceHealth(
                name="kafka",
                status=ServiceStatus.ERROR,
                message=f"Port {settings.KAFKA_PORT} not reachable (code: {result})",
                response_time_ms=round((time.time() - start) * 1000, 2),
            )
    except Exception as e:
        return ServiceHealth(
            name="kafka",
            status=ServiceStatus.ERROR,
            message=str(e),
            response_time_ms=round((time.time() - start) * 1000, 2),
        )


async def check_spark_master() -> ServiceHealth:
    start = time.time()
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=settings.CHECK_TIMEOUT)
        ) as session:
            async with session.get(
                f"http://{settings.HEALTH_SPARK_MASTER_HOST}:8080"
            ) as resp:
                if resp.status == 200:
                    return ServiceHealth(
                        name="spark-master",
                        status=ServiceStatus.OK,
                        message="Web UI accessible",
                        response_time_ms=round((time.time() - start) * 1000, 2),
                    )
                return ServiceHealth(
                    name="spark-master",
                    status=ServiceStatus.DEGRADED,
                    message=f"HTTP {resp.status}",
                    response_time_ms=round((time.time() - start) * 1000, 2),
                )
    except Exception as e:
        return ServiceHealth(
            name="spark-master",
            status=ServiceStatus.ERROR,
            message=str(e),
            response_time_ms=round((time.time() - start) * 1000, 2),
        )


async def check_ocr() -> ServiceHealth:
    start = time.time()
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=settings.CHECK_TIMEOUT)
        ) as session:
            async with session.get(
                f"http://{settings.HEALTH_OCR_HOST}:{settings.HEALTH_OCR_PORT}/health"
            ) as resp:
                data = await resp.json() if resp.content_type == "application/json" else {}
                return ServiceHealth(
                    name="ocr",
                    status=ServiceStatus.OK if resp.status == 200 else ServiceStatus.DEGRADED,
                    message=data.get("status", "OK"),
                    response_time_ms=round((time.time() - start) * 1000, 2),
                    details=data,
                )
    except Exception as e:
        return ServiceHealth(
            name="ocr",
            status=ServiceStatus.ERROR,
            message=str(e),
            response_time_ms=round((time.time() - start) * 1000, 2),
        )


async def run_all_checks() -> HealthCheckResponse:
    tasks = [
        check_postgres(),
        check_redis(),
        check_kafka(),
        check_spark_master(),
        check_ocr(),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    services = []
    for r in results:
        if isinstance(r, Exception):
            services.append(ServiceHealth(
                name="unknown",
                status=ServiceStatus.ERROR,
                message=str(r),
            ))
        elif isinstance(r, ServiceHealth):
            services.append(r)
    
    if any(s.status == ServiceStatus.ERROR for s in services):
        overall = ServiceStatus.ERROR
    elif any(s.status == ServiceStatus.DEGRADED for s in services):
        overall = ServiceStatus.DEGRADED
    else:
        overall = ServiceStatus.OK
    
    return HealthCheckResponse(
        status=overall,
        timestamp=datetime.utcnow().isoformat(),
        services=services,
    )