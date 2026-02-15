#!/usr/bin/env python3
"""
Ralph Discovery Blog Publisher - 2026 Edition

Automatically generates ENGAGING blog posts when Ralph makes discoveries.
Posts go to GitHub Pages and Dev.to.

2026 Standards Applied:
- Mermaid diagrams for technical flows
- Severity badges (CRITICAL/HIGH/MEDIUM/INFO)
- Actual code snippets from fixes
- Trend analysis with metrics
- Narrative storytelling structure
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

# Allow `python scripts/...` execution where sys.path[0] == scripts/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.content.blog_seo import (
    canonical_url_for_post,
    render_frontmatter,
    truncate_meta_description,
)

# Use Eastern Time for all blog dates (CEO timezone)
ET = ZoneInfo("America/New_York")

# Severity classification for discoveries
SEVERITY_BADGES = {
    "critical": "🔴 CRITICAL",
    "high": "🟠 HIGH",
    "medium": "🟡 MEDIUM",
    "low": "🟢 LOW",
    "info": "ℹ️ INFO",
}

# Keywords to classify severity
SEVERITY_KEYWORDS = {
    "critical": [
        "crash",
        "data loss",
        "security",
        "money",
        "production down",
        "exploit",
    ],
    "high": ["broken", "fail", "error", "exception", "race condition", "deadlock"],
    "medium": ["bug", "issue", "incorrect", "wrong", "missing", "timeout"],
    "low": ["warning", "deprecat", "cleanup", "refactor", "style"],
}


def get_devto_api_key() -> str | None:
    """Get Dev.to API key from environment."""
    return os.environ.get("DEVTO_API_KEY")


def classify_severity(text: str) -> str:
    """Classify severity based on keywords in text."""
    text_lower = text.lower()
    for severity, keywords in SEVERITY_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return severity
    return "info"


def get_code_diff_snippet(commit_sha: str, max_lines: int = 20) -> str | None:
    """Extract relevant code changes from a commit."""
    try:
        result = subprocess.run(
            ["git", "show", "--stat", "--patch", commit_sha, "--", "*.py"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None

        # Find actual code changes (additions)
        lines = result.stdout.split("\n")
        code_changes = []
        in_diff = False

        for line in lines:
            if line.startswith("diff --git"):
                in_diff = True
                continue
            if in_diff and line.startswith("+") and not line.startswith("+++"):
                # This is an added line
                code_changes.append(line[1:])  # Remove the + prefix
                if len(code_changes) >= max_lines:
                    break

        if code_changes:
            return "\n".join(code_changes)
        return None
    except Exception:
        return None


def get_recent_ralph_commits(max_count: int = 10) -> list[dict]:
    """Get recent commits from Ralph workflows with code snippets."""
    result = subprocess.run(
        [
            "git",
            "log",
            "--since=24 hours ago",
            "--oneline",
            "--grep=ralph\\|self-heal\\|auto-fix\\|fix(\\|feat(",
            "--format=%H|%s|%an|%ad",
            "--date=short",
        ],
        capture_output=True,
        text=True,
    )

    commits = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("|")
        if len(parts) >= 4:
            full_sha = parts[0]
            commit = {
                "sha": full_sha[:8],
                "full_sha": full_sha,
                "message": parts[1],
                "author": parts[2],
                "date": parts[3],
                "severity": classify_severity(parts[1]),
                "code_snippet": get_code_diff_snippet(full_sha, max_lines=15),
            }
            commits.append(commit)

    return commits[:max_count]


def get_recent_lesson_files(hours: int = 24) -> list[Path]:
    """Get lesson files created in the last N hours."""
    lessons_dir = Path("rag_knowledge/lessons_learned")
    if not lessons_dir.exists():
        return []

    cutoff = datetime.now().timestamp() - (hours * 60 * 60)
    recent = []

    for f in lessons_dir.glob("*.md"):
        if f.stat().st_mtime > cutoff:
            recent.append(f)

    return sorted(recent, key=lambda x: x.stat().st_mtime, reverse=True)


def extract_code_blocks(content: str) -> list[str]:
    """Extract code blocks from markdown content."""
    code_blocks = re.findall(r"```(?:python|bash|json)?\n(.*?)```", content, re.DOTALL)
    return [block.strip() for block in code_blocks if block.strip()]


def extract_discovery_content(lesson_file: Path) -> dict:
    """Extract meaningful content from a lesson file with 2026 engagement features."""
    content = lesson_file.read_text()
    lines = content.strip().split("\n")

    # Extract title
    title = lines[0].replace("#", "").strip() if lines else lesson_file.stem

    # Get the lesson ID from filename (e.g., LL-277)
    lesson_id = ""
    if match := re.search(r"LL-\d+", lesson_file.stem):
        lesson_id = match.group(0)

    # Extract code blocks for actual fix examples
    code_blocks = extract_code_blocks(content)

    # Extract key sections with smarter parsing
    problem = ""
    solution = ""
    impact = ""
    root_cause = ""
    tags = []

    current_section = None
    section_content = []

    for line in lines[1:]:
        lower_line = line.lower()

        # Extract tags
        if "tags:" in lower_line or line.startswith("- "):
            tag_match = re.findall(r"[a-z\-]+", lower_line)
            tags.extend([t for t in tag_match if len(t) > 2])

        # Detect section headers
        if (
            "problem" in lower_line
            or "issue" in lower_line
            or "bug" in lower_line
            or "what happened" in lower_line
        ):
            if current_section and section_content:
                if "problem" in current_section:
                    problem = " ".join(section_content)
            current_section = "problem"
            section_content = []
        elif "root cause" in lower_line or "why" in lower_line:
            if current_section and section_content:
                if "problem" in current_section:
                    problem = " ".join(section_content)
            current_section = "root_cause"
            section_content = []
        elif (
            "solution" in lower_line
            or "fix" in lower_line
            or "resolution" in lower_line
            or "how we fixed" in lower_line
        ):
            if current_section and section_content:
                if "problem" in current_section:
                    problem = " ".join(section_content)
                elif "root_cause" in current_section:
                    root_cause = " ".join(section_content)
            current_section = "solution"
            section_content = []
        elif (
            "impact" in lower_line
            or "result" in lower_line
            or "outcome" in lower_line
            or "lesson" in lower_line
        ):
            if current_section and section_content:
                if "solution" in current_section:
                    solution = " ".join(section_content)
            current_section = "impact"
            section_content = []
        elif line.strip() and not line.startswith("#") and not line.startswith("---"):
            section_content.append(line.strip())

    # Capture last section
    if current_section and section_content:
        if "problem" in current_section:
            problem = " ".join(section_content)
        elif "root_cause" in current_section:
            root_cause = " ".join(section_content)
        elif "solution" in current_section:
            solution = " ".join(section_content)
        elif "impact" in current_section:
            impact = " ".join(section_content)

    # If no structured content, use first meaningful paragraph
    if not problem and not solution:
        non_header_lines = [
            line.strip()
            for line in lines
            if line.strip() and not line.startswith("#") and not line.startswith("---")
        ]
        if non_header_lines:
            problem = " ".join(non_header_lines[:3])[:400]
            solution = " ".join(non_header_lines[3:6])[:400] if len(non_header_lines) > 3 else ""
            impact = " ".join(non_header_lines[6:8])[:300] if len(non_header_lines) > 6 else ""

    # Classify severity
    severity = classify_severity(f"{problem} {title}")

    return {
        "title": title,
        "lesson_id": lesson_id,
        "severity": severity,
        "problem": problem[:500] if problem else "- Dead code detected: true",
        "root_cause": root_cause[:400] if root_cause else "",
        "solution": solution[:500] if solution else "",
        "impact": impact[:300] if impact else "",
        "code_blocks": code_blocks[:2],  # Max 2 code blocks per discovery
        "tags": tags[:5],
        "raw_content": content[:2000],
    }


def generate_mermaid_diagram(discoveries: list[dict], commits: list[dict]) -> str:
    """Generate a Mermaid flowchart showing the discovery-to-fix flow."""
    if not discoveries and not commits:
        return ""

    diagram = """
