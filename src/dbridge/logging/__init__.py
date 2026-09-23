from logging import getLogger, Logger
import logging
import os

APP_NAME = "dbridge"
DEFAULT_LOGGING_LEVEL = os.getenv("dbridge_logging_level", "INFO")


def get_logger(name: str = APP_NAME, level_name: str = "") -> Logger:
    logger = getLogger(name)
    level = getattr(logging, level_name, DEFAULT_LOGGING_LEVEL)
    logger.setLevel(level)
    # Reuse direct handlers, including those supplied by an embedding application.
    # StreamHandler defaults to stderr; stdout is reserved for protocol frames.
    if not logger.handlers:
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ))
        logger.addHandler(console)
    return logger
