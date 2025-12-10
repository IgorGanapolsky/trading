#!/usr/bin/env python3
"""
Fetch RSS feeds for options trading education content and save to RAG knowledge base.
"""

import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import re


# Options trading RSS feeds
RSS_FEEDS = {
    "tastytrade": {
        "name": "TastyTrade Blog",
        "url": "https://www.tastytrade.com/news/rss",
        "fallback_url": "https://www.tastytrade.com/blog/rss",
        "focus": "Options trading strategies, volatility, premium selling"
    },
    "cboe": {
        "name": "CBOE Options Institute",
        "url": "https://www.cboe.com/rss/options-news",
        "fallback_url": "https://www.cboe.com/us/options/education/",
        "focus": "Options education, volatility indices, market structure"
    },
    "investopedia_options": {
        "name": "Investopedia Options Trading",
        "url": "https://www.investopedia.com/feedbuilder/feed/getfeed/?feedName=rss_options",
        "fallback_url": "https://www.investopedia.com/options-basics-tutorial-4583012",
        "focus": "Options basics, strategies, tutorials"
    },
    "options_alpha": {
        "name": "Options Alpha",
        "url": "https://optionsalpha.com/feed",
        "fallback_url": "https://optionsalpha.com/blog",
        "focus": "Options trading strategies, backtesting, automation"
    },
    "volatility_trading": {
        "name": "Volatility Trading & Analysis",
        "url": "https://volatiletradingresearch.com/feed/",
        "fallback_url": "https://vixcentral.com/",
        "focus": "VIX analysis, volatility trading, term structure"
    }
}


def clean_html(text: str) -> str:
    """Remove HTML tags from text."""
    if not text:
        return ""
    # Remove HTML tags
    clean = re.sub(r'<[^>]+>', '', text)
    # Remove extra whitespace
    clean = re.sub(r'\s+', ' ', clean)
    return clean.strip()


def fetch_rss_feed(feed_name: str, feed_config: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    Fetch and parse RSS feed.

    Args:
        feed_name: Identifier for the feed
        feed_config: Configuration dict with url, name, focus

    Returns:
        List of article dictionaries
    """
    articles = []
    url = feed_config["url"]

    try:
        print(f"\n[{feed_name}] Fetching RSS feed from {url}")

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        # Parse XML
        root = ET.fromstring(response.content)

        # Find channel items (RSS 2.0) or entries (Atom)
        items = root.findall('.//item') or root.findall('.//{http://www.w3.org/2005/Atom}entry')

        if not items:
            print(f"[{feed_name}] No items found in feed")
            return articles

        print(f"[{feed_name}] Found {len(items)} articles")

        for item in items[:10]:  # Limit to 10 most recent
            try:
                # RSS 2.0 format
                title = item.findtext('title') or item.findtext('{http://www.w3.org/2005/Atom}title') or "No title"
                link = item.findtext('link') or item.findtext('{http://www.w3.org/2005/Atom}link') or ""
                description = item.findtext('description') or item.findtext('{http://www.w3.org/2005/Atom}summary') or ""
                pub_date = item.findtext('pubDate') or item.findtext('{http://www.w3.org/2005/Atom}published') or ""

                # Clean HTML from description
                description_clean = clean_html(description)

                article = {
                    "source": feed_config["name"],
                    "source_id": feed_name,
                    "title": title.strip(),
                    "link": link.strip(),
                    "description": description_clean[:500] if description_clean else "",
                    "pub_date": pub_date.strip(),
                    "focus": feed_config["focus"],
                    "fetched_at": datetime.now().isoformat()
                }

                articles.append(article)

            except Exception as e:
                print(f"[{feed_name}] Error parsing item: {e}")
                continue

        return articles

    except requests.exceptions.RequestException as e:
        print(f"[{feed_name}] HTTP Error: {e}")
        return []
    except ET.ParseError as e:
        print(f"[{feed_name}] XML Parse Error: {e}")
        return []
    except Exception as e:
        print(f"[{feed_name}] Unexpected error: {e}")
        return []


def save_to_rag(articles: List[Dict[str, Any]], output_dir: Path):
    """
    Save fetched articles to RAG knowledge base.

    Args:
        articles: List of article dictionaries
        output_dir: Directory to save JSON files
    """
    if not articles:
        print("\nNo articles to save")
        return

    # Group by source
    by_source = {}
    for article in articles:
        source_id = article['source_id']
        if source_id not in by_source:
            by_source[source_id] = []
        by_source[source_id].append(article)

    # Save each source to separate file
    for source_id, source_articles in by_source.items():
        output_file = output_dir / f"{source_id}_rss.json"

        data = {
            "source_id": source_id,
            "name": source_articles[0]["source"],
            "focus": source_articles[0]["focus"],
            "fetched_at": datetime.now().isoformat(),
            "article_count": len(source_articles),
            "articles": source_articles
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"\n✓ Saved {len(source_articles)} articles from {source_articles[0]['source']} to {output_file}")


def main():
    """Main execution function."""
    print("=" * 80)
    print("OPTIONS TRADING RSS FEED FETCHER")
    print("=" * 80)

    # Set up output directory
    output_dir = Path(__file__).parent.parent / "rag_knowledge" / "newsletters"
    output_dir.mkdir(parents=True, exist_ok=True)

    all_articles = []
    successful_feeds = 0
    failed_feeds = 0

    # Fetch all feeds
    for feed_name, feed_config in RSS_FEEDS.items():
        articles = fetch_rss_feed(feed_name, feed_config)

        if articles:
            all_articles.extend(articles)
            successful_feeds += 1
        else:
            failed_feeds += 1

    # Save to RAG
    save_to_rag(all_articles, output_dir)

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Feeds checked: {len(RSS_FEEDS)}")
    print(f"Successful: {successful_feeds}")
    print(f"Failed: {failed_feeds}")
    print(f"Total articles fetched: {len(all_articles)}")
    print(f"Output directory: {output_dir}")
    print("=" * 80)

    # Show feed URLs for reference
    print("\nRSS FEED URLs (for reference):")
    print("-" * 80)
    for feed_name, feed_config in RSS_FEEDS.items():
        print(f"{feed_config['name']:30} {feed_config['url']}")
    print("-" * 80)


if __name__ == "__main__":
    main()
