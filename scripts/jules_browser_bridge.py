#!/usr/bin/env python3
"""Google Jules Browser Automation Bridge.

Provides programmatic CLI and Python API access to Google Jules (jules.google.com)
via macOS Google Chrome AppleScript automation under authenticated Google SSO
(iganapolsky@gmail.com).

Capabilities:
- Health check & session verification
- Extract proactive suggestions across all categories (Performance, Security, Code Health, Testing, Cleanup)
- Inspect suggestion details (file location, description, rationale, code context)
- Dispatch suggestions to Jules cloud runner with automatic safety constraints
- List and monitor recent Jules sessions
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess  # nosec B404
import sys
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any, Sequence

CHROME_APP = "Google Chrome"
JULES_BASE_URL = "https://jules.google.com"


@dataclass(frozen=True)
class JulesSuggestion:
    index: int
    title: str
    category: str
    location: str | None = None
    description: str | None = None
    rationale: str | None = None
    code_context: str | None = None


def execute_chrome_js(raw_js: str, target_url_prefix: str = JULES_BASE_URL) -> tuple[int, str, str]:
    """Execute JavaScript in the first Chrome tab matching target_url_prefix.

    Wraps execution in encodeURIComponent to prevent AppleScript newline/quote mangling.
    """
    wrapped_js = f"""
    (() => {{
        try {{
            const result = (() => {{ {raw_js} }})();
            if (result === undefined || result === null) return '__NULL__';
            if (typeof result === 'object') return encodeURIComponent(JSON.stringify(result));
            return encodeURIComponent(String(result));
        }} catch(e) {{
            return encodeURIComponent(JSON.stringify({{__error__: e.toString()}}));
        }}
    }})()
    """
    b64_js = base64.b64encode(wrapped_js.encode("utf-8")).decode("utf-8")
    applescript = f"""
    tell application "{CHROME_APP}"
        set targetTab to missing value
        repeat with w in windows
            repeat with t in tabs of w
                if URL of t starts with "{target_url_prefix}" then
                    set targetTab to t
                    exit repeat
                end if
            end repeat
            if targetTab is not missing value then exit repeat
        end repeat
        if targetTab is missing value then
            return "NO_JULES_TAB"
        end if
        tell targetTab
            return execute javascript "eval(atob('{b64_js}'))"
        end tell
    end tell
    """
    proc = subprocess.run(  # nosec B603
        ["osascript", "-e", applescript],
        capture_output=True,
        text=True,
    )
    raw_stdout = proc.stdout.strip()
    if raw_stdout == "NO_JULES_TAB":
        return proc.returncode, "NO_JULES_TAB", proc.stderr.strip()
    if proc.returncode != 0:
        return proc.returncode, raw_stdout, proc.stderr.strip()

    decoded = urllib.parse.unquote(raw_stdout)
    if decoded == "__NULL__":
        return 0, "", ""
    return 0, decoded, proc.stderr.strip()


def check_jules_health() -> dict[str, Any]:
    """Check if Jules tab is open, authenticated, and responsive."""
    js = r"""
        return {
            status: "ok",
            url: window.location.href,
            title: document.title,
            bodyLength: (document.body && document.body.innerText) ? document.body.innerText.length : 0,
            hasSuggestions: document.querySelectorAll('.suggestion-summary').length > 0,
            filterChips: Array.from(document.querySelectorAll('swebot-filter-chip')).map(c => c.textContent.replace(/\s+/g, ' ').trim())
        };
    """
    retcode, stdout, stderr = execute_chrome_js(js)
    if stdout == "NO_JULES_TAB":
        return {
            "status": "disconnected",
            "message": "No active Google Chrome tab found starting with https://jules.google.com",
            "fix": "Open Google Chrome and navigate to https://jules.google.com/repo/github/IgorGanapolsky/trading/suggestions",
        }
    if retcode != 0:
        return {"status": "error", "error": stderr or "Failed to run AppleScript"}

    try:
        data = json.loads(stdout)
        if isinstance(data, dict) and "__error__" in data:
            return {"status": "error", "message": data["__error__"]}
        return data
    except json.JSONDecodeError:
        return {"status": "error", "raw_output": stdout}


def list_jules_suggestions(category_filter: str | None = None) -> list[dict[str, Any]]:
    """List suggestions currently available in Jules UI."""
    extract_js = r"""
        const items = Array.from(document.querySelectorAll('.suggestion-item'));
        return items.map((item, idx) => {
            const summary = item.querySelector('.suggestion-summary');
            const text = summary ? summary.textContent.replace(/\s+/g, ' ').trim() : item.textContent.replace(/\s+/g, ' ').trim();
            let category = "cleanup";
            if (text.includes("speed")) category = "performance";
            else if (text.includes("healing")) category = "code_health";
            else if (text.includes("science")) category = "testing";
            else if (text.includes("security")) category = "security";
            else if (text.includes("checklist")) category = "cleanup";

            // Clean title
            let title = text
                .replace(/^chevron_right\s*/i, "")
                .replace(/\s*(speed|healing|science|security|checklist)\s*(Start|Review)\s*(edit)?close$/i, "")
                .trim();

            let location = null;
            let description = null;
            let rationale = null;

            const detail = item.querySelector('.suggestion-details');
            if (detail) {
                const dText = detail.textContent.replace(/\s+/g, ' ').trim();
                const locMatch = dText.match(/Location\s+([^\s]+)/i);
                if (locMatch) location = locMatch[1];
                const descMatch = dText.match(/Description\s*(.*?)(?=Location|Rationale|Code context|$)/i);
                if (descMatch) description = descMatch[1].trim();
                const ratMatch = dText.match(/Rationale\s*(.*?)(?=Location|Description|Code context|$)/i);
                if (ratMatch) rationale = ratMatch[1].trim();
            }

            return {
                index: idx,
                title: title,
                category: category,
                location: location,
                description: description,
                rationale: rationale
            };
        });
    """
    retcode, stdout, _ = execute_chrome_js(extract_js)
    if retcode != 0 or stdout == "NO_JULES_TAB":
        return []
    try:
        items = json.loads(stdout)
        if isinstance(items, dict) and "__error__" in items:
            return []
        if not isinstance(items, list):
            return []

        if category_filter and category_filter.lower() != "all":
            norm = category_filter.lower().replace("-", "_")
            items = [item for item in items if item.get("category") == norm]

        return items
    except json.JSONDecodeError:
        return []


def expand_suggestion(index: int) -> dict[str, Any] | None:
    """Expand and retrieve full metadata for a specific suggestion."""
    expand_js = rf"""
        const items = Array.from(document.querySelectorAll('.suggestion-item'));
        if ({index} >= items.length) return {{__error__: "index out of bounds"}};
        const item = items[{index}];
        const details = item.querySelector('.suggestion-details');
        if (!details) {{
            const btn = item.querySelector('.expand-button');
            if (btn) btn.click();
        }}
        return "CLICKED";
    """
    execute_chrome_js(expand_js)
    time.sleep(0.4)

    read_js = rf"""
        const items = Array.from(document.querySelectorAll('.suggestion-item'));
        if ({index} >= items.length) return null;
        const item = items[{index}];
        const summary = item.querySelector('.suggestion-summary');
        const text = summary ? summary.textContent.replace(/\s+/g, ' ').trim() : '';
        const details = item.querySelector('.suggestion-details');
        const dText = details ? details.textContent.replace(/\s+/g, ' ').trim() : '';

        let location = null;
        let description = null;
        let rationale = null;

        const locMatch = dText.match(/Location\s+([^\s]+)/i);
        if (locMatch) location = locMatch[1];
        const descMatch = dText.match(/Description\s*(.*?)(?=Location|Rationale|Code context|$)/i);
        if (descMatch) description = descMatch[1].trim();
        const ratMatch = dText.match(/Rationale\s*(.*?)(?=Location|Description|Code context|$)/i);
        if (ratMatch) rationale = ratMatch[1].trim();

        return {{
            index: {index},
            raw_summary: text,
            location: location,
            description: description,
            rationale: rationale,
            full_detail_text: dText
        }};
    """
    _, stdout, _ = execute_chrome_js(read_js)
    try:
        data = json.loads(stdout)
        if isinstance(data, dict) and "__error__" in data:
            return None
        return data
    except json.JSONDecodeError:
        return None


def dispatch_suggestion(index: int, custom_instructions: str | None = None) -> dict[str, Any]:
    """Load suggestion into composer, append safety constraints, and submit to Jules cloud."""
    # 1. Click edit/up-arrow button to load prompt into composer
    load_js = f"""
        const summaries = Array.from(document.querySelectorAll('.suggestion-summary'));
        if ({index} >= summaries.length) return {{__error__: "index out of bounds"}};
        const s = summaries[{index}];
        const editBtn = s.querySelector('.action-button.up-arrow') || s.querySelector('.action-button');
        if (!editBtn) return {{__error__: "no action button found"}};
        editBtn.click();
        return "LOADED";
    """
    _, load_res, _ = execute_chrome_js(load_js)
    if "LOADED" not in load_res:
        return {"status": "error", "message": f"Failed to load suggestion {index}: {load_res}"}

    time.sleep(0.5)

    # 2. Append safety constraints
    safety_rule = (
        "\n\n## 🛡️ MANDATORY SAFETY & HARMONIZATION CONSTRAINTS:\n"
        "1. TEST ISOLATION: Never write ephemeral test artifacts to repo manifests "
        "(e.g., data/audit/ingestion_version_manifest.json). Always use tmp_path in tests.\n"
        "2. IDENTITY: Never reference corporate identities (@ecisolutions.com). Maintain IgorGanapolsky.\n"
        "3. VERIFICATION: Ensure all local gates pass (`make check`).\n"
    )
    if custom_instructions:
        safety_rule += f"4. ADDITIONAL OPERATOR GUIDANCE: {custom_instructions}\n"

    b64_safety = base64.b64encode(safety_rule.encode("utf-8")).decode("utf-8")
    append_js = f"""
        const ce = document.querySelector('[contenteditable="true"]');
        if (!ce) return {{__error__: "no composer contenteditable found"}};
        const additional = atob('{b64_safety}');
        ce.innerText = ce.innerText + additional;
        ce.dispatchEvent(new Event('input', {{ bubbles: true }}));
        return "APPENDED";
    """
    execute_chrome_js(append_js)
    time.sleep(0.3)

    # 3. Click start task button
    submit_js = r"""
        const btn = document.querySelector('.start-task-button');
        if (!btn) return {__error__: "start-task-button not found"};
        btn.click();
        return "SUBMITTED";
    """
    _, submit_res, _ = execute_chrome_js(submit_js)
    if "SUBMITTED" in submit_res:
        return {
            "status": "success",
            "message": f"Suggestion {index} successfully dispatched to Jules cloud worker.",
            "dispatched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    return {"status": "error", "message": f"Failed to submit task: {submit_res}"}


def list_recent_sessions() -> list[dict[str, str]]:
    """List recent sessions visible in Jules sidebar."""
    js = r"""
        const links = Array.from(document.querySelectorAll('a[href*="session"]'));
        return links.map(l => ({
            id: (l.href.match(/session\/(\d+)/) || [])[1] || "",
            url: l.href,
            title: l.textContent.replace(/\s+/g, ' ').trim()
        }));
    """
    _, stdout, _ = execute_chrome_js(js)
    try:
        data = json.loads(stdout)
        if isinstance(data, list):
            return data
        return []
    except json.JSONDecodeError:
        return []


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Google Jules Browser Automation Bridge",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Health
    subparsers.add_parser("health", help="Check connection to Google Jules tab in Chrome")

    # List
    list_p = subparsers.add_parser("list", help="List available suggestions")
    list_p.add_argument(
        "--filter",
        choices=["all", "performance", "security", "code_health", "testing", "cleanup"],
        default="all",
        help="Filter suggestions by category",
    )
    list_p.add_argument("--json", action="store_true", help="Output raw JSON")

    # Show
    show_p = subparsers.add_parser("show", help="Show full details for a suggestion")
    show_p.add_argument("index", type=int, help="Suggestion index")
    show_p.add_argument("--json", action="store_true", help="Output raw JSON")

    # Start
    start_p = subparsers.add_parser("start", help="Dispatch a suggestion to Jules cloud")
    start_p.add_argument("index", type=int, help="Suggestion index to launch")
    start_p.add_argument(
        "--instructions", type=str, default=None, help="Additional prompt instructions"
    )

    # Sessions
    subparsers.add_parser("sessions", help="List recent Jules sessions")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "health":
        res = check_jules_health()
        print(json.dumps(res, indent=2))
        return 0 if res.get("status") == "ok" else 1

    elif args.command == "list":
        items = list_jules_suggestions(args.filter)
        if args.json:
            print(json.dumps(items, indent=2))
        else:
            print(f"Found {len(items)} suggestions (Filter: {args.filter}):")
            for item in items:
                idx = item.get("index")
                cat = item.get("category", "unknown")
                title = item.get("title")
                loc = item.get("location") or "N/A"
                print(f"[{idx:2d}] [{cat.upper():12s}] {title} ({loc})")
        return 0

    elif args.command == "show":
        details = expand_suggestion(args.index)
        if not details:
            print(f"Suggestion {args.index} not found.", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(details, indent=2))
        else:
            print(f"=== Suggestion [{args.index}] Details ===")
            print(f"Location:    {details.get('location')}")
            print(f"Description: {details.get('description')}")
            print(f"Rationale:   {details.get('rationale')}")
            print(f"Full Text:\n{details.get('full_detail_text')}")
        return 0

    elif args.command == "start":
        res = dispatch_suggestion(args.index, custom_instructions=args.instructions)
        print(json.dumps(res, indent=2))
        return 0 if res.get("status") == "success" else 1

    elif args.command == "sessions":
        sessions = list_recent_sessions()
        print(json.dumps(sessions, indent=2))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
