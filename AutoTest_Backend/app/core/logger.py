"""Centralised logging configuration for the AutoTest backend."""

import logging
import sys


def get_logger(name: str) -> logging.Logger:
    """Return a named logger under the ``autotest`` hierarchy."""
    return logging.getLogger(f"autotest.{name}")


def setup_logging(*, level: int = logging.INFO) -> None:
    """Configure the root ``autotest`` logger once at application startup."""
    root = logging.getLogger("autotest")
    if root.handlers:
        return
    root.setLevel(level)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root.addHandler(handler)
