#!/usr/bin/env python3
"""
OpenRouter Reasoning Model Price Monitor

Autonomous monitor that checks OpenRouter API pricing for reasoning models
and alerts when costs drop significantly (signal that providers adopted
optimizations like NVIDIA DMS, KV cache compression, etc.).

Runs daily via GitHub Actions. When a drop ≥30% is detected:
1. Creates a GitHub Issue with the pricing change details
2. Updates data/openrouter_pricing_baseline.json with new prices

This enables automatic detection of when to route more tasks through
reasoning models in model_selector.py BATS framework.

Feb 2026 — Built per CEO directive for autonomous price monitoring.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Models we track for pricing changes
TRACKED_MODELS = {
    "deepseek/deepseek-r1": "DeepSeek-R1 (reasoning)",
    "deepseek/deepseek-chat": "DeepSeek V3 (chat)",
    "mistralai/mistral-medium-3": "Mistral Medium 3",
    "moonshotai/kimi-k2-0905": "Kimi K2",
    "qwen/qwen3-235b-a22b": "Qwen3 235B",
    "qwen/qwen-r1-32b": "Qwen-R1 32B (reasoning)",
}

# Alert threshold: notify when price drops by this percentage
PRICE_DROP_THRESHOLD = 0.30  # 30%

BASELINE_FILE = Path("data/openrouter_pricing_baseline.json")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/models"


def fetch_openrouter_prices() -> dict[str, dict]:
    """Fetch current pricing from OpenRouter API (no auth required)."""
    logger.info("Fetching pricing from OpenRouter API...")

    req = urllib.request.Request(
        OPENROUTER_API_URL,
        headers={"User-Agent": "trading-price-monitor/1.0"},
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())

    models = data.get("data", [])
    logger.info(f"Fetched {len(models)} models from OpenRouter")

    prices = {}
    for model in models:
        model_id = model.get("id", "")
        if model_id in TRACKED_MODELS:
            pricing = model.get("pricing", {})
            # OpenRouter returns cost as string per-token, convert to per-1M
            prompt_cost = float(pricing.get("prompt", "0")) * 1_000_000
            completion_cost = float(pricing.get("completion", "0")) * 1_000_000

            prices[model_id] = {
                "name": TRACKED_MODELS[model_id],
                "input_cost_per_1m": round(prompt_cost, 4),
                "output_cost_per_1m": round(completion_cost, 4),
                "fetched_at": datetime.now().isoformat(),
            }
            logger.info(f"  {model_id}: ${prompt_cost:.4f}/${completion_cost:.4f} per 1M tokens")

    return prices


def load_baseline() -> dict[str, dict]:
    """Load baseline pricing from file, or return empty if first run."""
    if not BASELINE_FILE.exists():
        logger.info("No baseline file found — this is the first run")
        return {}

    with open(BASELINE_FILE) as f:
        return json.load(f)


def save_baseline(prices: dict[str, dict]) -> None:
    """Save current prices as the new baseline."""
    BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(BASELINE_FILE, "w") as f:
        json.dump(prices, f, indent=2)
    logger.info(f"Baseline saved to {BASELINE_FILE}")


def detect_price_drops(
    current: dict[str, dict],
    baseline: dict[str, dict],
) -> list[dict]:
    """Compare current prices against baseline, return significant drops."""
    drops = []

    for model_id, curr_data in current.items():
        if model_id not in baseline:
            continue

        base_data = baseline[model_id]
        base_input = base_data.get("input_cost_per_1m", 0)
        base_output = base_data.get("output_cost_per_1m", 0)
        curr_input = curr_data.get("input_cost_per_1m", 0)
        curr_output = curr_data.get("output_cost_per_1m", 0)

        # Check input cost drop
        if base_input > 0:
            input_drop_pct = (base_input - curr_input) / base_input
        else:
            input_drop_pct = 0

        # Check output cost drop
        if base_output > 0:
            output_drop_pct = (base_output - curr_output) / base_output
        else:
            output_drop_pct = 0

        if input_drop_pct >= PRICE_DROP_THRESHOLD or output_drop_pct >= PRICE_DROP_THRESHOLD:
            drops.append(
                {
                    "model_id": model_id,
                    "name": curr_data["name"],
                    "input_before": base_input,
                    "input_after": curr_input,
                    "input_drop_pct": round(input_drop_pct * 100, 1),
                    "output_before": base_output,
                    "output_after": curr_output,
                    "output_drop_pct": round(output_drop_pct * 100, 1),
                }
            )

    return drops


def create_github_issue(drops: list[dict]) -> None:
    """Create a GitHub issue alerting about significant price drops."""
    import subprocess

    title = f"OpenRouter Price Drop Alert: {len(drops)} reasoning model(s) cheaper"

    body_lines = [
        "## OpenRouter Reasoning Model Price Drop Detected",
        "",
        "The autonomous price monitor detected significant pricing changes.",
        "This may indicate providers adopted optimizations (NVIDIA DMS, KV cache compression, etc.).",
        "",
        "### Price Changes",
        "",
        "| Model | Input (before → after) | Output (before → after) | Drop |",
        "|---|---|---|---|",
    ]

    for d in drops:
        max_drop = max(d["input_drop_pct"], d["output_drop_pct"])
        body_lines.append(
            f"| {d['name']} | ${d['input_before']:.2f} → ${d['input_after']:.2f}/1M "
            f"| ${d['output_before']:.2f} → ${d['output_after']:.2f}/1M "
            f"| **{max_drop:.0f}%** |"
        )

    body_lines.extend(
        [
            "",
            "### Action Required",
            "",
            "- [ ] Update `MODEL_REGISTRY` in `src/utils/model_selector.py` with new prices",
            "- [ ] Consider routing more tasks through cheaper reasoning models",
            "- [ ] Update BATS budget thresholds if significant savings available",
            "",
            f"*Auto-generated by `scripts/openrouter_price_monitor.py` on {datetime.now().strftime('%Y-%m-%d')}*",
        ]
    )

    body = "\n".join(body_lines)

    try:
        result = subprocess.run(
            [
                "gh",
                "issue",
                "create",
                "--title",
                title,
                "--body",
                body,
                "--label",
                "cost-optimization",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            logger.info(f"GitHub Issue created: {result.stdout.strip()}")
        else:
            logger.warning(f"Failed to create issue: {result.stderr}")
    except Exception as e:
        logger.warning(f"Could not create GitHub issue: {e}")


def main() -> dict:
    """Run the price monitor."""
    logger.info("=" * 60)
    logger.info("OPENROUTER PRICE MONITOR")
    logger.info("=" * 60)

    # Fetch current prices
    try:
        current_prices = fetch_openrouter_prices()
    except Exception as e:
        logger.error(f"Failed to fetch OpenRouter prices: {e}")
        return {"success": False, "reason": str(e)}

    if not current_prices:
        logger.warning("No tracked models found in OpenRouter response")
        return {"success": False, "reason": "no_tracked_models_found"}

    # Load baseline
    baseline = load_baseline()

    # First run: save baseline and exit
    if not baseline:
        save_baseline(current_prices)
        logger.info("First run — baseline established. Will detect drops on next run.")
        return {"success": True, "action": "baseline_established", "models": len(current_prices)}

    # Detect significant price drops
    drops = detect_price_drops(current_prices, baseline)

    if drops:
        logger.info("=" * 60)
        logger.info(f"PRICE DROP ALERT: {len(drops)} model(s) significantly cheaper!")
        logger.info("=" * 60)
        for d in drops:
            logger.info(
                f"  {d['name']}: input {d['input_drop_pct']}% drop, "
                f"output {d['output_drop_pct']}% drop"
            )

        # Create GitHub Issue
        if os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN"):
            create_github_issue(drops)
        else:
            logger.info("No GITHUB_TOKEN — skipping issue creation (local run)")

        # Update baseline with new prices
        save_baseline(current_prices)
    else:
        logger.info("No significant price drops detected")
        # Still update baseline to track gradual changes
        save_baseline(current_prices)

    # Log summary
    logger.info("=" * 60)
    logger.info("CURRENT REASONING MODEL PRICES")
    logger.info("=" * 60)
    for model_id, data in current_prices.items():
        logger.info(
            f"  {data['name']}: ${data['input_cost_per_1m']:.4f} in / "
            f"${data['output_cost_per_1m']:.4f} out per 1M"
        )

    return {
        "success": True,
        "models_checked": len(current_prices),
        "drops_detected": len(drops),
        "drops": drops,
    }


if __name__ == "__main__":
    result = main()
    print(f"\nResult: {json.dumps(result, indent=2, default=str)}")
