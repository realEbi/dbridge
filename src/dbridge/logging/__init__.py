from logging import getLogger, Logger
import logging
import os

_loggers = {}

APP_NAME = "dbridge"
DEFAULT_LOGGING_LEVEL = os.getenv("dbridge_logging_level", "INFO")


def get_logger(name: str = APP_NAME, level_name: str = "") -> Logger:
    if logger := _loggers.get(name):
        return logger
    logger = getLogger(name)
    level = getattr(logging, level_name, DEFAULT_LOGGING_LEVEL)
    logger.setLevel(level)
    # create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(level)

    # create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # add formatter to ch
    ch.setFormatter(formatter)

    # add ch to logger
    logger.addHandler(ch)
    return logger
