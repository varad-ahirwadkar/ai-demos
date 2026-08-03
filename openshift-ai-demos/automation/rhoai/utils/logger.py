"""Logging configuration.

Call configure() once at startup. All other modules call get_logger(__name__).
"""

import logging
import sys


def configure(level: str = "INFO") -> None:
    """Configure root logger. Called once from cli/main.py.

    Args:
        level: DEBUG, INFO, WARNING, or ERROR.
    """
    logging.basicConfig(
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )


def get_logger(name: str) -> logging.Logger:
    """Return a logger for the given module.

    Usage:
        from utils.logger import get_logger
        log = get_logger(__name__)
    """
    return logging.getLogger(name)
