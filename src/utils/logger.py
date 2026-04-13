import logging
import os
import sys
from pathlib import Path


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logger.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # stdout handler
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    # file handler (only if /app/data exists — i.e. inside Docker)
    log_dir = Path("/app/data")
    if log_dir.exists():
        file_handler = logging.FileHandler(log_dir / "pulse.log")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
