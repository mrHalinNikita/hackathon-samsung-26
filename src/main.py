import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.core import setup_logger, get_logger
from src.infrastructure import (
    init_database,
    check_database_connection,
    init_redis,
    check_redis_connection,
    init_kafka_producer,
    ensure_topics_exist,
)

logger = get_logger("main")


def main() -> int:

    setup_logger()

    logger.info(
        "Start APP",
        app_name=settings.APP_NAME,
        env=settings.APP_ENV,
        log_level=settings.LOG_LEVEL,
        scan_root=settings.SCAN_ROOT_PATH,
    )

    # POSTGRES
    try:
        db_engine = init_database(settings.database_url)
        check_database_connection(db_engine)
        logger.debug("Database engine init")
    except Exception as e:
        logger.error("Error connecting to the database", error=str(e), error_type=type(e).__name__,)
        return 1
    
    # REDIS
    try:
        redis_client = init_redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,
            db=settings.REDIS_DB,
        )
        check_redis_connection(redis_client)
        logger.debug("Redis client init")
    except Exception as e:
        logger.error("Error connecting to the Redis", error=str(e), error_type=type(e).__name__,)
        return 1
    
    # KAFKA
    try:
        kafka_producer = init_kafka_producer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
        )
        
        ensure_topics_exist(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            topics=[
                settings.KAFKA_TOPIC_RAW_FILES,
                settings.KAFKA_TOPIC_EXTRACTED_TEXT,
                settings.KAFKA_TOPIC_RESULTS,
            ],
        )
        logger.debug("Kafka producer init")
    except Exception as e:
        logger.error("Critical error connecting to Kafka", error=str(e), error_type=type(e).__name__,)
        return 1

    logger.info("The application is ready to work!", message="Waiting for tasks...")

    try:
        input("Press Enter to stop the application....\n")
    except KeyboardInterrupt:
        logger.info("Interrupt signal received (Ctrl+C)")

    logger.info("Stopping application, closing connections...")
    if kafka_producer:
        kafka_producer.flush(timeout=10)
        kafka_producer.close()
    if redis_client:
        redis_client.close()
    if db_engine:
        db_engine.dispose()

    logger.info("Stopping the application")

    return 0


if __name__ == "__main__":
    sys.exit(main())
