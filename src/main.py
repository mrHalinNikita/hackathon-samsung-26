import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.core import setup_logger, get_logger

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

    logger.debug(
        "Configuration loaded",
        postgres_host=settings.POSTGRES_HOST,
        kafka_bootstrap=settings.kafka_bootstrap_servers,
    )

    logger.info("The application is ready to work!", message="Waiting for tasks...")

    try:
        input("Press Enter to stop the application....\n")
    except KeyboardInterrupt:
        logger.info("Interrupt signal received (Ctrl+C)")

    logger.info("Stopping the application")

    return 0


if __name__ == "__main__":
    sys.exit(main())
