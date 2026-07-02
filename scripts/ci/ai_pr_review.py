"""AI PR review — provider-agnostic in-repo equivalent of Sonar/Gitar.

Reads the PR diff + repo context (CLAUDE.md + .claude/rules), asks the
configured LLM provider for a focused review against this repo's risk
mandates, and posts the result as a single rolling PR comment.

Provider chain (first non-empty key wins, in order):
    1. LLM_GATEWAY_API_KEY   -> internal gateway at LLM_GATEWAY_BASE_URL ($0 internal)
    2. GOOGLE_API_KEY        -> gemini-2.5-flash via Google AI Studio (free tier)
    3. ANTHROPIC_API_KEY     -> claude-sonnet-4-6 (paid; ~$0.02/PR)
    4. OPENROUTER_API_KEY    -> claude-sonnet-4-6 routed (last resort; the
                                repo's key is xai-restricted, so this only
                                works with explicit AI_REVIEW_MODEL override)

Override the default model with AI_REVIEW_MODEL. Override the provider
with AI_REVIEW_PROVIDER (one of: llm_gateway, google, anthropic, openrouter).

Comment is identified by a deterministic HTML marker so subsequent runs
PATCH the prior comment instead of stacking.
"""

from __future__ import annotations

import json
import os
import subprocess  # trunk-ignore(bandit/B404)
import sys
import urllib.error
import urllib.request
from pathlib import Path

MAX_DIFF_BYTES = 200_000
MAX_RULES_BYTES = 60_000
COMMENT_MARKER = "<!-- ai-pr-review:v2 -->"

DEFAULT_MODELS = {
    "llm_gateway": "gpt-4o-mini",
    "google": "gemini-2.5-flash",
    "anthropic": "claude-sonnet-4-6",
    "openrouter": "anthropic/claude-sonnet-4-6",
}

REVIEW_SYSTEM_PROMPT = """You are reviewing a pull request against the
IgorGanapolsky/trading repo. Surface only the issues that matter; do not
narrate what the PR does.

Hard mandates (enforce ruthlessly):
- Phil Town Rule #1: don't lose money. Iron Condors on SPY only, 15-20
  delta, 30-45 DTE, defined risk both sides, MAX_CONTRACTS_PER_TRADE=1.
- Never hardcode credentials. Use src.utils.alpaca_client.get_alpaca_credentials.
- TradeGateway is the mandatory checkpoint. No trade may bypass it.
  Direct submit_order calls outside the gateway are violations.
- Closing positions outside the guardian workflow is a hard block
  (.claude/rules/boundary-policy.md).
- Trading remains paper-only under controlled-experiment.md until 30
  trades with positive expectancy.
- North Star is now framed as B2B guardrail SaaS, not paper IC P/L.
  Trading is the demo, not the cash register.

Review priorities (in order):
1. Risk/safety regressions: bypass TradeGateway, kill-switch removal,
   position-close shortcuts, hardcoded credentials, leaked PATs.
2. Bug risk: logic errors, off-by-one, type errors, exception
   swallowing, race conditions in trade execution.
3. CI/security regressions: unpinned actions, missing permissions blocks,
   force-push to main, --no-verify hook bypass without justification.
4. Hypothesis-bound bias: re-introducing the disproved Thursday-only
   entry gate (Bonferroni adj_p=0.190, retired 2026-05-20).
5. P/L misreporting: citing the paired-ledger -$3,958 number without
   acknowledging the ~$2.6K gap to broker truth.
6. Style/quality nits last and briefly.

OUTPUT FORMAT (markdown, terse):
- Top verdict: "APPROVE", "REQUEST_CHANGES", or "COMMENT".
- A "Why" line, one sentence.
- A short list of findings: severity (P0/P1/P2), file:line if
  applicable, one-line description. Skip the list if no findings.
- Optional "Suggested patch" block if the fix is small and obvious.

Do NOT:
- Praise. Do NOT summarize what the PR does. Do NOT thank the author.
- Speculate about runtime behavior you cannot verify from the diff.
- Cite line numbers you didn't see in the diff.
"""


def run(cmd: list[str], check: bool = True) -> str:
    # Args from controlled sources (env vars set by workflow + constants);
    # no shell expansion. Calling system gh/git binaries.
    # trunk-ignore(bandit/B603)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        sys.stderr.write(f"command failed: {' '.join(cmd)}\n{result.stderr}\n")
        sys.exit(1)
    return result.stdout


