import logging
import sys

import structlog


def configure_logging(log_level: str) -> None:
    timestamper = structlog.processors.TimeStamper(fmt="iso")
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        timestamper,
        structlog.processors.add_log_level,
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, log_level.upper())),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(level=log_level.upper(), format="%(message)s", stream=sys.stdout)