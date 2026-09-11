import logging
from dbridge.logging import get_logger


def test_logger_name():
    name = "test_logger_name"
    logger = get_logger(name, "INFO")
    assert logger.name == name


def test_logger_level():
    name = "test_logger_level"
    level = "INFO"
    logger = get_logger(name, level)
    assert logger.level == getattr(logging, level)


def test_logger_is_the_same_object_by_name():
    """Same name, same Logger — but via logging.getLogger, not the _loggers cache."""
    first = get_logger("test_logger_cached", "INFO")
    second = get_logger("test_logger_cached", "INFO")
    assert first is second


def test_repeated_get_logger_stacks_handlers():
    """Pins a known defect, not desired behavior.

    get_logger declares a _loggers cache but never writes to it, so the early
    return is unreachable and every call adds another StreamHandler to the same
    Logger. Because DBAdapter.__init__ calls get_logger, each Session created
    duplicates the server's log output once more. Recorded as a backlog item;
    when it is fixed this test changes to assert a single handler.
    """
    name = "test_logger_handlers"
    logger = get_logger(name, "INFO")
    before = len(logger.handlers)

    get_logger(name, "INFO")

    assert len(logger.handlers) == before + 1


def test_unknown_level_name_falls_back_to_the_default():
    """getattr(logging, level_name, DEFAULT) means a bad name is not fatal."""
    logger = get_logger("test_logger_bad_level", "NOT_A_LEVEL")
    assert logger.level == logging.INFO
