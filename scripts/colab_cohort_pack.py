#!/usr/bin/env python3
"""Package put-credit cohort evidence for Google Colab Pro+ (no new spend).

Verified UI: Colab home shows "Colab Pro+ home" for iganapolsky@gmail.com.
Never auto-purchases compute units. Optional Colab CLI recipe only.

Usage:
  .venv/bin/python scripts/colab_cohort_pack.py
  .venv/bin/python scripts/colab_cohort_pack.py --json
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess  # nosec B404 — local packager / version probe only
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
for path in (ROOT, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import put_credit_cohort_scorecard as sc  # noqa: E402

DEFAULT_OUT_DIR = ROOT / "data" / "audit" / "colab_packs"
GITHUB_NOTEBOOK_URL = (
    "https://colab.research.google.com/github/IgorGanapolsky/trading/blob/main/"
    "notebooks/put_credit_cohort_colab.ipynb"
)


def _which_colab() -> str | None:
    return shutil.which("colab")


def _compute_scorecard(
    trades_path: Path,
    entries_path: Path,
    kill_path: Path,
) -> dict[str, Any]:
    if hasattr(sc, "build_scorecard"):
        return sc.build_scorecard(  # type: ignore[attr-defined]
            trades_path=trades_path,
            entries_path=entries_path,
            kill_path=kill_path,
        )
    trades = sc._load_json(trades_path)  # noqa: SLF001
    entries = sc._load_json(entries_path)  # noqa: SLF001
    kill = sc._load_json(kill_path)  # noqa: SLF001
    rows = sc._trade_rows(trades)
    closed = sc.summarize_closed(rows)
    open_ = sc.summarize_open(entries if isinstance(entries, dict) else None)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "kill_switch": kill,
        "closed": closed,
        "open": open_,
        "source": {
            "trades": str(trades_path),
            "entries": str(entries_path),
            "kill": str(kill_path),
        },
    }


def build_pack(
    *,
    out_dir: Path,
    trades_path: Path | None = None,
    entries_path: Path | None = None,
    kill_path: Path | None = None,
) -> dict[str, Any]:
    trades_path = trades_path or sc.DEFAULT_TRADES
    entries_path = entries_path or sc.DEFAULT_ENTRIES
    kill_path = kill_path or sc.DEFAULT_KILL

    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    pack_dir = out_dir / f"cohort_{stamp}"
    pack_dir.mkdir(parents=True, exist_ok=True)

    scorecard = _compute_scorecard(trades_path, entries_path, kill_path)
    score_path = pack_dir / "put_credit_cohort.json"
    score_path.write_text(json.dumps(scorecard, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for src, name in (
        (trades_path, "trades.json"),
        (entries_path, "put_credit_entries.json"),
        (kill_path, "strategy_kill_switch.json"),
    ):
        if src.is_file():
            shutil.copy2(src, pack_dir / name)

    closed = scorecard.get("closed") if isinstance(scorecard.get("closed"), dict) else {}
    kill_verdict = (closed.get("kill_criteria") or {}).get("verdict")

    colab_bin = _which_colab()
    colab_ver = None
    if colab_bin:
        try:
            ver = subprocess.run(  # nosec B603
                [colab_bin, "version"],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            colab_ver = (ver.stdout or ver.stderr or "").strip()[:80]
        except Exception:  # noqa: BLE001
            colab_ver = None

    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "plan_policy": "use_existing_colab_pro_plus_only",
        "never_auto_buy_compute_units": True,
        "account_hint": "iganapolsky@gmail.com",
        "verified_ui": "Colab home link label: Colab Pro+ home",
        "pack_dir": str(pack_dir),
        "scorecard_path": str(score_path),
        "notebook_repo_path": "notebooks/put_credit_cohort_colab.ipynb",
        "colab_github_url": GITHUB_NOTEBOOK_URL,
        "colab_cli_present": bool(colab_bin),
        "colab_cli_version": colab_ver,
        "colab_cli_recipe": [
            "colab new --gpu t4",
            f"colab upload {score_path} /content/put_credit_cohort.json",
            "colab exec -f notebooks/put_credit_cohort_colab.ipynb",
            "colab stop",
        ],
        "kill_verdict": kill_verdict,
        "closed_n": closed.get("closed_n"),
        "honesty": (
            "Paper lab only. Never claim EDGE_CANDIDATE or profitability without "
            "n>=30 cohort and positive expectancy+PF."
        ),
    }
    (pack_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_dir / "latest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    manifest = build_pack(out_dir=args.out_dir)
    if args.json:
        print(json.dumps(manifest, indent=2, sort_keys=True))
    else:
        print(f"pack_dir={manifest.get('pack_dir')}")
        print(f"colab_url={manifest.get('colab_github_url')}")
        print(f"colab_cli={manifest.get('colab_cli_present')} {manifest.get('colab_cli_version')}")
        print(f"kill_verdict={manifest.get('kill_verdict')} closed_n={manifest.get('closed_n')}")
        print("policy=use_existing_colab_pro_plus_only (never auto-buy CUs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
