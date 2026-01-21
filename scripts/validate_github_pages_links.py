#!/usr/bin/env python3
"""
GitHub Pages Link Validator

Validates that all Jekyll templates use relative_url filter correctly
and that generated HTML has valid internal links.

Usage:
    python scripts/validate_github_pages_links.py [--check-live]
"""

import argparse
import re
import sys
from pathlib import Path


class LinkValidator:
    """Validates GitHub Pages links in Jekyll templates and built HTML."""

    DOCS_DIR = Path(__file__).parent.parent / "docs"
    SITE_DIR = DOCS_DIR / "_site"
    BASEURL = "/trading"

    def __init__(self):
        self.errors = []
        self.warnings = []

    def validate_jekyll_templates(self) -> bool:
        """Check all .md and .html files use relative_url filter for internal links."""
        print("=" * 60)
        print("VALIDATING JEKYLL TEMPLATES")
        print("=" * 60)

        # Pattern to find {{ something.url }} without relative_url
        bad_url_pattern = re.compile(
            r"\{\{\s*\w+\.url\s*\}\}"  # {{ lesson.url }} without filter
        )

        # Pattern to find good usage
        good_url_pattern = re.compile(
            r"\{\{\s*\w+\.url\s*\|\s*relative_url\s*\}\}"  # {{ lesson.url | relative_url }}
        )

        template_files = list(self.DOCS_DIR.glob("*.md")) + list(self.DOCS_DIR.glob("*.html"))
        template_files += list(self.DOCS_DIR.glob("_layouts/*.html"))
        template_files += list(self.DOCS_DIR.glob("_includes/*.html"))

        found_issues = False

        for filepath in template_files:
            if filepath.name.startswith("_"):
                continue

            content = filepath.read_text()

            # Find bad patterns
            bad_matches = bad_url_pattern.findall(content)
            good_matches = good_url_pattern.findall(content)

            # Filter out false positives (bad matches that are actually inside good matches)
            actual_bad = []
            for bad in bad_matches:
                # Check if this bad pattern is part of a good pattern
                bad_in_good = any(bad.strip("{}").strip() in good for good in good_matches)
                if not bad_in_good:
                    actual_bad.append(bad)

            if actual_bad:
                found_issues = True
                for match in actual_bad:
                    line_num = self._find_line_number(content, match)
                    error_msg = f"❌ {filepath.relative_to(self.DOCS_DIR)}:{line_num} - Missing relative_url filter: {match}"
                    self.errors.append(error_msg)
                    print(error_msg)

        if not found_issues:
            print("✅ All Jekyll templates use relative_url filter correctly")

        return not found_issues

    def validate_built_html(self) -> bool:
        """Validate links in built _site directory."""
        print("\n" + "=" * 60)
        print("VALIDATING BUILT HTML")
        print("=" * 60)

        if not self.SITE_DIR.exists():
            print(f"⚠️  _site directory not found at {self.SITE_DIR}")
            print("   Run 'bundle exec jekyll build' first, or skip with --templates-only")
            self.warnings.append("_site directory not found - skipping HTML validation")
            return True  # Not a failure, just can't validate

        html_files = list(self.SITE_DIR.glob("**/*.html"))
        if not html_files:
            print("⚠️  No HTML files found in _site")
            return True

        # Pattern for internal links that DON'T start with /trading/ or are absolute
        internal_link_pattern = re.compile(r'href=["\'](/(?!trading/)[^"\']*)["\']')

        found_issues = False

        for filepath in html_files:
            content = filepath.read_text()

            # Find internal links missing baseurl
            bad_links = internal_link_pattern.findall(content)

            # Filter out valid patterns (anchors, external protocols, etc.)
            bad_links = [
                link
                for link in bad_links
                if not link.startswith("/#")  # Anchor links
                and not link.startswith("/trading")  # Correct baseurl
                and "://" not in link  # External links
                and link != "/"  # Root might be intentional
            ]

            if bad_links:
                found_issues = True
                for link in bad_links[:5]:  # Limit output per file
                    error_msg = f"❌ {filepath.relative_to(self.SITE_DIR)}: Bad internal link: {link} (missing /trading prefix)"
                    self.errors.append(error_msg)
                    print(error_msg)

        if not found_issues:
            print("✅ All built HTML links are correctly prefixed")

        return not found_issues

    def smoke_test_live_site(
        self, base_url: str = "https://igorganapolsky.github.io/trading"
    ) -> bool:
        """Test actual deployed site for 404s."""
        print("\n" + "=" * 60)
        print("SMOKE TESTING LIVE SITE")
        print("=" * 60)

        try:
            import requests
        except ImportError:
            print("⚠️  requests library not installed - skipping live test")
            self.warnings.append("requests not installed - skipping live smoke test")
            return True

        # Key pages to test
        test_urls = [
            f"{base_url}/",
            f"{base_url}/lessons/",
            f"{base_url}/RETROSPECTIVE",
        ]

        # Also test a few lesson URLs from the _lessons directory
        lessons_dir = self.DOCS_DIR / "_lessons"
        if lessons_dir.exists():
            lesson_files = list(lessons_dir.glob("*.md"))[:3]
            for lesson_file in lesson_files:
                # Convert filename to URL slug
                slug = lesson_file.stem.replace("_", "-")
                test_urls.append(f"{base_url}/lessons/{slug}/")

        found_issues = False
        for url in test_urls:
            try:
                response = requests.get(url, timeout=10, allow_redirects=True)
                if response.status_code == 404:
                    found_issues = True
                    error_msg = f"❌ 404 NOT FOUND: {url}"
                    self.errors.append(error_msg)
                    print(error_msg)
                elif response.status_code == 200:
                    print(f"✅ {url} - OK")
                else:
                    print(f"⚠️  {url} - Status: {response.status_code}")
            except requests.RequestException as e:
                print(f"⚠️  {url} - Request failed: {e}")

        return not found_issues

    def _find_line_number(self, content: str, search_str: str) -> int:
        """Find line number of a string in content."""
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            if search_str in line:
                return i
        return 0

    def run_all(self, check_live: bool = False, templates_only: bool = False) -> bool:
        """Run all validations and return success status."""
        print("\n🔍 GitHub Pages Link Validator")
        print("=" * 60)

        results = []

        # Always check templates
        results.append(self.validate_jekyll_templates())

        # Check built HTML unless templates-only
        if not templates_only:
            results.append(self.validate_built_html())

        # Optionally check live site
        if check_live:
            results.append(self.smoke_test_live_site())

        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)

        if self.errors:
            print(f"\n❌ FAILED: {len(self.errors)} error(s) found:")
            for error in self.errors:
                print(f"   {error}")

        if self.warnings:
            print(f"\n⚠️  {len(self.warnings)} warning(s):")
            for warning in self.warnings:
                print(f"   {warning}")

        if not self.errors:
            print("\n✅ ALL VALIDATIONS PASSED")

        return all(results) and not self.errors


def main():
    parser = argparse.ArgumentParser(description="Validate GitHub Pages links")
    parser.add_argument(
        "--check-live", action="store_true", help="Also test the live deployed site"
    )
    parser.add_argument(
        "--templates-only", action="store_true", help="Only check Jekyll templates, skip built HTML"
    )
    args = parser.parse_args()

    validator = LinkValidator()
    success = validator.run_all(check_live=args.check_live, templates_only=args.templates_only)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
