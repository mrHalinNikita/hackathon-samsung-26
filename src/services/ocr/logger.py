import sys
import structlog
from structlog.typing import WrappedLogger, EventDict
from src.services.ocr.config import settings


def _drop_color_meta_key(_: WrappedLogger, __: str, event_dict: EventDict) -> EventDict:
    event_dict.pop("_colorful", None)
    return event_dict


def setup_logger() -> None:
    
    if settings.LOG_LEVEL == "DEBUG":
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.dict_tracebacks,
            _drop_color_meta_key,
            structlog.processors.JSONRenderer(),
        ]
    
    structlog.configure(
        processors=processors,
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
        wrapper_class=structlog.make_filtering_bound_logger(settings.LOG_LEVEL),
    )


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    return structlog.get_logger(name)