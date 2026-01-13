#!/usr/bin/env python3
"""
Automatic Failure Reflection System (Reflexion Pattern).

Based on arXiv 2303.11366 - "Reflexion: Language Agents with Verbal Reinforcement Learning"
Key insight: Store verbal reflections about failures in episodic memory for future retrieval.

This module auto-generates lessons from:
- Trade execution failures
- Blocked trades (by gates)
- System errors during trading

NO fine-tuning required - improvement via in-context learning.
Created: Jan 13, 2026
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

LESSONS_DIR = Path("rag_knowledge/lessons_learned")
REFLECTIONS_LOG = Path("data/failure_reflections.json")


def generate_failure_reflection(
    failure_type: str,
    symbol: Optional[str] = None,
    error_message: str = "",
    context: Optional[dict[str, Any]] = None,
    strategy: Optional[str] = None,
) -> dict[str, Any]:
    """
    Generate verbal reflection from failure context (Reflexion pattern).

    This is the SELF-REFLECTION step from Reflexion:
    - Analyze what went wrong
    - Generate actionable insight
    - Store for future retrieval

    Args:
        failure_type: Type of failure (TRADE_BLOCKED, ORDER_FAILED, GATE_REJECTED, etc.)
        symbol: Trading symbol if applicable
        error_message: The actual error message
        context: Additional context (account state, market conditions, etc.)
        strategy: Trading strategy that failed

    Returns:
        Reflection dict with: id, title, content, severity, prevention
    """
    context = context or {}
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Determine severity based on failure type
    severity_map = {
        "TRADE_BLOCKED": "HIGH",
        "ORDER_FAILED": "CRITICAL",
        "GATE_REJECTED": "MEDIUM",
        "PATTERN_BLOCKED": "HIGH",
        "STOP_LOSS_FAILED": "CRITICAL",
        "SYNC_FAILED": "HIGH",
    }
    severity = severity_map.get(failure_type, "MEDIUM")

    # Generate reflection content based on failure type
    if failure_type == "TRADE_BLOCKED":
        title = f"Trade blocked: {symbol or 'unknown'} - {strategy or 'unknown strategy'}"
        root_cause = f"Trade was blocked by safety gate. Reason: {error_message}"
        prevention = "Review gate criteria before attempting similar trades. Check for: position limits, buying power, pattern history."

    elif failure_type == "ORDER_FAILED":
        title = f"Order execution failed: {symbol or 'unknown'}"
        root_cause = f"Broker rejected order. Error: {error_message}"
        prevention = "Verify account has sufficient funds. Check symbol is tradeable. Confirm market hours."

    elif failure_type == "PATTERN_BLOCKED":
        win_rate = context.get("win_rate", 0)
        sample_size = context.get("sample_size", 0)
        title = f"Pattern blocked due to poor history: {strategy}"
        root_cause = f"Strategy {strategy} has {win_rate:.1%} win rate over {sample_size} trades - below 50% threshold."
        prevention = f"Avoid {strategy} strategy until win rate improves. Consider: different entry criteria, better timing, alternative strategy."

    elif failure_type == "STOP_LOSS_FAILED":
        title = f"CRITICAL: Stop-loss not placed for {symbol}"
        root_cause = f"Position opened WITHOUT protection. Error: {error_message}"
        prevention = "NEVER open positions without stop-loss. If stop fails, immediately close position manually."
        severity = "CRITICAL"

    elif failure_type == "SYNC_FAILED":
        title = "Portfolio sync failed - blind trading risk"
        root_cause = f"Cannot verify account state. Error: {error_message}"
        prevention = "BLOCK all trading until sync restored. Never trade without knowing current positions/equity."

    else:
        title = f"Trading failure: {failure_type}"
        root_cause = error_message or "Unknown error occurred"
        prevention = "Review logs and investigate root cause before retrying."

    # Build reflection
    reflection = {
        "id": f"auto_{failure_type.lower()}_{timestamp}",
        "timestamp": datetime.now().isoformat(),
        "failure_type": failure_type,
        "symbol": symbol,
        "strategy": strategy,
        "title": title,
        "severity": severity,
        "root_cause": root_cause,
        "prevention": prevention,
        "context": context,
        "error_message": error_message,
    }

    # Log the reflection
    logger.warning(f"[REFLEXION] {severity}: {title}")
    logger.info(f"[REFLEXION] Root cause: {root_cause}")
    logger.info(f"[REFLEXION] Prevention: {prevention}")

    return reflection


def save_reflection_to_rag(reflection: dict[str, Any]) -> Optional[str]:
    """
    Save reflection to RAG lessons directory for future retrieval.

    This is the EPISODIC MEMORY storage from Reflexion.
    Saved lessons are automatically picked up by LessonsSearch.

    Returns:
        Path to saved lesson file, or None if save failed
    """
    try:
        LESSONS_DIR.mkdir(parents=True, exist_ok=True)

        # Generate lesson filename
        date_str = datetime.now().strftime("%b%d").lower()
        lesson_id = f"auto_{reflection['failure_type'].lower()}_{date_str}"
        filename = f"{lesson_id}.md"
        filepath = LESSONS_DIR / filename

        # Check if similar lesson exists (avoid duplicates)
        # Allow max 3 auto-lessons per failure type per day
        existing = list(LESSONS_DIR.glob(f"auto_{reflection['failure_type'].lower()}_{date_str}*.md"))
        if len(existing) >= 3:
            logger.info(f"[REFLEXION] Max auto-lessons reached for {reflection['failure_type']} today, skipping save")
            return None

        # Add sequence number if exists
        if filepath.exists():
            for i in range(2, 4):
                new_path = LESSONS_DIR / f"{lesson_id}_{i}.md"
                if not new_path.exists():
                    filepath = new_path
                    break

        # Format as markdown lesson (matches LessonsSearch format)
        content = f"""# {reflection['title']}

