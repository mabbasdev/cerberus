"""
logger_setup.py
---------------
Rotating file logger for Cerberus.

Every authentication attempt (and every shutdown decision) is written
to cerberus.log with timestamps. This is your audit trail — essential
for a security project report.
"""

import logging
from logging.handlers import RotatingFileHandler

LOG_FILE = "cerberus.log"


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger (file + console) for the given module."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    return logger