import sys
import asyncio
from pathlib import Path
import time
import signal

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.core import setup_logger, get_logger
from src.scanner import walk_directory
from src.services import start_background_scanner
from src.consumers import RawFilesConsumer
from src.utils.csv_report import save_csv_report
from src.utils.json_report import save_json_report
from src.spark.job import run_spark_processing
from src.infrastructure import (
    init_database,
    check_database_connection,
    init_redis,
    check_redis_connection,
    check_and_mark_processed,
    init_kafka_producer,
    ensure_topics_exist,
    init_spark_session,
    check_spark_connection,
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
    
    # SPARK
    try:
        spark = init_spark_session(
            app_name=settings.APP_NAME,
            master="local[2]",  # master=f"spark://{settings.SPARK_MASTER_HOST}:7077"
        )
        check_spark_connection(spark)
        logger.debug("Spark session init")
    except Exception as e:
        logger.error("Critical error connecting to Spark", error=str(e), error_type=type(e).__name__,)
        return 1

    # SPARK JOB
    try:
        logger.info("Collecting files for Spark processing...")
        
        files_to_process = []
        results = []
        for file_info in walk_directory(
            root_path=settings.SCAN_ROOT_PATH,
            calculate_hash=True
        ):
            if check_and_mark_processed(redis_client, file_info.file_hash):
                continue
            files_to_process.append(str(file_info.path))

        if not files_to_process:
            logger.info("No new files to process.")
        else:
            logger.info(f"Found {len(files_to_process)} files. Sending to Spark...")
            
            results = run_spark_processing(spark, files_to_process)

    except Exception as e:
        logger.error("Error in Spark processing", error=str(e))

    save_csv_report(results, settings.REPORT_OUTPUT_PATH, findings_only=settings.REPORT_FINDINGS_ONLY)
    if settings.REPORT_JSON_OUTPUT_PATH:
        save_json_report(results, settings.REPORT_JSON_OUTPUT_PATH, findings_only=settings.REPORT_FINDINGS_ONLY)

    logger.info("The application is ready to work!", message="Waiting for tasks...")

    '''try:
        input("Press Enter to stop the application....\n")
    except KeyboardInterrupt:
        logger.info("Interrupt signal received (Ctrl+C)")'''
    

    def _shutdown_handler(signum, frame):
        logger.info("Received shutdown signal, exiting gracefully...")
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown_handler)
    signal.signal(signal.SIGINT, _shutdown_handler)

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        sys.exit(0)

    logger.info("Stopping application, closing connections...")
    if spark:
        spark.stop()
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
