#!/usr/bin/env python3
"""CLI entrypoint for Codex notify -> hybrid RLHF bridge."""

from __future__ import annotations

from src.learning.codex_feedback_bridge import main


if __name__ == "__main__":
    raise SystemExit(main())
