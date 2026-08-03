from __future__ import annotations

import json
from pathlib import Path

from scripts.query_lessons_learned import main, parse_args


def test_limit_aliases_share_one_destination() -> None:
    assert parse_args(["risk", "--limit", "3"]).limit == 3
    assert parse_args(["risk", "--top-k", "4"]).limit == 4


def test_query_cli_uses_dependency_free_custom_corpus(tmp_path: Path, capsys, monkeypatch) -> None:
    lesson = tmp_path / "ll_999_inventory_reconciliation.md"
    lesson.write_text(
        """# LL-999 Inventory reconciliation

## Summary
Reconcile broker inventory before allowing new risk.

## Tags
`inventory`, `risk`
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("LANCEDB_RAG", "false")

    result = main(
        [
            "broker inventory risk",
            "--knowledge-dir",
            str(tmp_path),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    # Custom corpus may hit pipeline, defended path, or keyword fallback.
    assert payload["source"] in {"pipeline", "keyword", "defended"}
    assert payload["count"] == 1
    assert payload["results"][0]["id"] == "ll_999_inventory_reconciliation"