def select_providers() -> list[tuple[str, str, str]]:
    """Return available (provider, model, api_key) candidates in fallback order.

    Order (2026-05-21): internal gateway first (zero marginal cost,
    routed), then Google Gemini free tier, then Anthropic (paid), then
    OpenRouter (last resort because this repo's key is provider-
    restricted to xai which 404s most non-xai models).
    """
    forced = os.environ.get("AI_REVIEW_PROVIDER", "").strip().lower()
    candidates = (
        ("llm_gateway", "LLM_GATEWAY_API_KEY"),
        ("google", "GOOGLE_API_KEY"),
        ("anthropic", "ANTHROPIC_API_KEY"),
        ("openrouter", "OPENROUTER_API_KEY"),
    )
    if forced:
        candidates = tuple(c for c in candidates if c[0] == forced)
    available: list[tuple[str, str, str]] = []
    for provider, env in candidates:
        key = os.environ.get(env)
        if key:
            model = os.environ.get("AI_REVIEW_MODEL", DEFAULT_MODELS[provider])
            available.append((provider, model, key))
    return available


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


def _http_post_json(url: str, headers: dict, body: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"content-type": "application/json", **headers},
        method="POST",
    )
    # URL is a hardcoded provider endpoint (not user-controlled).
    # trunk-ignore(bandit/B310)
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())


def call_openrouter(model: str, key: str, system: str, user: str) -> str:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": 2048,
    }
    headers = {
        "authorization": f"Bearer {key}",
        "http-referer": "https://github.com/IgorGanapolsky/trading",
        "x-title": "ai-pr-review",
    }
    payload = _http_post_json("https://openrouter.ai/api/v1/chat/completions", headers, body)
    choices = payload.get("choices") or []
    if not choices:
        return ""
    return (choices[0].get("message") or {}).get("content", "").strip()


def call_llm_gateway(model: str, key: str, system: str, user: str) -> str:
    base = os.environ.get("LLM_GATEWAY_BASE_URL", "").rstrip("/")
    if not base:
        sys.stderr.write("LLM_GATEWAY_BASE_URL not set; cannot use llm_gateway\n")
        sys.exit(2)
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": 2048,
    }
    payload = _http_post_json(f"{base}/chat/completions", {"authorization": f"Bearer {key}"}, body)
    choices = payload.get("choices") or []
    if not choices:
        return ""
    return (choices[0].get("message") or {}).get("content", "").strip()


def call_anthropic(model: str, key: str, system: str, user: str) -> str:
    body = {
        "model": model,
        "max_tokens": 2048,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    headers = {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
    }
    payload = _http_post_json("https://api.anthropic.com/v1/messages", headers, body)
    blocks = payload.get("content") or []
    return "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()


def call_google(model: str, key: str, system: str, user: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    body = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"parts": [{"text": user}]}],
        "generationConfig": {"maxOutputTokens": 2048},
    }
    payload = _http_post_json(url, {}, body)
    cands = payload.get("candidates") or []
    if not cands:
        return ""
    parts = (cands[0].get("content") or {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts).strip()


PROVIDER_DISPATCH = {
    "openrouter": call_openrouter,
    "llm_gateway": call_llm_gateway,
    "anthropic": call_anthropic,
    "google": call_google,
}


def call_review(system: str, user: str) -> tuple[str, str, str]:
    providers = select_providers()
    if not providers:
        sys.stderr.write(
            "no LLM provider key in env. set one of OPENROUTER_API_KEY, "
            "LLM_GATEWAY_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY.\n"
        )
        return "none", "", ""

    failures: list[str] = []
    for provider, model, key in providers:
        print(f"using provider={provider} model={model}", file=sys.stderr)
        try:
            text = PROVIDER_DISPATCH[provider](model, key, system, user)
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", errors="replace")
            failures.append(f"{provider} api error {e.code}: {msg}")
            sys.stderr.write(f"{failures[-1]}\n")
            continue
        if text:
            return provider, model, text
        failures.append(f"{provider} returned empty review")
        sys.stderr.write(f"{failures[-1]}\n")

    sys.stderr.write("all AI review providers failed:\n" + "\n".join(failures) + "\n")
    return "none", "", ""


def find_existing_comment(repo: str, pr: str) -> int | None:
    raw = run(["gh", "api", f"repos/{repo}/issues/{pr}/comments", "--paginate"])
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
    provider, model, review = call_review(REVIEW_SYSTEM_PROMPT, user_msg)
    if not review:
        print("empty review from model — skipping post")
        return 0

    footer = f"\n\n---\n*Reviewed by `{model}` via `{provider}`.*"
    post_or_update_comment(repo, pr, review + footer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
