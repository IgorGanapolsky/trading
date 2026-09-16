#!/usr/bin/env python3
"""
Unit tests for HydraFusion Multi-Model Orchestrator, Anti-Duplication Scanner,
LLM Semantic Cache, and DAIR.AI Research Scraper.
"""

from pathlib import Path
from scripts.anti_code_duplication_scanner import AntiCodeDuplicationScanner
from scripts.dair_ai_research_scraper import DAIRResearchScraper
from scripts.hydrafusion_orchestrator import HydraFusionOrchestrator
from scripts.llm_semantic_cache import LLMSemanticCache


def test_hydrafusion_orchestrator_patterns():
    orch = HydraFusionOrchestrator(quality_threshold=0.80)

    # 1. Single Pattern
    res_single = orch.execute_single("Draft hello world")
    assert res_single.pattern == "SINGLE"
    assert res_single.quality_score == 1.0
    assert not res_single.escalated

    # 2. Cascade Pattern (Fast Pass)
    res_cascade_pass = orch.execute_cascade(
        "Draft clean python function",
        quality_eval_fn=lambda out: 0.95,
    )
    assert res_cascade_pass.pattern == "CASCADE"
    assert not res_cascade_pass.escalated

    # 3. Cascade Pattern (Escalate to Frontier)
    res_cascade_escalate = orch.execute_cascade(
        "Draft complex compiler optimization",
        quality_eval_fn=lambda out: 0.50 if "local" in out.lower() else 0.95,
        runner_fn=lambda m, p: f"Output from {m}",
    )
    assert res_cascade_escalate.pattern == "CASCADE"
    assert res_cascade_escalate.escalated
    assert res_cascade_escalate.critic_or_escalated_model == orch.frontier_model

    # 4. Critique Pattern
    res_critique = orch.execute_critique("Implement risk diode")
    assert res_critique.pattern == "CRITIQUE"
    assert res_critique.critique_notes is not None
    assert "Critic" in res_critique.critique_notes


def test_llm_semantic_cache_l1_and_l2(tmp_path: Path):
    cache = LLMSemanticCache(cache_file=tmp_path / "cache.json", semantic_threshold=0.85)

    # Put entry
    cache.put("Calculate SPY put credit spread risk", '{"max_loss": 500, "credit": 50}')

    # L1 Exact Hit
    res_l1 = cache.get("Calculate SPY put credit spread risk")
    assert res_l1.hit
    assert res_l1.tier == "L1_EXACT"
    assert res_l1.similarity == 1.0

    # L2 Semantic Hit (Minor variation)
    res_l2 = cache.get("calculate spy put credit spread risk today")
    assert res_l2.hit
    assert res_l2.tier in ["L1_EXACT", "L2_SEMANTIC"]

    # Miss
    res_miss = cache.get("Completely unrelated real estate tax query")
    assert not res_miss.hit
    assert res_miss.tier == "MISS"


def test_anti_code_duplication_scanner(tmp_path: Path):
    scanner = AntiCodeDuplicationScanner(min_block_lines=4, max_duplication_pct=10.0)

    # Create two files with duplicate block
    file_a = tmp_path / "a.py"
    file_b = tmp_path / "b.py"

    duplicate_block = (
        "def compute_common_metric(x, y):\n"
        "    res = x * 2 + y * 3\n"
        "    adjusted = res / 100.0\n"
        "    return round(adjusted, 4)\n"
    )

    file_a.write_text(f"# File A\n{duplicate_block}\ndef unique_a(): pass\n", encoding="utf-8")
    file_b.write_text(f"# File B\n{duplicate_block}\ndef unique_b(): pass\n", encoding="utf-8")

    report = scanner.scan_directory(tmp_path)
    assert report.total_files_scanned == 2
    assert report.duplicate_blocks_count >= 1
    assert len(report.duplicates) >= 1


def test_dair_ai_research_scraper(tmp_path: Path):
    scraper = DAIRResearchScraper(output_dir=tmp_path)
    manifest = scraper.ingest_latest_research()

    assert manifest.total_papers_indexed >= 3
    assert len(manifest.papers) >= 3
    assert any("HydraFusion" in p.title for p in manifest.papers)
    assert any("GitClear" in " ".join(p.authors) or "gitclear" in p.tags for p in manifest.papers)


def test_main_climethods(capsys, tmp_path: Path):
    import sys
    from scripts.anti_code_duplication_scanner import main as scanner_main
    from scripts.dair_ai_research_scraper import main as scraper_main
    from scripts.hydrafusion_orchestrator import main as hydra_main
    from scripts.llm_semantic_cache import main as cache_main

    orig_argv = sys.argv
    try:
        # Scanner doctor
        sys.argv = ["anti_code_duplication_scanner.py", "--doctor"]
        scanner_main()
        captured = capsys.readouterr()
        assert "ONLINE" in captured.out

        # Scanner scan
        sys.argv = ["anti_code_duplication_scanner.py", "--path", str(tmp_path)]
        scanner_main()
        captured = capsys.readouterr()
        assert "ANTI-DUPLICATION SCANNER" in captured.out

        # Cache doctor
        sys.argv = ["llm_semantic_cache.py", "--doctor"]
        cache_main()
        captured = capsys.readouterr()
        assert "LLM Semantic Cache: ONLINE" in captured.out

        # Hydra doctor
        sys.argv = ["hydrafusion_orchestrator.py", "--doctor"]
        hydra_main()
        captured = capsys.readouterr()
        assert "HydraFusion Orchestrator: ONLINE" in captured.out

        # Hydra single and critique
        sys.argv = ["hydrafusion_orchestrator.py", "--pattern", "single"]
        hydra_main()
        captured = capsys.readouterr()
        assert "SINGLE" in captured.out

        sys.argv = ["hydrafusion_orchestrator.py", "--pattern", "critique"]
        hydra_main()
        captured = capsys.readouterr()
        assert "CRITIQUE" in captured.out

        # Scraper doctor and sync
        sys.argv = ["dair_ai_research_scraper.py", "--doctor"]
        scraper_main()
        captured = capsys.readouterr()
        assert "ONLINE" in captured.out

        sys.argv = ["dair_ai_research_scraper.py", "--sync"]
        scraper_main()
        captured = capsys.readouterr()
        assert "RESEARCH INGESTION" in captured.out

    finally:
        sys.argv = orig_argv
