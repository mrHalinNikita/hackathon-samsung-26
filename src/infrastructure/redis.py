import redis
from redis.asyncio import Redis as AsyncRedis
import structlog

from src.config import settings

logger = structlog.get_logger("redis")


def init_redis(
    host: str,
    port: int,
    password: str,
    db: int,
    decode_responses: bool = True,
    socket_timeout: float = 5.0,
    socket_connect_timeout: float = 5.0,
) -> redis.Redis:

    logger.debug(
        "Create Redis client",
        host=host,
        port=port,
        db=db,
    )
    
    client = redis.Redis(
        host=host,
        port=port,
        password=password,
        db=db,
        decode_responses=decode_responses,
        socket_timeout=socket_timeout,
        socket_connect_timeout=socket_connect_timeout,
        health_check_interval=30,
    )
    
    return client


def init_redis_async(
    host: str,
    port: int,
    password: str,
    db: int,
    decode_responses: bool = True,
) -> AsyncRedis:

    logger.debug(
        "Create async Redis client",
        host=host,
        port=port,
        db=db,
    )
    
    return AsyncRedis(
        host=host,
        port=port,
        password=password,
        db=db,
        decode_responses=decode_responses,
    )


def check_redis_connection(client: redis.Redis) -> bool:

    logger.debug("Checking the connection to Redis")
    
    try:
        pong = client.ping()
        if pong:
            logger.info("Connection to Redis established")
            return True
        else:
            raise ConnectionError("Redis ping returned False")
    except Exception as e:
        logger.error("Failed to connect to Redis", error=str(e), error_type=type(e).__name__,)
        raise