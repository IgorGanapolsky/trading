#!/usr/bin/env python3
"""
Update existing Dev.to post with engaging content.

This script finds today's post and updates it with the new engaging format.
"""

import os
import sys

import requests
from scripts.publish_weekend_devto import generate_engaging_post


def get_devto_api_key() -> str | None:
    """Get Dev.to API key from environment."""
    return os.environ.get("DEVTO_API_KEY")


def find_todays_article(api_key: str) -> dict | None:
    """Find today's article to update."""
    headers = {"api-key": api_key}

    response = requests.get(
        "https://dev.to/api/articles/me/published?per_page=20",
        headers=headers,
        timeout=30,
    )

    if response.status_code != 200:
        print(f"Error fetching articles: {response.status_code}")
        return None

    articles = response.json()

    for article in articles:
        # Check if it's today's post
        if "Day 79" in article["title"] or "January 18" in article["title"]:
            print(f"Found article to update: {article['id']} - {article['title']}")
            return article

    print("No matching article found for today")
    return None


def update_article(api_key: str, article_id: int, title: str, body: str) -> bool:
    """Update an existing article."""
    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
    }

    payload = {
        "article": {
            "title": title,
            "body_markdown": body,
        }
    }

    response = requests.put(
        f"https://dev.to/api/articles/{article_id}",
        headers=headers,
        json=payload,
        timeout=30,
    )

    if response.status_code == 200:
        data = response.json()
        print(f"✅ Article updated: {data.get('url', 'N/A')}")
        return True
    else:
        print(f"Error updating article: {response.status_code}")
        print(response.text)
        return False


def main():
    """Main entry point."""
    print("=" * 60)
    print("Dev.to Post Updater - Engaging Format")
    print("=" * 60)

    api_key = get_devto_api_key()
    if not api_key:
        print("No DEVTO_API_KEY found")
        return 1

    # Find today's article
    article = find_todays_article(api_key)
    if not article:
        print("No article to update - will create new one")
        # Fall back to creating new
        from scripts.publish_weekend_devto import publish_to_devto

        title, body = generate_engaging_post()
        url = publish_to_devto(title, body)
        return 0 if url else 1

    # Generate new engaging content
    title, body = generate_engaging_post()
    print(f"\nNew title: {title}")
    print(f"Body length: {len(body)} characters")

    # Update the article
    success = update_article(api_key, article["id"], title, body)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