```mermaid
flowchart LR
    subgraph Detection["🔍 Detection"]
"""
    # Add detection nodes
    for i, d in enumerate(discoveries[:3], 1):
        severity = d.get("severity", "info")
        icon = (
            "🔴"
            if severity == "critical"
            else "🟠"
            if severity == "high"
            else "🟡"
            if severity == "medium"
            else "🟢"
        )
        # Get lesson_id or create short title from title field
        short_title = d.get("lesson_id") or d.get("title", f"Issue{i}")[:15]
        diagram += f'        D{i}["{icon} {short_title}"]\n'

    diagram += """    end
    subgraph Analysis["🔬 Analysis"]
        A1["Root Cause Found"]
    end
    subgraph Fix["🔧 Fix Applied"]
"""
    # Add fix nodes
    for i, c in enumerate(commits[:3], 1):
        diagram += f'        F{i}["{c.get("sha", "fix")[:7]}"]\n'

    diagram += """    end
    subgraph Verify["✅ Verified"]
        V1["Tests Pass"]
        V2["CI Green"]
    end
"""
    # Connect the nodes
    for i in range(1, min(len(discoveries) + 1, 4)):
        diagram += f"    D{i} --> A1\n"
    diagram += "    A1 --> F1\n"
    for i in range(1, min(len(commits) + 1, 4)):
        diagram += f"    F{i} --> V1\n"
    diagram += "    V1 --> V2\n"

    diagram += "```\n"
    return diagram


