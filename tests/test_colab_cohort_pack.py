"""Tests for Colab cohort packager."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def _load():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    path = SCRIPTS / "colab_cohort_pack.py"
    spec = importlib.util.spec_from_file_location("colab_cohort_pack", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_build_pack_writes_manifest(tmp_path: Path):
    mod = _load()
    # Use repo ledgers if present; else empty stubs
    trades = ROOT / "data" / "trades.json"
    entries = ROOT / "data" / "put_credit_entries.json"
    kill = ROOT / "data" / "runtime" / "strategy_kill_switch.json"
    if not trades.is_file():
        trades = tmp_path / "trades.json"
        trades.write_text(json.dumps({"trades": []}))
    if not entries.is_file():
        entries = tmp_path / "put_credit_entries.json"
        entries.write_text("{}")
    if not kill.is_file():
        kill = tmp_path / "strategy_kill_switch.json"
        kill.write_text(json.dumps({"active_family": "spy_put_credit", "live_blocked": True}))

    out = tmp_path / "packs"
    manifest = mod.build_pack(
        out_dir=out,
        trades_path=trades,
        entries_path=entries,
        kill_path=kill,
    )
    from urllib.parse import urlparse

    assert manifest["never_auto_buy_compute_units"] is True
    assert manifest["plan_policy"] == "use_existing_colab_pro_plus_only"
    assert Path(manifest["pack_dir"]).is_dir()
    assert Path(manifest["scorecard_path"]).is_file()
    assert (out / "latest.json").is_file()
    parsed = urlparse(str(manifest["colab_github_url"]))
    assert parsed.scheme == "https"
    assert parsed.hostname == "colab.research.google.com"


def test_notebook_exists_and_is_ipynb():
    nb = ROOT / "notebooks" / "put_credit_cohort_colab.ipynb"
    assert nb.is_file()
    data = json.loads(nb.read_text())
    assert data["nbformat"] == 4
    sources = "".join("".join(c.get("source") or []) for c in data["cells"])
    assert "never buy" in sources.lower() or "Never buy" in sources or "never buy" in sources
    assert "put_credit_cohort.json" in sources
