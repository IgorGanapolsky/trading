#!/usr/bin/env python3
"""
Phil Town Blog Ingestion Script

Scrapes and stores articles from Phil Town's Rule One Investing blog
into RAG for ML pipeline synthesis.

Blog: https://www.ruleoneinvesting.com/blog/
"""

import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Blog and Podcast info
BLOG_URL = "https://www.ruleoneinvesting.com/blog/"
PODCAST_URL = "https://www.ruleoneinvesting.com/podcast/"

# Storage paths
RAG_BLOG = Path("rag_knowledge/blogs/phil_town")
RAG_PODCAST = Path("rag_knowledge/podcasts/phil_town")
CACHE_FILE = Path("data/blog_cache/phil_town_articles.json")


def ensure_directories():
    """Create required directories."""
    RAG_BLOG.mkdir(parents=True, exist_ok=True)
    RAG_PODCAST.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)


def fetch_page(url: str) -> Optional[str]:
    """Fetch a web page with retry logic."""
    try:
        import urllib.error
        import urllib.request

        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0; +https://github.com/trading)"
        }
        request = urllib.request.Request(url, headers=headers)

        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8")

    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return None


def parse_blog_index(html: str) -> list[dict]:
    """Parse blog index page to extract article links."""
    articles = []

    # Simple regex patterns for common blog structures
    # Look for article links with titles
    article_pattern = r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]+)</a>'

    matches = re.findall(article_pattern, html, re.IGNORECASE)

    for url, title in matches:
        # Filter for blog article URLs (not navigation, not external)
        if "/blog/" in url and len(title) > 10:
            # Skip common non-article links
            skip_words = ["category", "tag", "page", "author", "search", "login"]
            if any(word in url.lower() for word in skip_words):
                continue

            full_url = url if url.startswith("http") else urljoin(BLOG_URL, url)

            articles.append({"url": full_url, "title": title.strip()})

    # Deduplicate by URL
    seen = set()
    unique_articles = []
    for article in articles:
        if article["url"] not in seen:
            seen.add(article["url"])
            unique_articles.append(article)

    logger.info(f"Found {len(unique_articles)} articles")
    return unique_articles[:200]  # Increased limit for comprehensive coverage


# Known blog category pages to crawl for more articles
CATEGORY_PAGES = [
    "https://www.ruleoneinvesting.com/blog/how-to-invest/",
    "https://www.ruleoneinvesting.com/blog/stock-market-basics/",
    "https://www.ruleoneinvesting.com/blog/financial-control/",
    "https://www.ruleoneinvesting.com/blog/personal-development/",
    "https://www.ruleoneinvesting.com/blog/investing-news-and-tips/",
    "https://www.ruleoneinvesting.com/blog/retirement-planning/",
    "https://www.ruleoneinvesting.com/blog/value-investing/",
    "https://www.ruleoneinvesting.com/blog/options-trading/",
]


def discover_all_articles() -> list[dict]:
    """Crawl main blog and all category pages to discover articles."""
    all_articles = []
    seen_urls = set()

    # Fetch main blog index
    logger.info("Crawling main blog index...")
    main_html = fetch_page(BLOG_URL)
    if main_html:
        articles = parse_blog_index(main_html)
        for a in articles:
            if a["url"] not in seen_urls:
                seen_urls.add(a["url"])
                all_articles.append(a)

    # Crawl each category page
    for category_url in CATEGORY_PAGES:
        logger.info(f"Crawling category: {category_url}")
        time.sleep(0.5)  # Rate limiting
        html = fetch_page(category_url)
        if html:
            articles = parse_blog_index(html)
            for a in articles:
                # Skip if it's a category page itself
                if a["url"].rstrip("/") in [c.rstrip("/") for c in CATEGORY_PAGES]:
                    continue
                if a["url"] not in seen_urls:
                    seen_urls.add(a["url"])
                    all_articles.append(a)

    logger.info(f"Total unique articles discovered: {len(all_articles)}")
    return all_articles


def parse_article_content(html: str) -> Optional[str]:
    """Extract main article content from HTML."""
    # Remove scripts and styles
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)

    # Try to find article content
    content_patterns = [
        r"<article[^>]*>(.*?)</article>",
        r'<div[^>]+class="[^"]*content[^"]*"[^>]*>(.*?)</div>',
        r'<div[^>]+class="[^"]*post[^"]*"[^>]*>(.*?)</div>',
        r"<main[^>]*>(.*?)</main>",
    ]

    content = None
    for pattern in content_patterns:
        match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
        if match:
            content = match.group(1)
            break

    if not content:
        # Fallback: get body content
        body_match = re.search(r"<body[^>]*>(.*?)</body>", html, re.DOTALL | re.IGNORECASE)
        if body_match:
            content = body_match.group(1)

    if not content:
        return None

    # Clean HTML tags
    text = re.sub(r"<[^>]+>", " ", content)

    # Clean whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # Remove common boilerplate
    boilerplate = [
        "Subscribe to our newsletter",
        "Share this post",
        "Leave a comment",
        "Related posts",
        "Follow us on",
    ]
    for bp in boilerplate:
        text = re.sub(re.escape(bp) + r".*", "", text, flags=re.IGNORECASE)

    return text if len(text) > 200 else None


