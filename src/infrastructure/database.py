from sqlalchemy import create_engine, text, event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool
import structlog

from src.config import settings

logger = structlog.get_logger("database")


def _on_connect(dbapi_conn, connection_record) -> None:
    with dbapi_conn.cursor() as cur:
        cur.execute("SET statement_timeout TO 30000")
        cur.execute("SET lock_timeout TO 10000")


def init_database(database_url: str, pool_size: int = 5, max_overflow: int = 10, pool_timeout: int = 30, pool_recycle: int = 3600,) -> Engine:

    logger.debug(
        "Creating an engine for PostgreSQL",
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        database=settings.POSTGRES_DB,
        pool_size=pool_size,
    )
    
    engine = create_engine(
        database_url,
        poolclass=QueuePool,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_recycle=pool_recycle,
        pool_pre_ping=True,
        echo=settings.APP_ENV == "dev",
    )
    
    event.listen(engine, "connect", _on_connect)
    
    return engine


def check_database_connection(engine: Engine) -> bool:

    logger.debug("Checking the connection to PostgreSQL")
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            pg_version = result.scalar()
            logger.info("Connection to PostgreSQL established", version=pg_version if pg_version else "unknown",)
            return True
    except Exception as e:
        logger.error("Failed to connect to PostgreSQL", error=str(e), error_type=type(e).__name__,)
        raise