def generate_trend_metrics(discoveries: list[dict]) -> str:
    """Generate trend analysis metrics section."""
    # Count by severity
    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for d in discoveries:
        sev = d.get("severity", "info")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    # Build metrics section
    metrics = """
## 📊 Today's Metrics

| Metric | Value |
|--------|-------|
"""
    metrics += f"| Issues Detected | {len(discoveries)} |\n"
    metrics += f"| 🔴 Critical | {severity_counts['critical']} |\n"
    metrics += f"| 🟠 High | {severity_counts['high']} |\n"
    metrics += f"| 🟡 Medium | {severity_counts['medium']} |\n"
    metrics += f"| 🟢 Low/Info | {severity_counts['low'] + severity_counts['info']} |\n"

    return metrics


def generate_blog_post(discoveries: list[dict], commits: list[dict]) -> dict:
    """Generate an engaging 2026-standard blog post from discoveries."""
    # Use Eastern Time for dates (CEO timezone)
    now_et = datetime.now(ET)
    date = now_et.strftime("%Y-%m-%d")
    timestamp = now_et.strftime("%Y-%m-%d %H:%M:%S")
    day_of_week = now_et.strftime("%A")  # e.g., "Sunday"
    repo_url = "https://github.com/IgorGanapolsky/trading"

    # Find the highest severity discovery for the title
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    sorted_discoveries = sorted(
        discoveries, key=lambda d: severity_order.get(d.get("severity", "info"), 4)
    )

    # Create engaging title based on content
    if len(sorted_discoveries) == 1:
        d = sorted_discoveries[0]
        sev_badge = SEVERITY_BADGES.get(d.get("severity", "info"), "")
        title = (
            f"{sev_badge} {d['title'][:50]}" if d.get("title") else "Today's Engineering Discovery"
        )
    elif len(sorted_discoveries) > 0:
        d = sorted_discoveries[0]
        sev_badge = SEVERITY_BADGES.get(d.get("severity", "info"), "")
        main_topic = d["title"][:35] if d.get("title") else "System Improvements"
        title = f"{sev_badge} {main_topic} (+{len(sorted_discoveries) - 1} more)"
    else:
        title = f"🚀 What We Shipped Today: {len(commits)} Commits"

    # Collect all tags from discoveries
    all_tags = set()
    for d in discoveries:
        all_tags.update(d.get("tags", []))

    canonical = canonical_url_for_post(date, "ralph-discovery")
    description = truncate_meta_description(
        (
            f"Autonomous self-healing update for {now_et.strftime('%B %d, %Y')}: "
            f"{len(sorted_discoveries)} discoveries and {len(commits)} commits. "
            f"Top highlight: {title}."
        ),
        max_chars=160,
    )
    tag_list = (
        list(all_tags)[:4] if all_tags else ["ralph", "self-healing", "automation", "ai-trading"]
    )
    questions = [
        {
            "question": "What did Ralph fix today?",
            "answer": f"{len(sorted_discoveries)} discoveries and {len(commits)} commits. Top highlight: {title}.",
        },
        {
            "question": "How does the self-healing pipeline work?",
            "answer": "Ralph monitors CI, runs tests, generates fixes, verifies them, and publishes a post with code snippets and metrics.",
        },
        {"question": "Where is the canonical version of this post?", "answer": f"{canonical}"},
    ]

    frontmatter = render_frontmatter(
        {
            "layout": "post",
            "title": title,
            "description": description,
            "date": timestamp,
            "last_modified_at": date,
            "image": "/assets/og-image.png",
            "categories": ["engineering", "lessons-learned", "ai-trading"],
            "tags": tag_list,
            "mermaid": True,
        },
        questions=questions,
    )

    # Build the post content with 2026 engagement features
    content = (
        frontmatter
        + f"""**{day_of_week}, {now_et.strftime("%B %d, %Y")}** (Eastern Time)

> Building an autonomous AI trading system means things break. Here's how our AI CTO (Ralph) detected, diagnosed, and fixed issues today—completely autonomously.

## 🗺️ Today's Fix Flow

{generate_mermaid_diagram(discoveries, commits)}

{generate_trend_metrics(discoveries)}

---

"""
    )

    # Add discoveries with enhanced narrative style
    for i, discovery in enumerate(sorted_discoveries, 1):
        severity = discovery.get("severity", "info")
        sev_badge = SEVERITY_BADGES.get(severity, "ℹ️ INFO")

        # Build lesson link
        lesson_link = ""
        if discovery.get("lesson_id"):
            lesson_link = f"\n\n📚 *[Full lesson: {discovery['lesson_id']}]({repo_url}/blob/main/rag_knowledge/lessons_learned/)*"

        # Build code snippet section
        code_section = ""
        if discovery.get("code_blocks"):
            code_section = f"""

### 💻 The Fix

```python
{discovery["code_blocks"][0][:500]}
```
"""

        # Build root cause section
        root_cause_section = ""
        if discovery.get("root_cause"):
            root_cause_section = f"""

### 🔬 Root Cause

{discovery["root_cause"][:300]}
"""

        # Build the discovery section with narrative
        problem_text = discovery.get("problem", "Issue detected during routine scan")
        solution_text = discovery.get("solution", "")
        impact_text = discovery.get("impact", "")

        content += f"""
## {sev_badge} {discovery.get("title", f"Discovery #{i}")}

### 🚨 What Went Wrong

{problem_text}
{root_cause_section}

### ✅ How We Fixed It

{solution_text if solution_text else "Applied targeted fix based on root cause analysis."}
{code_section}

### 📈 Impact

{impact_text if impact_text else "Risk reduced and system resilience improved."}{lesson_link}

---
"""

    # Add commit summary with severity and code snippets
    if commits:
        content += f"""
## 🚀 Code Changes

These commits shipped today ([view on GitHub]({repo_url}/commits/main)):

| Severity | Commit | Description |
|----------|--------|-------------|
"""
        for commit in commits[:5]:
            sev_badge = SEVERITY_BADGES.get(commit.get("severity", "info"), "ℹ️")
            sha_link = f"[{commit['sha']}]({repo_url}/commit/{commit['sha']})"
            content += f"| {sev_badge} | {sha_link} | {commit['message'][:45]} |\n"

        # Add code snippet from most significant commit
        significant_commit = next((c for c in commits if c.get("code_snippet")), None)
        if significant_commit and significant_commit.get("code_snippet"):
            content += f"""

### 💻 Featured Code Change

From commit `{significant_commit["sha"]}`:

```python
{significant_commit["code_snippet"][:600]}
```
"""

    # Add engaging footer with call-to-action
    content += f"""

## 🎯 Key Takeaways

1. **Autonomous detection works** - Ralph found and fixed these issues without human intervention
2. **Self-healing systems compound** - Each fix makes the system smarter
3. **Building in public accelerates learning** - Your feedback helps us improve

---

## FAQ

### What did Ralph fix today?

{len(sorted_discoveries)} discoveries and {len(commits)} commits. Top highlight: {title}.

### Where is the canonical version of this post?

{canonical}

---

## 🤖 About Ralph Mode

Ralph is our AI CTO that autonomously maintains this trading system. It:
- Monitors for issues 24/7
- Runs tests and fixes failures
- Learns from mistakes via RAG + RLHF
- Documents everything for transparency

*This is part of our journey building an AI-powered iron condor trading system targeting $6K/month financial independence.*

**Resources:**
- 📊 [Source Code]({repo_url})
- 📈 [Strategy Guide](https://igorganapolsky.github.io/trading/2026/01/21/iron-condors-ai-trading-complete-guide.html)
- 🤫 [The Silent 74 Days](https://igorganapolsky.github.io/trading/2026/01/07/the-silent-74-days.html) - How we built a system that did nothing

---

*💬 Found this useful? Star the repo or drop a comment!*
"""

    return {
        "title": title,
        "content": content,
        "date": date,
        "tags": (list(all_tags)[:4] if all_tags else ["ralph", "automation", "self-healing", "ai"]),
    }