**ID**: {reflection['id']}
**Date**: {datetime.now().strftime('%Y-%m-%d')}
**Severity**: {reflection['severity']}
**Type**: Auto-generated (Reflexion pattern)

## Problem
{reflection['root_cause']}

## Context
- Symbol: {reflection.get('symbol', 'N/A')}
- Strategy: {reflection.get('strategy', 'N/A')}
- Error: {reflection.get('error_message', 'N/A')}

## Prevention
{reflection['prevention']}

## Tags
failure, {reflection['failure_type'].lower()}, auto-generated, reflexion
"""

        with open(filepath, "w") as f:
            f.write(content)

        logger.info(f"[REFLEXION] Saved lesson to {filepath}")
        return str(filepath)

    except Exception as e:
        logger.error(f"[REFLEXION] Failed to save lesson: {e}")
        return None


def log_reflection(reflection: dict[str, Any]) -> None:
    """
    Log reflection to JSON file for analysis and stats.
    Keeps last 100 reflections.
    """
    try:
        REFLECTIONS_LOG.parent.mkdir(parents=True, exist_ok=True)

        # Load existing
        if REFLECTIONS_LOG.exists():
            with open(REFLECTIONS_LOG) as f:
                data = json.load(f)
        else:
            data = {"reflections": [], "stats": {}}

        # Append new reflection
        data["reflections"].append(reflection)
        data["reflections"] = data["reflections"][-100:]  # Keep last 100

        # Update stats
        ft = reflection["failure_type"]
        data["stats"][ft] = data["stats"].get(ft, 0) + 1
        data["last_updated"] = datetime.now().isoformat()

        with open(REFLECTIONS_LOG, "w") as f:
            json.dump(data, f, indent=2)

    except Exception as e:
        logger.warning(f"[REFLEXION] Failed to log reflection: {e}")


def reflect_on_failure(
    failure_type: str,
    symbol: Optional[str] = None,
    error_message: str = "",
    context: Optional[dict[str, Any]] = None,
    strategy: Optional[str] = None,
    save_to_rag: bool = True,
) -> dict[str, Any]:
    """
    Main entry point: Generate reflection and optionally save to RAG.

    This implements the full Reflexion loop:
    1. Generate verbal reflection about failure
    2. Store in episodic memory (RAG lessons)
    3. Future actions will retrieve this lesson

    Usage:
        from src.learning.failure_reflection import reflect_on_failure

        # When a trade fails:
        reflect_on_failure(
            failure_type="ORDER_FAILED",
            symbol="AAPL",
            error_message="Insufficient buying power",
            strategy="momentum"
        )
    """
    # Generate reflection
    reflection = generate_failure_reflection(
        failure_type=failure_type,
        symbol=symbol,
        error_message=error_message,
        context=context,
        strategy=strategy,
    )

    # Log to JSON
    log_reflection(reflection)

    # Save to RAG if enabled
    if save_to_rag:
        filepath = save_reflection_to_rag(reflection)
        reflection["saved_to"] = filepath

    return reflection


# Convenience functions for common failure types
def reflect_trade_blocked(symbol: str, reason: str, strategy: str = None, context: dict = None):
    """Reflect on a blocked trade."""
    return reflect_on_failure("TRADE_BLOCKED", symbol, reason, context, strategy)


def reflect_order_failed(symbol: str, error: str, strategy: str = None, context: dict = None):
    """Reflect on a failed order."""
    return reflect_on_failure("ORDER_FAILED", symbol, error, context, strategy)


def reflect_pattern_blocked(strategy: str, win_rate: float, sample_size: int):
    """Reflect on a pattern-blocked trade."""
    return reflect_on_failure(
        "PATTERN_BLOCKED",
        error_message=f"Win rate {win_rate:.1%} below threshold",
        context={"win_rate": win_rate, "sample_size": sample_size},
        strategy=strategy,
    )


def reflect_stop_loss_failed(symbol: str, error: str):
    """Reflect on failed stop-loss placement - CRITICAL."""
    return reflect_on_failure("STOP_LOSS_FAILED", symbol, error)
