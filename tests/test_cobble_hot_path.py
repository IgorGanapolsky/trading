"""CobbleDB FORMAT: query the hot JSONL, never glob durable markdown."""

from __future__ import annotations

import json
from pathlib import Path

import scripts.cobble_hot_path as mod

ROOT = Path(__file__).resolve().parents[1]


def _md(dir_: Path, name: str, body: str) -> Path:
    p = dir_ / name
    p.write_text(body, encoding="utf-8")
    return p


def test_export_then_multiget_does_not_need_markdown(tmp_path: Path):
    durable = tmp_path / "lessons"
    durable.mkdir()
    _md(
        durable,
        "ll_demo.md",
        "# ll_demo\n\nSeverity: HIGH\n\nNever glob durable files at query time.\n",
    )
    _md(
        durable,
        "ll_other.md",
        "# ll_other\n\nSeverity: LOW\n\nBatched updates only.\n",
    )
    hot = tmp_path / "hot.jsonl"
    exp = mod.export_hot(durable=durable, hot=hot)
    assert exp["exported"] == 2
    # Remove durable so a glob would fail
    for p in durable.glob("*.md"):
        p.unlink()
    got = mod.multiget(hot, ["ll_demo", "missing"])
    assert got["durable_globbed"] is False
    assert got["n_hits"] == 1
    assert got["misses"] == ["missing"]
    assert got["hits"][0]["id"] == "ll_demo"


def test_query_scores_excerpts_only(tmp_path: Path):
    durable = tmp_path / "lessons"
    durable.mkdir()
    _md(durable, "a.md", "# ll_straggler\n\nSeverity: HIGH\n\nSync idle wait.\n")
    _md(durable, "b.md", "# ll_unrelated\n\nSeverity: LOW\n\nSomething else.\n")
    hot = tmp_path / "hot.jsonl"
    mod.export_hot(durable=durable, hot=hot)
    q = mod.query_hot(hot, "straggler idle", limit=5)
    assert q["durable_globbed"] is False
    assert q["count"] >= 1
    assert q["results"][0]["id"] == "ll_straggler"


def test_status_stale_when_counts_differ(tmp_path: Path):
    durable = tmp_path / "lessons"
    durable.mkdir()
    _md(durable, "a.md", "# ll_a\n\nSeverity: LOW\n\nx\n")
    hot = tmp_path / "hot.jsonl"
    mod.export_hot(durable=durable, hot=hot)
    _md(durable, "b.md", "# ll_b\n\nSeverity: LOW\n\ny\n")
    st = mod.status(durable=durable, hot=hot)
    assert st["stale"] is True
    assert st["n_durable"] == 2
    assert st["n_hot"] == 1
    assert "do_not_clone_cobbledb" in st["refuses"]
    assert "do_not_claim_5x_latency" in st["refuses"]


def test_cli_export_query_and_status(tmp_path: Path, capsys):
    durable = tmp_path / "lessons"
    durable.mkdir()
    (durable / "ll_cli.md").write_text(
        "# ll_cli\n\nSeverity: MEDIUM\n\nHot path only.\n", encoding="utf-8"
    )
    hot = tmp_path / "hot.jsonl"

    ret = mod.main(["--durable", str(durable), "--hot", str(hot), "export"])
    assert ret == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["exported"] == 1

    ret = mod.main(["--hot", str(hot), "get", "--keys", "ll_cli,nope"])
    assert ret == 0
    got = json.loads(capsys.readouterr().out)
    assert got["n_hits"] == 1
    assert got["durable_globbed"] is False

    ret = mod.main(["--hot", str(hot), "query", "hot path", "--limit", "2"])
    assert ret == 0
    q_out = json.loads(capsys.readouterr().out)
    assert q_out["count"] == 1
    assert q_out["results"][0]["id"] == "ll_cli"

    ret = mod.main(["--durable", str(durable), "--hot", str(hot), "status"])
    assert ret == 0
    st_out = json.loads(capsys.readouterr().out)
    assert st_out["ok"] is True
    assert st_out["stale"] is False
