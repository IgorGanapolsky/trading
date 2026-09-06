# Scorecard remediation (AGENT-583)

GitHub **code scanning on `branch:main`** for this repo is OpenSSF Scorecard,
not application CodeQL CVEs. CodeQL currently has 0 open alerts.

Same-day docs-only commits (`e7f1f9b69`, `f1681c8de`) did not move write
tokens to job scope and did not pin pip. AGENT-581 SHA-pinned Actions.
This change is the remaining contract.

## What the gate now fails closed on

- Missing top-level `permissions` or any top-level `write` scope
- Unhashed `pip install` in workflows (use `uv sync --frozen`)
- Unpinned `FROM` images (digest required)
- Workflows creating GitHub Issues (LL-569)

Owner: `scripts/scorecard_hygiene.py` + `.github/workflows/scorecard-hygiene.yml`.

## What stays open on purpose

- **Branch-Protection / enforce_admins**: owner-token agent merges would stop.
  Do not enable without a dedicated bypass actor. Scorecard will keep this High.
- **Code-Review trailing 30 PRs**: AI review now submits a GitHub review event.
  The Scorecard number only moves after ~30 reviewed merges.
- **CII Best Practices badge**: external form, not a code change.
- **GO-2026-5932** (`golang.org/x/crypto/openpgp` unmaintained): indirect via
  Google ADK. Bumping `x/crypto` clears the ssh/net/text OSV IDs; openpgp stays
  until the upstream module splits.

Do not treat GitHub Issues as the Scorecard dashboard.