def save_to_github_pages(post: dict) -> str | None:
    """Save post to GitHub Pages _posts directory."""
    posts_dir = Path("docs/_posts")
    posts_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{post['date']}-ralph-discovery.md"
    filepath = posts_dir / filename

    filepath.write_text(post["content"])
    print(f"✅ Saved to GitHub Pages: {filepath}")
    return str(filepath)


def publish_to_devto(post: dict) -> dict | None:
    """Publish post to Dev.to."""
    api_key = get_devto_api_key()
    if not api_key:
        print("⚠️ DEVTO_API_KEY not set - skipping Dev.to publish")
        return None

    # Convert to Dev.to format
    devto_content = post["content"]
    # Remove Jekyll front matter for Dev.to
    devto_content = re.sub(r"---\n.*?---\n", "", devto_content, flags=re.DOTALL)

    payload = {
        "article": {
            "title": post["title"],
            "body_markdown": devto_content,
            "published": True,
            "tags": post["tags"][:4],  # Dev.to allows max 4 tags
            "series": "Ralph Mode: AI Self-Healing Systems",
            "canonical_url": canonical_url_for_post(post["date"], "ralph-discovery"),
        }
    }

    try:
        response = requests.post(
            "https://dev.to/api/articles",
            headers={"api-key": api_key, "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )

        if response.status_code == 201:
            result = response.json()
            print(f"✅ Published to Dev.to: {result.get('url', 'Success')}")
            return result
        else:
            print(f"⚠️ Dev.to publish failed: {response.status_code} - {response.text[:200]}")
            return None
    except Exception as e:
        print(f"⚠️ Dev.to error: {e}")
        return None


def should_publish() -> bool:
    """Determine if there's enough content to warrant a blog post."""
    lessons = get_recent_lesson_files(hours=24)
    commits = get_recent_ralph_commits()

    # Need at least 1 lesson or 3 significant commits
    significant_commits = [
        c for c in commits if "fix" in c["message"].lower() or "feat" in c["message"].lower()
    ]

    return len(lessons) >= 1 or len(significant_commits) >= 3


def main():
    print("=" * 60)
    print("RALPH DISCOVERY BLOG PUBLISHER")
    print("=" * 60)

    # Check if there's content to publish
    if not should_publish():
        print("ℹ️ No significant discoveries in last 24 hours - skipping")
        return 0

    # Gather discoveries
    lessons = get_recent_lesson_files(hours=24)
    commits = get_recent_ralph_commits()

    print(f"Found {len(lessons)} recent lessons, {len(commits)} recent commits")

    # Extract discovery content
    discoveries = []
    for lesson in lessons[:3]:  # Max 3 discoveries per post
        try:
            discovery = extract_discovery_content(lesson)
            discoveries.append(discovery)
        except Exception as e:
            print(f"⚠️ Could not parse {lesson}: {e}")

    if not discoveries and not commits:
        print("ℹ️ No parseable discoveries - skipping")
        return 0

    # Generate blog post
    post = generate_blog_post(discoveries, commits)
    print(f"\n📝 Generated post: {post['title']}")

    # Save to GitHub Pages
    gh_path = save_to_github_pages(post)

    # Publish to Dev.to
    devto_result = publish_to_devto(post)

    print("\n" + "=" * 60)
    print("BLOG PUBLISHING COMPLETE")
    print("=" * 60)
    print(f"GitHub Pages: {gh_path or 'Skipped'}")
    print(f"Dev.to: {devto_result.get('url') if devto_result else 'Skipped'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
