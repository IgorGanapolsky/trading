"""Trade Lock - Prevents Race Conditions in Position Accumulation.

CRITICAL SAFETY COMPONENT - Jan 22, 2026 (LL-281)

This module implements a file-based mutex to prevent multiple trades
from passing position checks simultaneously.

Root Cause of Crisis:
- Multiple trade requests evaluated position count at same time
- Each passed the "< 4 positions" check
- All executed, resulting in 8 contracts instead of max 4

Solution:
- Acquire exclusive lock before evaluating trade
- Hold lock through execution
- Release after trade completes or fails

Author: AI Trading System
Date: January 22, 2026
"""

import fcntl
import logging
import os
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator

logger = logging.getLogger(__name__)

# Lock file location
LOCK_FILE = Path("data/.trade_lock")
LOCK_TIMEOUT = 30  # seconds - max time to wait for lock
LOCK_STALE_THRESHOLD = 300  # 5 minutes - consider lock stale after this


class TradeLockError(Exception):
    """Raised when trade lock cannot be acquired."""

    pass


class TradeLockTimeout(TradeLockError):
    """Raised when lock acquisition times out."""

    pass


def _is_lock_stale(lock_file: Path) -> bool:
    """Check if lock file is stale (older than threshold)."""
    if not lock_file.exists():
        return False
    try:
        mtime = lock_file.stat().st_mtime
        age = time.time() - mtime
        return age > LOCK_STALE_THRESHOLD
    except Exception:
        return True  # Assume stale if we can't check


def _clear_stale_lock(lock_file: Path) -> None:
    """Remove stale lock file."""
    try:
        if lock_file.exists() and _is_lock_stale(lock_file):
            logger.warning(f"🔓 Clearing stale lock file: {lock_file}")
            lock_file.unlink()
    except Exception as e:
        logger.error(f"Failed to clear stale lock: {e}")


@contextmanager
def acquire_trade_lock(timeout: float = LOCK_TIMEOUT) -> Generator[None, None, None]:
    """
    Acquire exclusive trade lock.

    This MUST be held during:
    1. Position count check
    2. Trade evaluation
    3. Trade execution

    Usage:
        with acquire_trade_lock():
            # Check positions
            # Evaluate trade
            # Execute trade

    Raises:
        TradeLockTimeout: If lock cannot be acquired within timeout
    """
    # Ensure lock directory exists
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Clear stale locks
    _clear_stale_lock(LOCK_FILE)

    start_time = time.time()
    lock_fd = None

    try:
        # Open/create lock file
        lock_fd = os.open(str(LOCK_FILE), os.O_RDWR | os.O_CREAT)

        # Try to acquire exclusive lock with timeout
        while True:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break  # Lock acquired
            except BlockingIOError:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    raise TradeLockTimeout(
                        f"Could not acquire trade lock within {timeout}s. "
                        "Another trade may be in progress."
                    )
                logger.debug(f"Waiting for trade lock... ({elapsed:.1f}s)")
                time.sleep(0.5)

        # Write lock info
        os.ftruncate(lock_fd, 0)
        os.lseek(lock_fd, 0, os.SEEK_SET)
        lock_info = f"pid={os.getpid()},time={datetime.now().isoformat()}\n"
        os.write(lock_fd, lock_info.encode())

        logger.info("🔒 Trade lock acquired")
        yield

    finally:
        if lock_fd is not None:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                os.close(lock_fd)
                logger.info("🔓 Trade lock released")
            except Exception as e:
                logger.error(f"Error releasing trade lock: {e}")


def is_trade_locked() -> bool:
    """Check if trade lock is currently held."""
    if not LOCK_FILE.exists():
        return False

    try:
        fd = os.open(str(LOCK_FILE), os.O_RDONLY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fd, fcntl.LOCK_UN)
            return False  # Lock not held
        except BlockingIOError:
            return True  # Lock is held
        finally:
            os.close(fd)
    except Exception:
        return False


def force_release_lock() -> bool:
    """
    Force release trade lock (emergency use only).

    WARNING: Only use this if you're sure no trade is in progress
    and the lock is stuck.

    Returns:
        True if lock was released, False otherwise
    """
    try:
        if LOCK_FILE.exists():
            logger.warning("⚠️ Force releasing trade lock!")
            LOCK_FILE.unlink()
            return True
    except Exception as e:
        logger.error(f"Failed to force release lock: {e}")
    return False
