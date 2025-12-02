"""Central logging configuration for the hybrid orchestrator."""

from __future__ import annotations

import logging
import os


def setup_logging(level: str | None = None) -> logging.Logger:
    """
    Configure application-wide logging.

    Args:
        level: Optional log level override (INFO, DEBUG, etc.).

    Returns:
        Root trading logger instance.
    """

    log_level = level or os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    )
    logger = logging.getLogger("trading")
    logger.setLevel(getattr(logging, log_level, logging.INFO))
    return logger
