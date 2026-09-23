import logging

import pytest

from dbridge.adapters.sqlite import SqliteAdapter
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
    """The standard logging registry owns named logger identity."""
    first = get_logger("test_logger_cached", "INFO")
    second = get_logger("test_logger_cached", "INFO")
    assert first is second


def test_repeated_get_logger_emits_once_to_stderr(capsys):
    logger = get_logger("test_logger_handlers", "INFO")
    for _ in range(5):
        assert get_logger("test_logger_handlers", "INFO") is logger

    logger.info("one diagnostic")

    assert len(logger.handlers) == 1
    captured = capsys.readouterr()
    assert captured.err.count("one diagnostic") == 1
    assert captured.out == ""


@pytest.fixture
def isolated_server_logger():
    logger = logging.getLogger("dbridge")
    previous_handlers, previous_level = logger.handlers[:], logger.level
    logger.handlers = []
    try:
        yield logger
    finally:
        for handler in logger.handlers:
            handler.close()
        logger.handlers = previous_handlers
        logger.setLevel(previous_level)


def test_repeated_adapter_construction_emits_once(isolated_server_logger, capsys):
    adapters = [SqliteAdapter({"uri": ":memory:"}) for _ in range(5)]
    assert all(adapter.logger is isolated_server_logger for adapter in adapters)
    assert len(isolated_server_logger.handlers) == 1

    adapters[-1].logger.warning("five adapters, one diagnostic")

    captured = capsys.readouterr()
    assert captured.err.count("five adapters, one diagnostic") == 1
    assert captured.out == ""


def test_existing_handler_is_preserved():
    logger = logging.getLogger("test_logger_configured")
    handler = logging.NullHandler()
    logger.addHandler(handler)
    try:
        assert get_logger(logger.name) is logger
        assert logger.handlers == [handler]
    finally:
        logger.removeHandler(handler)
        handler.close()


def test_reused_console_observes_new_logger_level(capsys):
    logger = get_logger("test_logger_updated_level", "WARNING")
    logger.info("filtered diagnostic")
    get_logger(logger.name, "INFO").info("enabled diagnostic")

    captured = capsys.readouterr()
    assert "filtered diagnostic" not in captured.err
    assert captured.err.count("enabled diagnostic") == 1
    assert captured.out == ""
    assert len(logger.handlers) == 1


def test_unknown_level_name_falls_back_to_the_default():
    """getattr(logging, level_name, DEFAULT) means a bad name is not fatal."""
    logger = get_logger("test_logger_bad_level", "NOT_A_LEVEL")
    assert logger.level == logging.INFO
