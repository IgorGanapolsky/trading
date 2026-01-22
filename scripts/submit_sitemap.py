#!/usr/bin/env python3
"""
Submit sitemap to search engines for better discoverability.

This script pings search engines to notify them of sitemap updates.
Run this after deploying new content to accelerate indexing.

Usage:
    python3 scripts/submit_sitemap.py [--dry-run]
"""

import argparse
import urllib.parse
import urllib.request
import sys
from datetime import datetime

# Site configuration
SITEMAP_URL = "https://igorganapolsky.github.io/trading/sitemap.xml"
FEED_URL = "https://igorganapolsky.github.io/trading/feed.xml"

# Search engine ping endpoints
SEARCH_ENGINES = {
    "Google": f"https://www.google.com/ping?sitemap={urllib.parse.quote(SITEMAP_URL)}",
    "Bing": f"https://www.bing.com/ping?sitemap={urllib.parse.quote(SITEMAP_URL)}",
    # IndexNow for faster Bing/Yandex indexing (requires API key)
    # "IndexNow": f"https://api.indexnow.org/indexnow?url={SITEMAP_URL}&key=YOUR_KEY",
}

# Feed aggregators
FEED_SERVICES = {
    "Feedly": f"https://cloud.feedly.com/v3/search/feeds?query={urllib.parse.quote(FEED_URL)}",
    # Pingomatic for blog aggregators
    "Pingomatic": "https://pingomatic.com/",
}


def ping_search_engine(name: str, url: str, dry_run: bool = False) -> bool:
    """Ping a search engine with sitemap URL."""
    print(f"  Pinging {name}...")

    if dry_run:
        print(f"    [DRY RUN] Would ping: {url}")
        return True

    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "AI-Trading-Bot/1.0 (+https://github.com/IgorGanapolsky/trading)"}
        )
        response = urllib.request.urlopen(request, timeout=30)
        status = response.getcode()

        if status == 200:
            print(f"    OK ({status})")
            return True
        else:
            print(f"    Warning: Status {status}")
            return False

    except urllib.error.HTTPError as e:
        print(f"    HTTP Error: {e.code}")
        return False
    except urllib.error.URLError as e:
        print(f"    URL Error: {e.reason}")
        return False
    except Exception as e:
        print(f"    Error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Submit sitemap to search engines")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually ping")
    args = parser.parse_args()

    print("=" * 60)
    print("SITEMAP SUBMISSION")
    print(f"Sitemap: {SITEMAP_URL}")
    print(f"Feed: {FEED_URL}")
    print(f"Time: {datetime.now().isoformat()}")
    print("=" * 60)

    # Ping search engines
    print("\nSearch Engines:")
    success_count = 0
    for name, url in SEARCH_ENGINES.items():
        if ping_search_engine(name, url, args.dry_run):
            success_count += 1

    print(f"\nResults: {success_count}/{len(SEARCH_ENGINES)} successful")

    # Info about manual submissions
    print("\n" + "=" * 60)
    print("MANUAL SUBMISSION RECOMMENDED:")
    print("=" * 60)
    print("""
For better indexing, manually submit to:

1. Google Search Console:
   https://search.google.com/search-console
   - Add property: igorganapolsky.github.io/trading
   - Submit sitemap: /trading/sitemap.xml

2. Bing Webmaster Tools:
   https://www.bing.com/webmasters
   - Add site
   - Submit sitemap

3. Dev.to:
   - Your posts auto-link back to GitHub Pages (canonical URLs)
   - Cross-posting increases discoverability

4. Hacker News / Reddit:
   - Share significant discoveries manually
   - Subreddits: r/algotrading, r/options, r/python

5. Twitter/X:
   - Share daily discoveries with #algotrading #python #AI
""")

    return 0 if success_count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
