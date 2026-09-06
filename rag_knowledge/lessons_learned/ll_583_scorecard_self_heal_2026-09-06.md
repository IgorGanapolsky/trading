# LL-583 Scorecard 65-open was pip + top-level GITHUB_TOKEN write (2026-09-06)

## Lesson

GitHub Security → Code scanning `is:open branch:main` on this public repo
was OpenSSF Scorecard (65 alerts), not CodeQL. The CodeQL banner was a
tool status line; analyses were succeeding with 0 open CodeQL alerts.

Same-day "security scan remediation" commits added CODEOWNERS and a plan
that told agents to prefer floating action versions over SHAs — the
opposite of AGENT-581. Token-Permissions stayed High because write scopes
were still **top-level**. Pinned-Dependencies stayed Medium because
workflows still ran unhashed `pip install`.

## Prevention

`scripts/scorecard_hygiene.py` fails CI when a workflow has top-level
write, unhashed pip, or an unpinned Dockerfile FROM. Workflows install
with SHA-pinned `astral-sh/setup-uv` + `uv sync --frozen`. Never open
GitHub Issues for Scorecard (LL-569).

## Do not

- Enable `enforce_admins` to "clear" Branch-Protection (breaks owner-token merge)
- Treat 65 Scorecard rows as 65 application CVEs
- Claim 0 open alerts before Scorecard re-uploads SARIF on `main`
