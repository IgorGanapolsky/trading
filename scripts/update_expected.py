#!/usr/bin/env python3
import json
import pathlib
import re
import subprocess
import sys

# Usage: python scripts/update_expected.py <out-json>
# <out-json> is produced by run_smoke.sh

if len(sys.argv) < 2:
    print("Usage: update_expected.py <out-json>")
    sys.exit(1)

OUT_JSON = sys.argv[1]
TEST_FILE = "tests/smoke_backtest.py"

try:
    with open(OUT_JSON) as f:
        data = json.load(f)
        pnl = float(data["pnl"])
except Exception as e:
    print(f"Error reading {OUT_JSON}: {e}")
    sys.exit(1)

p = pathlib.Path(TEST_FILE)
if not p.exists():
    # Try finding it relative to repo root if run from elsewhere
    repo_root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"]).strip().decode()
    p = pathlib.Path(repo_root) / TEST_FILE
    if not p.exists():
        print(f"Could not find {TEST_FILE}")
        sys.exit(1)

txt = p.read_text()
# replace EXPECTED = <number>  (assumes unique line)
# Allows scientific notation or floats
new_txt = re.sub(r"(EXPECTED\s*=\s*)([0-9.+-eE]+)", rf"\1{pnl:.6f}", txt, count=1)

if new_txt == txt:
    print("No EXPECTED line replaced or value identical; nothing to do.")
    # Check if value is identical or just regex failed
    pass
else:
    p.write_text(new_txt)
    print(f"Updated EXPECTED to {pnl:.6f} in {TEST_FILE}")

    # Check if we should push
    # This requires secrets.CI_WRITE_TOKEN to be present and used in git config in CI
    # We will only print the git commands here for now, or execute them if configured.
    # The user script snippet included subprocess calls.

    # Check if we are in CI environment
    import os

    if os.getenv("CI") == "true" and os.getenv("GIT_AUTHOR_EMAIL"):
        try:
            subprocess.run(
                ["git", "config", "user.email", os.environ["GIT_AUTHOR_EMAIL"]], check=True
            )
            subprocess.run(
                ["git", "config", "user.name", os.environ["GIT_AUTHOR_NAME"]], check=True
            )
            subprocess.run(["git", "add", str(p)], check=True)
            subprocess.run(
                ["git", "commit", "-m", f"ci: update deterministic EXPECTED to {pnl:.6f}"],
                check=True,
            )
            subprocess.run(["git", "push", "origin", "main"], check=True)
            print("Pushed update to remote.")
        except subprocess.CalledProcessError as e:
            print(f"Git operation failed: {e}")
            sys.exit(1)
