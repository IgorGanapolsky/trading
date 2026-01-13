"""
Centralized logging setup for trading scripts.

This module provides a standardized logging configuration to eliminate
DRY violations across scripts. Each script can initialize consistent
logging with a single function call.

Usage:
    from src.utils.logging_setup import setup_script_logging

    logger = setup_script_logging("my_script")
    logger.info("Script started")
"""

import logging
import os
from datetime import datetime


def setup_script_logging(
    script_name: str,
    log_dir: str = "logs",
    level: str | None = None,
    include_console: bool = True,
) -> logging.Logger:
    """
    Initialize logging for trading scripts with consistent format.

    Creates a logger with both console and file handlers, using a
    standardized format across all scripts. Log files are timestamped
    to prevent overwrites and enable historical analysis.

    Args:
        script_name: Name of the script (used for logger name and log file).
        log_dir: Directory for log files. Defaults to "logs".
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
               Defaults to LOG_LEVEL env var or INFO.
        include_console: Whether to include console output. Defaults to True.

    Returns:
        logging.Logger: Configured logger instance ready for use.

    Example:
        >>> logger = setup_script_logging("daily_health_check")
        >>> logger.info("Starting health check")
        >>> logger.error("Connection failed", exc_info=True)
    """
    # Determine log level from parameter, environment, or default
    log_level = level or os.getenv("LOG_LEVEL", "INFO").upper()
    numeric_level = getattr(logging, log_level, logging.INFO)

    # Create log directory if it doesn't exist
    # Use absolute path based on current working directory
    if not os.path.isabs(log_dir):
        log_dir = os.path.join(os.getcwd(), log_dir)
    os.makedirs(log_dir, exist_ok=True)

    # Create logger with script-specific name
    logger = logging.getLogger(script_name)
    logger.setLevel(numeric_level)

    # Clear existing handlers to avoid duplicates on repeated calls
    logger.handlers = []

    # Define consistent format for all handlers
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    formatter = logging.Formatter(log_format)

    # Add console handler if requested
    if include_console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # Create timestamped log file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"{script_name}_{timestamp}.log"
    log_path = os.path.join(log_dir, log_filename)

    # Add file handler with same format
    file_handler = logging.FileHandler(log_path)
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Prevent propagation to root logger to avoid duplicate logs
    logger.propagate = False

    logger.debug(f"Logging initialized: {log_path}")

    return logger


def get_script_logger(script_name: str) -> logging.Logger:
    """
    Get an existing logger by script name without reconfiguring.

    Use this to retrieve a logger that was previously set up with
    setup_script_logging(). If the logger doesn't exist, returns
    a basic logger without file handling.

    Args:
        script_name: Name of the script/logger to retrieve.

    Returns:
        logging.Logger: The existing logger instance.
    """
    return logging.getLogger(script_name)