def analyze_blog_article(content: str, title: str) -> dict:
    """Extract insights from blog article."""
    insights = {
        "key_concepts": [],
        "stocks_mentioned": [],
        "strategies": [],
        "sentiment": "educational",
    }

    content_lower = content.lower()

    # Phil Town concepts
    concepts = {
        "4 Ms Framework": ["4 m", "four m", "meaning", "moat", "management", "margin of safety"],
        "Moat Analysis": ["moat", "competitive advantage", "durable advantage"],
        "Margin of Safety": ["margin of safety", "mos", "sticker price"],
        "Big Five Numbers": ["big five", "roic", "equity growth", "eps growth"],
        "Rule #1": ["rule one", "rule #1", "don't lose money"],
        "Value Investing": ["intrinsic value", "undervalued", "wonderful company"],
        "Options Income": ["covered call", "cash secured put", "wheel strategy"],
    }

    for concept, keywords in concepts.items():
        if any(kw in content_lower for kw in keywords):
            insights["key_concepts"].append(concept)

    # Stock tickers
    ticker_pattern = r"\b([A-Z]{2,5})\b"
    valid_tickers = {
        "AAPL",
        "MSFT",
        "GOOGL",
        "AMZN",
        "META",
        "NVDA",
        "TSLA",
        "BRK",
        "V",
        "MA",
        "SPY",
        "QQQ",
    }
    for match in re.findall(ticker_pattern, content):
        if match in valid_tickers and match not in insights["stocks_mentioned"]:
            insights["stocks_mentioned"].append(match)

    return insights


def save_article_to_rag(article: dict, content: str, insights: dict):
    """Save article to RAG storage."""
    # Create safe filename from URL
    safe_name = re.sub(r"[^\w\s-]", "", article["title"])[:50].strip().replace(" ", "_")
    slug = (
        article["url"].split("/")[-2]
        if article["url"].endswith("/")
        else article["url"].split("/")[-1]
    )
    slug = re.sub(r"[^\w-]", "", slug)[:30]

    filename = f"{slug}_{safe_name}.md"
    filepath = RAG_BLOG / filename

    markdown = f"""# {article["title"]}

**Source**: {article["url"]}
**Author**: Phil Town
**Ingested**: {datetime.now().isoformat()}
**Category**: Rule #1 Investing Blog

## Key Concepts
{", ".join(insights["key_concepts"]) if insights["key_concepts"] else "General investing education"}

## Stocks Mentioned
{", ".join(insights["stocks_mentioned"]) if insights["stocks_mentioned"] else "None specific"}

## Article Content

{content}

---
*This content was automatically ingested from Phil Town's Rule One Investing blog for educational purposes.*
"""

    filepath.write_text(markdown)
    logger.info(f"Saved: {filepath}")

    return filepath


def load_processed_articles() -> set:
    """Load set of already processed article URLs."""
    if CACHE_FILE.exists():
        try:
            data = json.loads(CACHE_FILE.read_text())
            return set(data.get("processed_urls", []))
        except:
            pass
    return set()


def save_processed_articles(urls: set):
    """Save set of processed article URLs."""
    data = {
        "processed_urls": list(urls),
        "last_updated": datetime.now().isoformat(),
        "count": len(urls),
    }
    CACHE_FILE.write_text(json.dumps(data, indent=2))


def ingest_blog(max_articles: int = 100) -> dict:
    """Main blog ingestion function."""
    ensure_directories()

    results = {"success": 0, "failed": 0, "skipped": 0, "articles": []}

    processed = load_processed_articles()

    # Discover all articles from main blog AND category pages
    logger.info("Discovering articles from all sources...")
    articles = discover_all_articles()

    if not articles:
        logger.error("Failed to discover any articles")
        return {"success": False, "reason": "failed_to_discover_articles"}

    for article in articles[:max_articles]:
        if article["url"] in processed:
            logger.info(f"Skipping already processed: {article['title'][:40]}...")
            results["skipped"] += 1
            continue

        logger.info(f"Processing: {article['title'][:50]}...")

        # Fetch article
        html = fetch_page(article["url"])
        if not html:
            results["failed"] += 1
            continue

        # Parse content
        content = parse_article_content(html)
        if not content:
            logger.warning(f"Could not extract content from {article['url']}")
            results["failed"] += 1
            continue

        # Analyze
        insights = analyze_blog_article(content, article["title"])

        # Save
        try:
            save_article_to_rag(article, content, insights)
            processed.add(article["url"])
            results["success"] += 1
            results["articles"].append(
                {"title": article["title"], "concepts": insights["key_concepts"]}
            )
        except Exception as e:
            logger.error(f"Failed to save: {e}")
            results["failed"] += 1

        # Be nice to the server
        time.sleep(1)

    save_processed_articles(processed)

    return results


