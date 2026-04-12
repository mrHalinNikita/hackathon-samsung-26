import redis
import structlog
from src.config import settings

logger = structlog.get_logger("redis_dedup")

DEDUP_PREFIX = "pd_scanner:dedup:"
DEDUP_TTL_SECONDS = 86400 * 7  # 7 days


def check_and_mark_processed(client: redis.Redis, file_hash: str) -> bool:

    if not file_hash:
        return False

    key = f"{DEDUP_PREFIX}{file_hash}"
    was_set = client.set(key, "1", nx=True, ex=DEDUP_TTL_SECONDS)

    if was_set:
        logger.debug("New file marked for processing", hash=file_hash)
        return False
    else:
        logger.debug("The file has already been processed, skipping", hash=file_hash)
        return True