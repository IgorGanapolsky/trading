"""
Compatibility helpers for third-party libraries expecting pydantic.BaseSettings.
"""

import logging
from functools import lru_cache

from packaging.version import InvalidVersion, Version

logger = logging.getLogger(__name__)


def _pydantic_version() -> Version | None:
    """Return parsed pydantic version if available."""
    try:
        import pydantic  # type: ignore

        return Version(pydantic.__version__)
    except (ImportError, InvalidVersion):
        return None


@lru_cache(maxsize=1)
def ensure_pydantic_base_settings() -> None:
    """
    Some libraries (e.g. ChromaDB) still import BaseSettings from pydantic<2.x.
    This shim re-exports the class from pydantic-settings to keep them working.
    """
    version = _pydantic_version()
    if version and version >= Version("2.0.0"):
        logger.debug("Pydantic >= 2 detected (%s); skipping BaseSettings shim", version)
        return

    try:
        import pydantic  # type: ignore
        from pydantic_settings import BaseSettings  # type: ignore

        pydantic.BaseSettings = BaseSettings  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        logger.debug("Could not apply pydantic BaseSettings shim: %s", exc)
