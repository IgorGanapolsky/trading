"""
Compatibility helpers for third-party libraries expecting pydantic.BaseSettings.
"""

import logging
from functools import lru_cache

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def ensure_pydantic_base_settings() -> None:
    """
    Some libraries (e.g. ChromaDB) still import BaseSettings from pydantic<2.x.
    This shim re-exports the class from pydantic-settings to keep them working.
    """
    try:
        import pydantic  # type: ignore
        from pydantic_settings import BaseSettings  # type: ignore

        pydantic.BaseSettings = BaseSettings  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        logger.debug("Could not apply pydantic BaseSettings shim: %s", exc)
