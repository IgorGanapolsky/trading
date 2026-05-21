"""Claude AI PR review — in-repo equivalent of Sonar/Gitar.

Reads the PR diff + repo context (CLAUDE.md / .claude/rules), asks Claude
to produce a focused review against this repo's coding standards and risk
mandates, and posts the result as a single PR comment with a deterministic
marker so subsequent runs replace the prior comment instead of stacking.

Triggered by .github/workflows/claude-pr-review.yml on pull_request open /
reopened / ready_for_review. Required env:
    ANTHROPIC_API_KEY  - Anthropic API key
    GH_TOKEN           - GitHub token with pull-requests:write
    PR_NUMBER          - The pull request number to review
    REPO               - "owner/name"
    PR_BASE_SHA        - Base ref SHA of the PR
    PR_HEAD_SHA        - Head ref SHA of the PR
"""

from __future__ import annotations

import json
import os
import subprocess  # nosec B404 — used to call `gh`/`git` CLIs from CI with controlled args
import sys
import urllib.request
from pathlib import Path

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("CLAUDE_REVIEW_MODEL", "claude-sonnet-4-6")
MAX_DIFF_BYTES = 200_000
MAX_RULES_BYTES = 60_000
COMMENT_MARKER = "<!-- claude-pr-review:v1 -->"

REVIEW_SYSTEM_PROMPT = """You are reviewing a pull request against the
IgorGanapolsky/trading repo. You read the diff and surface ONLY the issues
that matter; you do not narrate what the PR does.

Hard mandates from this repo (enforce ruthlessly):
- Phil Town Rule #1: don't lose money. Iron Condors on SPY only, 15-20
  delta, 30-45 DTE, defined risk both sides, MAX_CONTRACTS_PER_TRADE=1.
- Never hardcode credentials. Use src.utils.alpaca_client.get_alpaca_credentials.
- TradeGateway is the mandatory checkpoint — no trade may bypass it.
  All direct submit_order calls outside the gateway are violations.
- Closing positions outside the guardian workflow is a hard block
  (.claude/rules/boundary-policy.md).
- Trading remains paper-only under the controlled-experiment.md gate
  until 30 trades with positive expectancy.
- North Star ($6K/mo after-tax) is now framed as B2B guardrail SaaS,
  not paper IC P/L. The trading account is the demo, not the cash register.

Review priorities (in order):
1. Risk/safety regressions: new ways to bypass TradeGateway, kill-switch
   removal, position-close shortcuts, hardcoded credentials, leaked PATs.
2. Bug risk: logic errors, off-by-one, type errors, exception swallowing,
   race conditions in trade execution.
3. CI/security regressions: unpinned actions, missing permissions blocks,
   force-push to main, --no-verify hook bypass without justification.
4. Hypothesis-bound bias: enforcing or re-introducing the disproved
   Thursday-only entry gate (Bonferroni adj_p=0.190, retired 2026-05-20).
5. P/L misreporting: citing the paired-ledger -$3,958 number without
   acknowledging the ~$2.6K gap to broker truth.
6. Style/quality nits last and briefly.

OUTPUT FORMAT (markdown, terse):
- A one-line top verdict: "APPROVE", "REQUEST_CHANGES", or "COMMENT".
- A "Why" line, one sentence.
- A short list of findings, each with: severity (P0/P1/P2), file:line if
  applicable, and a one-line description. Skip the list if there are no
  findings.
- Optional "Suggested patch" block with concrete code if the fix is small
  and obvious.

Do NOT:
- Praise. Do NOT summarize what the PR does. Do NOT thank the author.
- Speculate about runtime behavior you cannot verify from the diff.
- Cite line numbers you didn't see in the diff.
"""


def run(cmd: list[str], check: bool = True) -> str:
    # Args are constructed from controlled sources (env vars set by the
    # workflow and module-level constants); no shell expansion. Calling
    # the system gh/git binaries via the resolved PATH on the runner.
    # trunk-ignore(bandit/B603)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        sys.stderr.write(f"command failed: {' '.join(cmd)}\n{result.stderr}\n")
        sys.exit(1)
    return result.stdout


def load_context() -> str:
    parts: list[str] = []
    candidates = [
        Path("CLAUDE.md"),
        Path(".claude/CLAUDE.md"),
        Path(".claude/rules/risk-management.md"),
        Path(".claude/rules/controlled-experiment.md"),
        Path(".claude/rules/boundary-policy.md"),
        Path(".claude/rules/trading.md"),
    ]
    budget = MAX_RULES_BYTES
    for p in candidates:
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8")[: budget // len(candidates)]
        parts.append(f"# {p}\n{text}")
        budget -= len(text)
        if budget <= 0:
            break
    return "\n\n".join(parts)


def get_diff(base: str, head: str) -> str:
    diff = run(["git", "diff", "--unified=3", f"{base}...{head}"])
    if len(diff.encode("utf-8")) > MAX_DIFF_BYTES:
        diff = diff[:MAX_DIFF_BYTES] + "\n\n[diff truncated at 200K bytes]"
    return diff


def call_claude(system: str, user: str) -> str:
    key = os.environ["ANTHROPIC_API_KEY"]
    body = json.dumps(
        {
            "model": MODEL,
            "max_tokens": 2048,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        # URL is the hardcoded constant API_URL (https://api.anthropic.com);
        # not user-controlled, scheme is fixed https.
        # trunk-ignore(bandit/B310)
        with urllib.request.urlopen(req, timeout=90) as r:
            payload = json.loads(r.read())
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", errors="replace")
        sys.stderr.write(f"anthropic api error {e.code}: {msg}\n")
        sys.exit(2)
    blocks = payload.get("content") or []
    text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
    return text.strip()


def find_existing_comment(repo: str, pr: str) -> int | None:
    raw = run(
        [
            "gh",
            "api",
            f"repos/{repo}/issues/{pr}/comments",
            "--paginate",
        ]
    )
    try:
        comments = json.loads(raw)
    except json.JSONDecodeError:
        return None
    for c in comments:
        if COMMENT_MARKER in (c.get("body") or ""):
            return c["id"]
    return None


def post_or_update_comment(repo: str, pr: str, body: str) -> None:
    body_full = f"{COMMENT_MARKER}\n{body}"
    existing = find_existing_comment(repo, pr)
    if existing is not None:
        run(
            [
                "gh",
                "api",
                "-X",
                "PATCH",
                f"repos/{repo}/issues/comments/{existing}",
                "-f",
                f"body={body_full}",
            ]
        )
        print(f"updated existing comment {existing}")
    else:
        run(
            [
                "gh",
                "api",
                "-X",
                "POST",
                f"repos/{repo}/issues/{pr}/comments",
                "-f",
                f"body={body_full}",
            ]
        )
        print("posted new comment")


def main() -> int:
    pr = os.environ["PR_NUMBER"]
    repo = os.environ["REPO"]
    base = os.environ["PR_BASE_SHA"]
    head = os.environ["PR_HEAD_SHA"]

    diff = get_diff(base, head)
    if not diff.strip():
        print("empty diff — skipping review")
        return 0

    context = load_context()
    user_msg = (
        "Review the following pull request diff under the repo mandates above.\n\n"
        f"## Repo context (CLAUDE.md + key rules)\n\n{context}\n\n"
        f"## PR #{pr} diff\n\n```diff\n{diff}\n```\n"
    )
    review = call_claude(REVIEW_SYSTEM_PROMPT, user_msg)
    if not review:
        print("empty review from model — skipping post")
        return 0

    post_or_update_comment(repo, pr, review)
    return 0


if __name__ == "__main__":
    sys.exit(main())
