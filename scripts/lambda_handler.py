"""
AWS Lambda entrypoint for the hybrid trading orchestrator.

This lightweight shim allows us to re-use the same `scripts/autonomous_trader.py`
flow inside EventBridge/Lambda to guarantee cloud execution even if the primary
GitHub Actions runner is unavailable.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

WORKSPACE_ROOT = Path(__file__).resolve().parent
if str(WORKSPACE_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT / "src"))
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.autonomous_trader import main as run_autonomous_session  # noqa: E402

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def lambda_handler(event: dict | None, context: object | None) -> dict[str, str]:
    """
    AWS Lambda handler compatible with the instructions inside CLOUD_DEPLOYMENT.md.
    """
    env_path = WORKSPACE_ROOT / ".env"
    load_dotenv(env_path)  # Safe no-op if file missing
    os.environ.setdefault("ENABLE_WEEKEND_PROXY", "true")

    try:
        logger.info("Lambda trading invocation started (event=%s)", json.dumps(event or {}))
        run_autonomous_session()
        logger.info("Lambda trading invocation finished successfully.")
        return {"statusCode": "200", "body": "Hybrid orchestrator run completed"}
    except Exception as exc:  # pragma: no cover - cloud runtime diagnostics
        logger.exception("Lambda trading invocation failed: %s", exc)
        return {"statusCode": "500", "body": f"Execution failed: {exc}"}
