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

    # Create logs directory if it doesn't exist
    log_dir = os.path.join(os.getcwd(), "logs")
    os.makedirs(log_dir, exist_ok=True)

    # Configure root logger
    logger = logging.getLogger("trading")
    logger.setLevel(getattr(logging, log_level, logging.INFO))
    logger.handlers = []  # clear existing handlers to avoid duplicates

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level, logging.INFO))
    console_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File Handler - System Log (INFO+)
    system_log_path = os.path.join(log_dir, "trading_system.log")
    file_handler = logging.FileHandler(system_log_path)
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # File Handler - Error Log (ERROR+)
    error_log_path = os.path.join(log_dir, "trading_errors.log")
    error_handler = logging.FileHandler(error_log_path)
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)
    logger.addHandler(error_handler)

    return logger
