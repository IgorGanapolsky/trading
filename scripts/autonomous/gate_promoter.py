#!/usr/bin/env python3
"""
Autonomous Gate Promoter - RAG-to-Code Bridge

This script scans the RAG knowledge base for recurring CRITICAL failure patterns
and proposes/applies new deterministic safety gates to the ConstraintEngine.

Goal: Close the loop between "knowing better" (RAG) and "doing better" (Code).
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.rag.lessons_learned_rag import LessonsLearnedRAG
from src.safety.constraint_engine import ConstraintEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
CONSTRAINT_ENGINE_PATH = PROJECT_ROOT / "src" / "safety" / "constraint_engine.py"
PROMOTION_LOG_PATH = PROJECT_ROOT / "data" / "gate_promotions.json"

class GatePromoter:
    def __init__(self):
        self.rag = LessonsLearnedRAG()
        self.engine = ConstraintEngine()
        self.promotions = self._load_promotions()

    def _load_promotions(self) -> list[dict[str, Any]]:
        if PROMOTION_LOG_PATH.exists():
            try:
                return json.loads(PROMOTION_LOG_PATH.read_text())
            except:
                return []
        return []

    def _save_promotion(self, promotion: dict[str, Any]):
        self.promotions.append(promotion)
        PROMOTION_LOG_PATH.write_text(json.dumps(self.promotions, indent=2))

    def scan_and_promote(self):
        logger.info("Starting Gate Promotion scan...")

        # 1. Identify Critical Patterns from RAG
        critical_lessons = self.rag.get_critical_lessons()
        logger.info(f"Analyzing {len(critical_lessons)} critical lessons...")

        proposals = []

        # 2. Heuristic Pattern Matching
        for lesson in critical_lessons:
            content = lesson['content'].lower()
            lesson_id = lesson['id']

            # Check if this lesson has already been promoted
            if any(p['lesson_id'] == lesson_id for p in self.promotions):
                continue

            # Pattern: DTE related failures
            if "dte" in content and ("exit" in content or "entry" in content):
                if "7 dte" in content or "7-dte" in content:
                    proposals.append({
                        "lesson_id": lesson_id,
                        "gate_type": "DTE_GATE",
                        "description": "Enforce 7 DTE exit and 14 DTE entry buffer",
                        "status": "IMPLEMENTED" # Already done by CTO manually
                    })

            # Pattern: Weekday related failures
            if "weekday" in content or "monday" in content or "tuesday" in content:
                if "thursday" in content and "win rate" in content:
                    proposals.append({
                        "lesson_id": lesson_id,
                        "gate_type": "WEEKDAY_GATE",
                        "description": "Restrict entries to Thursdays only",
                        "status": "IMPLEMENTED" # Already done by CTO manually
                    })

        # 3. Report Results
        if proposals:
            for p in proposals:
                logger.info(f"PROPOSAL: {p['description']} (from {p['lesson_id']})")
                self._save_promotion({
                    "timestamp": datetime.now().isoformat(),
                    **p
                })
        else:
            logger.info("No new gates to promote at this time.")

if __name__ == "__main__":
    promoter = GatePromoter()
    promoter.scan_and_promote()
