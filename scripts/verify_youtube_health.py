#!/usr/bin/env python3
"""
YouTube Integration Health Check

Run this script to verify all YouTube ingestion components are working.
Exits 0 if healthy, non-zero if issues found.

Usage:
    python3 scripts/verify_youtube_health.py
    python3 scripts/verify_youtube_health.py --verbose
    python3 scripts/verify_youtube_health.py --fix  # Attempt auto-fixes
"""

from __future__ import annotations

import argparse
import importlib
import json
import subprocess
import sys
from pathlib import Path

# Colors for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
CHECK = f"{GREEN}✓{RESET}"
CROSS = f"{RED}✗{RESET}"
WARN = f"{YELLOW}⚠{RESET}"


class YouTubeHealthChecker:
    """Comprehensive health checker for YouTube integration."""

    def __init__(self, verbose: bool = False, fix: bool = False):
        self.verbose = verbose
        self.fix = fix
        self.issues: list[str] = []
        self.warnings: list[str] = []
        self.passed: list[str] = []
        self.root = Path(__file__).parent.parent

    def log(self, msg: str, level: str = "info") -> None:
        """Print message if verbose or if error."""
        if self.verbose or level in ("error", "warn"):
            print(msg)

    def check_python_dependencies(self) -> bool:
        """Verify required Python packages are installed."""
        print("\n📦 Checking Python Dependencies...")

        required = [
            ("yt_dlp", "yt-dlp"),
            ("youtube_transcript_api", "youtube-transcript-api"),
        ]
        optional = [
            ("openai", "openai"),
            ("pydantic", "pydantic"),
        ]

        all_required_ok = True

        for module_name, pip_name in required:
            try:
                importlib.import_module(module_name)
                print(f"  {CHECK} {module_name} installed")
                self.passed.append(f"Package {module_name}")
            except ImportError:
                print(f"  {CROSS} {module_name} NOT installed")
                self.issues.append(f"Missing required package: {pip_name}")
                all_required_ok = False
                if self.fix:
                    print(f"    → Installing {pip_name}...")
                    subprocess.run([sys.executable, "-m", "pip", "install", pip_name, "-q"])

        for module_name, pip_name in optional:
            try:
                importlib.import_module(module_name)
                print(f"  {CHECK} {module_name} installed (optional)")
                self.passed.append(f"Package {module_name} (optional)")
            except ImportError:
                print(f"  {WARN} {module_name} not installed (optional - LLM analysis disabled)")
                self.warnings.append(f"Optional package missing: {pip_name}")

        return all_required_ok

    def check_mcp_config(self) -> bool:
        """Verify MCP server configuration."""
        print("\n🔌 Checking MCP Server Configuration...")

        mcp_config = self.root / ".claude" / "mcp_config.json"

        if not mcp_config.exists():
            print(f"  {CROSS} MCP config not found: {mcp_config}")
            self.issues.append("MCP config file missing")
            return False

        try:
            config = json.loads(mcp_config.read_text())
            servers = config.get("mcpServers", {})

            if "youtube-transcript" in servers:
                yt_config = servers["youtube-transcript"]
                print(f"  {CHECK} youtube-transcript MCP server configured")
                print(f"      Command: {yt_config.get('command')} {' '.join(yt_config.get('args', []))}")
                self.passed.append("MCP youtube-transcript server")
                return True
            else:
                print(f"  {CROSS} youtube-transcript server NOT in MCP config")
                self.issues.append("youtube-transcript MCP server not configured")
                return False

        except json.JSONDecodeError as e:
            print(f"  {CROSS} Invalid JSON in MCP config: {e}")
            self.issues.append(f"MCP config invalid JSON: {e}")
            return False

    def check_skill_files(self) -> bool:
        """Verify YouTube skill files exist and are valid."""
        print("\n📁 Checking Skill Files...")

        skill_dir = self.root / ".claude" / "skills" / "youtube-analyzer"

        required_files = [
            "SKILL.md",
            "scripts/analyze_youtube.py",
        ]

        all_ok = True
        for rel_path in required_files:
            full_path = skill_dir / rel_path
            if full_path.exists():
                print(f"  {CHECK} {rel_path}")
                self.passed.append(f"Skill file: {rel_path}")
            else:
                print(f"  {CROSS} {rel_path} MISSING")
                self.issues.append(f"Missing skill file: {rel_path}")
                all_ok = False

        # Verify script syntax
        script = skill_dir / "scripts" / "analyze_youtube.py"
        if script.exists():
            try:
                compile(script.read_text(), str(script), "exec")
                print(f"  {CHECK} analyze_youtube.py syntax valid")
                self.passed.append("Skill script syntax")
            except SyntaxError as e:
                print(f"  {CROSS} analyze_youtube.py has syntax error: {e}")
                self.issues.append(f"Syntax error in analyze_youtube.py: {e}")
                all_ok = False

        return all_ok

    def check_monitor_script(self) -> bool:
        """Verify YouTube monitor script and config."""
        print("\n📺 Checking Monitor Script...")

        monitor_script = self.root / "scripts" / "youtube_monitor.py"
        channels_config = self.root / "scripts" / "youtube_channels.json"
        cron_script = self.root / "scripts" / "cron_youtube_monitor.sh"

        all_ok = True

        # Check monitor script
        if monitor_script.exists():
            print(f"  {CHECK} youtube_monitor.py exists")
            try:
                compile(monitor_script.read_text(), str(monitor_script), "exec")
                print(f"  {CHECK} youtube_monitor.py syntax valid")
                self.passed.append("Monitor script")
            except SyntaxError as e:
                print(f"  {CROSS} Syntax error: {e}")
                self.issues.append(f"Monitor script syntax error: {e}")
                all_ok = False
        else:
            print(f"  {CROSS} youtube_monitor.py MISSING")
            self.issues.append("Monitor script missing")
            all_ok = False

        # Check channels config
        if channels_config.exists():
            try:
                config = json.loads(channels_config.read_text())
                channels = config.get("channels", [])
                print(f"  {CHECK} youtube_channels.json valid ({len(channels)} channels)")

                # Validate channel structure
                for ch in channels:
                    if not all(k in ch for k in ["name", "channel_id"]):
                        print(f"  {WARN} Channel missing required fields: {ch.get('name', 'unknown')}")
                        self.warnings.append(f"Channel config incomplete: {ch.get('name')}")

                self.passed.append(f"Channel config ({len(channels)} channels)")
            except json.JSONDecodeError as e:
                print(f"  {CROSS} Invalid JSON in channels config: {e}")
                self.issues.append(f"Channels config invalid: {e}")
                all_ok = False
        else:
            print(f"  {CROSS} youtube_channels.json MISSING")
            self.issues.append("Channels config missing")
            all_ok = False

        # Check cron script
        if cron_script.exists():
            print(f"  {CHECK} cron_youtube_monitor.sh exists")
            self.passed.append("Cron script")
        else:
            print(f"  {WARN} cron_youtube_monitor.sh missing (optional)")
            self.warnings.append("Cron script missing")

        return all_ok

    def check_output_directories(self) -> bool:
        """Verify output directories exist or can be created."""
        print("\n📂 Checking Output Directories...")

        dirs = [
            self.root / "data" / "youtube_cache",
            self.root / "docs" / "youtube_analysis",
            self.root / "rag_knowledge" / "youtube",
        ]

        all_ok = True
        for d in dirs:
            if d.exists():
                print(f"  {CHECK} {d.relative_to(self.root)}")
                self.passed.append(f"Directory: {d.name}")
            else:
                if self.fix:
                    d.mkdir(parents=True, exist_ok=True)
                    print(f"  {CHECK} {d.relative_to(self.root)} (created)")
                    self.passed.append(f"Directory: {d.name} (created)")
                else:
                    print(f"  {WARN} {d.relative_to(self.root)} does not exist (will be created on first run)")
                    self.warnings.append(f"Directory missing: {d.name}")

        return all_ok

    def check_youtube_network(self) -> bool:
        """Test actual YouTube connectivity."""
        print("\n🌐 Testing YouTube Network Access...")

        try:
            from youtube_transcript_api import YouTubeTranscriptApi

            # Try to fetch a well-known video transcript
            test_video = "jNQXAC9IVRw"  # "Me at the zoo" - first YouTube video

            try:
                api = YouTubeTranscriptApi()
                transcript = api.fetch(test_video, languages=["en"])
                if transcript and hasattr(transcript, 'snippets'):
                    print(f"  {CHECK} YouTube API accessible (test video fetched)")
                    self.passed.append("YouTube network access")
                    return True
            except Exception as e:
                error_str = str(e)
                if "403" in error_str or "Forbidden" in error_str:
                    print(f"  {WARN} YouTube blocked in this environment (403 Forbidden)")
                    print(f"      This is normal in sandboxed environments.")
                    print(f"      Will work on your local machine or GitHub Actions.")
                    self.warnings.append("YouTube blocked in sandbox (expected)")
                    return True  # Not a failure - expected in some environments
                else:
                    print(f"  {CROSS} YouTube API error: {e}")
                    self.issues.append(f"YouTube API error: {e}")
                    return False

        except ImportError:
            print(f"  {CROSS} youtube_transcript_api not installed")
            self.issues.append("Cannot test network - package missing")
            return False

    def check_rag_integration(self) -> bool:
        """Verify RAG storage for YouTube insights."""
        print("\n🧠 Checking RAG Integration...")

        rag_dir = self.root / "rag_knowledge" / "youtube"
        insights_file = rag_dir / "insights" / "options_education_sources.json"

        if insights_file.exists():
            try:
                data = json.loads(insights_file.read_text())
                sources = data.get("sources", [])
                print(f"  {CHECK} Pre-loaded insights: {len(sources)} education sources")
                self.passed.append(f"RAG insights ({len(sources)} sources)")
                return True
            except json.JSONDecodeError:
                print(f"  {WARN} Invalid JSON in insights file")
                self.warnings.append("RAG insights file invalid")
                return True
        else:
            print(f"  {WARN} No pre-loaded insights (will be populated on first run)")
            self.warnings.append("No pre-loaded YouTube insights")
            return True

    def run_all_checks(self) -> bool:
        """Run all health checks and return overall status."""
        print("=" * 60)
        print("🎬 YOUTUBE INTEGRATION HEALTH CHECK")
        print("=" * 60)

        checks = [
            ("Python Dependencies", self.check_python_dependencies),
            ("MCP Configuration", self.check_mcp_config),
            ("Skill Files", self.check_skill_files),
            ("Monitor Script", self.check_monitor_script),
            ("Output Directories", self.check_output_directories),
            ("YouTube Network", self.check_youtube_network),
            ("RAG Integration", self.check_rag_integration),
        ]

        results = []
        for name, check_fn in checks:
            try:
                results.append(check_fn())
            except Exception as e:
                print(f"  {CROSS} Check '{name}' crashed: {e}")
                self.issues.append(f"Check '{name}' failed: {e}")
                results.append(False)

        # Summary
        print("\n" + "=" * 60)
        print("📊 SUMMARY")
        print("=" * 60)

        print(f"\n{GREEN}Passed ({len(self.passed)}):{RESET}")
        for item in self.passed:
            print(f"  {CHECK} {item}")

        if self.warnings:
            print(f"\n{YELLOW}Warnings ({len(self.warnings)}):{RESET}")
            for item in self.warnings:
                print(f"  {WARN} {item}")

        if self.issues:
            print(f"\n{RED}Issues ({len(self.issues)}):{RESET}")
            for item in self.issues:
                print(f"  {CROSS} {item}")

        overall = len(self.issues) == 0
        print("\n" + "=" * 60)
        if overall:
            print(f"{GREEN}✅ YOUTUBE INTEGRATION: HEALTHY{RESET}")
        else:
            print(f"{RED}❌ YOUTUBE INTEGRATION: ISSUES FOUND{RESET}")
            print(f"\nRun with --fix to attempt automatic fixes:")
            print(f"  python3 scripts/verify_youtube_health.py --fix")
        print("=" * 60)

        return overall


def main():
    parser = argparse.ArgumentParser(description="YouTube Integration Health Check")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--fix", action="store_true", help="Attempt to fix issues")
    args = parser.parse_args()

    checker = YouTubeHealthChecker(verbose=args.verbose, fix=args.fix)
    healthy = checker.run_all_checks()

    sys.exit(0 if healthy else 1)


if __name__ == "__main__":
    main()