def ingest_podcast(max_episodes: int = 20) -> dict:
    """Ingest podcast episodes from Phil Town's podcast page."""
    ensure_directories()

    results = {"success": 0, "failed": 0, "skipped": 0, "episodes": []}

    processed = load_processed_articles()

    # Fetch podcast index
    logger.info(f"Fetching podcast index: {PODCAST_URL}")
    index_html = fetch_page(PODCAST_URL)

    if not index_html:
        logger.error("Failed to fetch podcast index")
        return {"success": False, "reason": "failed_to_fetch_podcast_index"}

    # Parse episodes (similar to blog parsing)
    episodes = parse_blog_index(index_html)  # Reuse blog parser

    for episode in episodes[:max_episodes]:
        if episode["url"] in processed:
            results["skipped"] += 1
            continue

        logger.info(f"Processing podcast: {episode['title'][:50]}...")

        html = fetch_page(episode["url"])
        if not html:
            results["failed"] += 1
            continue

        content = parse_article_content(html)
        if not content:
            results["failed"] += 1
            continue

        insights = analyze_blog_article(content, episode["title"])

        # Save to podcast directory
        safe_name = re.sub(r"[^\w\s-]", "", episode["title"])[:50].strip().replace(" ", "_")
        slug = (
            episode["url"].split("/")[-2]
            if episode["url"].endswith("/")
            else episode["url"].split("/")[-1]
        )
        slug = re.sub(r"[^\w-]", "", slug)[:30]

        filename = f"{slug}_{safe_name}.md"
        filepath = RAG_PODCAST / filename

        markdown = f"""# {episode["title"]}

**Source**: {episode["url"]}
**Host**: Phil Town
**Type**: InvestED Podcast Episode
**Ingested**: {datetime.now().isoformat()}

## Key Concepts
{", ".join(insights["key_concepts"]) if insights["key_concepts"] else "General investing discussion"}

## Episode Notes

{content}

---
*Podcast show notes ingested from Phil Town InvestED Podcast.*
"""
        try:
            filepath.write_text(markdown)
            processed.add(episode["url"])
            results["success"] += 1
            results["episodes"].append({"title": episode["title"]})
            logger.info(f"Saved podcast: {filepath}")
        except Exception as e:
            logger.error(f"Failed to save podcast: {e}")
            results["failed"] += 1

        time.sleep(1)

    save_processed_articles(processed)
    return results


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Ingest Phil Town blog and podcast to RAG")
    parser.add_argument(
        "--max-articles",
        type=int,
        default=100,
        help="Maximum articles/episodes to process (default: 100)",
    )
    parser.add_argument(
        "--source",
        choices=["blog", "podcast", "all"],
        default="all",
        help="Source to ingest: blog, podcast, or all (default: all)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would be processed")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("PHIL TOWN CONTENT INGESTION")
    logger.info(f"Source: {args.source}")
    logger.info("=" * 60)

    ensure_directories()

    if args.dry_run:
        if args.source in ["blog", "all"]:
            html = fetch_page(BLOG_URL)
            if html:
                articles = parse_blog_index(html)
                logger.info("Blog articles to process:")
                for a in articles[: args.max_articles]:
                    logger.info(f"  - {a['title'][:60]}...")
        if args.source in ["podcast", "all"]:
            html = fetch_page(PODCAST_URL)
            if html:
                episodes = parse_blog_index(html)
                logger.info("Podcast episodes to process:")
                for e in episodes[: args.max_articles]:
                    logger.info(f"  - {e['title'][:60]}...")
        return {"dry_run": True}

    results = {"blog": {}, "podcast": {}}

    if args.source in ["blog", "all"]:
        logger.info("--- Ingesting Blog ---")
        results["blog"] = ingest_blog(max_articles=args.max_articles)

    if args.source in ["podcast", "all"]:
        logger.info("--- Ingesting Podcast ---")
        results["podcast"] = ingest_podcast(max_episodes=args.max_articles)

    logger.info("=" * 60)
    logger.info("INGESTION COMPLETE")
    if results["blog"]:
        logger.info(
            f"Blog - Success: {results['blog'].get('success', 0)}, Failed: {results['blog'].get('failed', 0)}"
        )
    if results["podcast"]:
        logger.info(
            f"Podcast - Success: {results['podcast'].get('success', 0)}, Failed: {results['podcast'].get('failed', 0)}"
        )
    logger.info("=" * 60)

    return results


if __name__ == "__main__":
    result = main()
    print(f"\nResult: {json.dumps(result, indent=2, default=str)}")
