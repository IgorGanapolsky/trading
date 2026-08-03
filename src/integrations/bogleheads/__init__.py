"""Bogleheads forum automation: RSS ingest, RAG promote, Chrome session, gated post."""

from __future__ import annotations

from src.integrations.bogleheads.pipeline import run_pipeline
from src.integrations.bogleheads.rss import fetch_bogleheads_feed

__all__ = ["fetch_bogleheads_feed", "run_pipeline"]
