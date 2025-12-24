#!/usr/bin/env python3
"""
System Health Check - Verify ML/RAG/RL Actually Work
Run daily before trading to catch silent failures.

Usage: python3 scripts/system_health_check.py
"""

import sys
from datetime import datetime
from pathlib import Path


def check_rag_system():
    """Verify RAG system works end-to-end."""
    results = {"name": "RAG System", "status": "UNKNOWN", "details": []}

    try:
        from src.rag.lessons_learned_rag import LessonsLearnedRAG

        rag = LessonsLearnedRAG()
        results["details"].append(f"✓ LessonsLearnedRAG loaded with {len(rag.lessons)} lessons")

        # Test query() method
        if hasattr(rag, "query"):
            test_results = rag.query("trading failure", top_k=3)
            results["details"].append(
                f"✓ query() method works - returned {len(test_results)} results"
            )
        else:
            results["details"].append("✗ query() method missing")
            results["status"] = "BROKEN"
            return results

        # Test search() method (used by gates.py and main.py)
        if hasattr(rag, "search"):
            search_results = rag.search(query="trading failure", top_k=3)
            results["details"].append(
                f"✓ search() method works - returned {len(search_results)} results"
            )
            # Verify format is (lesson, score) tuples
            if search_results and len(search_results) > 0:
                first = search_results[0]
                if isinstance(first, tuple) and len(first) == 2:
                    results["details"].append("✓ search() returns correct (lesson, score) format")
                else:
                    results["details"].append("✗ search() returns wrong format")
                    results["status"] = "BROKEN"
                    return results
        else:
            results["details"].append("✗ search() method missing - gates.py will crash!")
            results["status"] = "BROKEN"
            return results

        results["status"] = "OK"

    except Exception as e:
        results["status"] = "BROKEN"
        results["details"].append(f"✗ Error: {e}")

    return results


def check_rl_system():
    """Verify RL system is functional, not just stubs."""
    results = {"name": "RL System", "status": "UNKNOWN", "details": []}

    try:
        # Check if RL is enabled
        import os

        rl_enabled = os.getenv("RL_FILTER_ENABLED", "false").lower() in {"true", "1"}
        results["details"].append(f"RL_FILTER_ENABLED: {rl_enabled}")

        # Check if agents are stubs
        from src.ml.dqn_agent import DQNAgent

        agent = DQNAgent()
        prediction = agent.predict({})

        if prediction == 0.5:
            results["details"].append("✗ DQNAgent returns hardcoded 0.5 (STUB)")
            results["status"] = "STUB"
        else:
            results["details"].append(f"✓ DQNAgent returns real prediction: {prediction}")
            results["status"] = "OK"

    except Exception as e:
        results["status"] = "BROKEN"
        results["details"].append(f"✗ Error: {e}")

    return results


def check_ml_pipeline():
    """Verify ML inference works."""
    results = {"name": "ML Pipeline", "status": "UNKNOWN", "details": []}

    try:
        from src.ml.inference import MLPredictor

        predictor = MLPredictor()
        prediction = predictor.predict({})

        if prediction == 0.5:
            results["details"].append("✗ MLPredictor returns hardcoded 0.5 (STUB)")
            results["status"] = "STUB"
        else:
            results["details"].append(f"✓ MLPredictor returns real prediction: {prediction}")
            results["status"] = "OK"

    except Exception as e:
        results["status"] = "BROKEN"
        results["details"].append(f"✗ Error: {e}")

    return results


def check_blog_deployment():
    """Verify blog lessons have dates and are current."""
    results = {"name": "Blog Deployment", "status": "UNKNOWN", "details": []}

    try:
        lessons_dir = Path("docs/_lessons")
        if not lessons_dir.exists():
            results["details"].append("✗ docs/_lessons/ directory missing")
            results["status"] = "BROKEN"
            return results

        lessons = list(lessons_dir.glob("*.md"))
        results["details"].append(f"✓ Found {len(lessons)} lesson files")

        # Check for date field in front matter
        missing_dates = 0
        for lesson in lessons[:10]:  # Sample check
            content = lesson.read_text()
            if "date:" not in content[:500]:
                missing_dates += 1

        if missing_dates > 0:
            results["details"].append(f"✗ {missing_dates}/10 sampled lessons missing date field")
            results["status"] = "BROKEN"
        else:
            results["details"].append("✓ All sampled lessons have date field")
            results["status"] = "OK"

    except Exception as e:
        results["status"] = "BROKEN"
        results["details"].append(f"✗ Error: {e}")

    return results


def main():
    """Run all health checks and report."""
    print("=" * 60)
    print(f"SYSTEM HEALTH CHECK - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    checks = [
        check_rag_system,
        check_rl_system,
        check_ml_pipeline,
        check_blog_deployment,
    ]

    all_ok = True
    for check in checks:
        result = check()
        status_icon = {"OK": "✅", "STUB": "⚠️", "BROKEN": "❌", "UNKNOWN": "❓"}
        icon = status_icon.get(result["status"], "❓")

        print(f"\n{icon} {result['name']}: {result['status']}")
        for detail in result["details"]:
            print(f"   {detail}")

        if result["status"] in ["BROKEN"]:
            all_ok = False

    print("\n" + "=" * 60)
    if all_ok:
        print("✅ ALL CHECKS PASSED")
        return 0
    else:
        print("❌ SOME CHECKS FAILED - FIX BEFORE TRADING")
        return 1


if __name__ == "__main__":
    sys.exit(main())
