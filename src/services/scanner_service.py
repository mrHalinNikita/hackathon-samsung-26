import asyncio
import json
import redis
from confluent_kafka import Producer
from src.scanner import walk_directory
from src.config import settings
from src.infrastructure import check_and_mark_processed
import structlog

logger = structlog.get_logger("scanner_service")


def _sync_scan_and_publish(redis_client: redis.Redis, kafka_producer: Producer, topic: str, root_path: str) -> dict:
    stats = {"processed": 0, "skipped_dedup": 0, "errors": 0}

    for file_info in walk_directory(root_path, calculate_hash=True):
        try:
            if file_info.file_hash and check_and_mark_processed(redis_client, file_info.file_hash):
                stats["skipped_dedup"] += 1
                continue

            payload = json.dumps({
                "path": str(file_info.path),
                "size_bytes": file_info.size_bytes,
                "extension": file_info.extension,
                "file_hash": file_info.file_hash,
            }).encode("utf-8")

            kafka_producer.produce(
                topic,
                key=file_info.file_hash or str(file_info.path),
                value=payload
            )
            kafka_producer.poll(0)  # delivery callbacks
            stats["processed"] += 1

            if stats["processed"] % 50 == 0:
                logger.info("Scan progress", **stats)

        except Exception as e:
            logger.error("File processing error", path=str(file_info.path), error=str(e))
            stats["errors"] += 1

    remaining = kafka_producer.flush(timeout=30)
    if remaining > 0:
        logger.warning("Not all messages were delivered after scanning", remaining=remaining)

    logger.info("Scanning complete", **stats)
    return stats


async def start_background_scanner(redis_client: redis.Redis, kafka_producer: Producer, topic: str, root_path: str) -> None:
    logger.info("Initializing the scanner", root=root_path, topic=topic)
    loop = asyncio.get_event_loop()

    task = loop.run_in_executor(
        None, 
        _sync_scan_and_publish, 
        redis_client, kafka_producer, topic, root_path
    )

    task.add_done_callback(lambda t: logger.info(
        "The scanner has completed its work", 
        result=t.result() if not t.exception() else str(t.exception())
    ))
    
    await task