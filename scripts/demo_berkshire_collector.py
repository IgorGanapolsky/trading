#!/usr/bin/env python3
"""
Standalone demo of Berkshire Hathaway Letters Collector.

This script demonstrates the collector without relying on package imports
that may have dependency issues.
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SimpleBerkshireCollector:
    """
    Simplified Berkshire Letters Collector for demonstration.
    """

    BASE_URL = "https://www.berkshirehathaway.com"
    LETTERS_URL = f"{BASE_URL}/letters/letters.html"

    def __init__(self, cache_dir: str = "data/rag/berkshire_letters"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.raw_dir = self.cache_dir / "raw"
        self.parsed_dir = self.cache_dir / "parsed"
        self.index_dir = self.cache_dir / "index"

        for dir_path in [self.raw_dir, self.parsed_dir, self.index_dir]:
            dir_path.mkdir(exist_ok=True)

        self.index_file = self.index_dir / "letters_index.json"
        self.index = self._load_index()

        logger.info(f"Initialized collector (cache: {self.cache_dir})")

    def _load_index(self) -> dict:
        """Load the letters index from disk."""
        if self.index_file.exists():
            try:
                with open(self.index_file) as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading index: {e}")
                return {}
        return {}

    def _save_index(self):
        """Save the letters index to disk."""
        try:
            with open(self.index_file, "w") as f:
                json.dump(self.index, f, indent=2)
            logger.info(f"Saved index with {len(self.index)} letters")
        except Exception as e:
            logger.error(f"Error saving index: {e}")

    def download_all_letters(self, limit: int = 5) -> int:
        """
        Download shareholder letters (limited for demo).

        Args:
            limit: Maximum number of letters to download (default: 5 for demo)

        Returns:
            Number of letters downloaded
        """
        logger.info("Fetching Berkshire letters index page...")

        try:
            response = requests.get(self.LETTERS_URL, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            # Find all letter links
            letter_links = []
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if "/letters/" in href and any(str(year) in href for year in range(1977, 2025)):
                    full_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"
                    letter_links.append(full_url)

            # Deduplicate and sort
            letter_links = sorted(set(letter_links), reverse=True)
            logger.info(f"Found {len(letter_links)} letter links")

            # Download limited number
            downloaded = 0
            for url in letter_links[:limit]:
                year = self._extract_year(url)
                if year and year not in self.index:
                    if self._download_letter(year, url):
                        downloaded += 1

            self._save_index()
            logger.info(f"Downloaded {downloaded} new letters")
            return downloaded

        except Exception as e:
            logger.error(f"Error downloading letters: {e}")
            return 0

    def _extract_year(self, url: str) -> int | None:
        """Extract year from letter URL."""
        match = re.search(r"(19|20)\d{2}", url)
        if match:
            year = int(match.group(0))
            if 1977 <= year <= 2024:
                return year
        return None

    def _download_letter(self, year: int, url: str) -> bool:
        """Download a single letter."""
        try:
            logger.info(f"Downloading {year} letter from {url}")
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            # Determine file type
            content_type = response.headers.get("Content-Type", "").lower()
            is_pdf = "pdf" in content_type or url.endswith(".pdf")

            # Save raw file
            ext = "pdf" if is_pdf else "html"
            raw_file = self.raw_dir / f"{year}.{ext}"

            with open(raw_file, "wb") as f:
                f.write(response.content)

            # Parse content
            text = self._parse_pdf(raw_file) if is_pdf else self._parse_html(response.text)

            if not text:
                logger.warning(f"No text extracted from {year} letter")
                return False

            # Save parsed text
            parsed_file = self.parsed_dir / f"{year}.txt"
            with open(parsed_file, "w", encoding="utf-8") as f:
                f.write(text)

            # Update index
            self.index[str(year)] = {
                "year": year,
                "url": url,
                "raw_file": str(raw_file),
                "parsed_file": str(parsed_file),
                "file_type": ext,
                "downloaded_at": datetime.now().isoformat(),
                "char_count": len(text),
                "word_count": len(text.split()),
            }

            logger.info(f"✓ Downloaded and parsed {year} letter ({len(text)} chars)")
            return True

        except Exception as e:
            logger.error(f"Error downloading {year} letter: {e}")
            return False

    def _parse_pdf(self, file_path: Path) -> str:
        """Parse PDF to text."""
        if PyPDF2 is None:
            logger.error("PyPDF2 not installed - cannot parse PDF files")
            return ""

        try:
            text_parts = []
            with open(file_path, "rb") as f:
                pdf_reader = PyPDF2.PdfReader(f)
                for page in pdf_reader.pages:
                    text_parts.append(page.extract_text())

            return "\n\n".join(text_parts)

        except Exception as e:
            logger.error(f"Error parsing PDF {file_path}: {e}")
            return ""

    def _parse_html(self, html_content: str) -> str:
        """Parse HTML to text."""
        try:
            soup = BeautifulSoup(html_content, "html.parser")

            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()

            # Get text
            text = soup.get_text()

            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = "\n".join(chunk for chunk in chunks if chunk)

            return text

        except Exception as e:
            logger.error(f"Error parsing HTML: {e}")
            return ""

    def search(self, query: str, top_k: int = 3) -> dict[str, Any]:
        """
        Search shareholder letters for relevant content.

        Args:
            query: Search query
            top_k: Number of top results to return

        Returns:
            Search results with excerpts and years
        """
        logger.info(f"Searching letters for: '{query}'")

        if not self.index:
            logger.warning("No letters in index")
            return {
                "query": query,
                "relevant_excerpts": [],
                "years_referenced": [],
                "sentiment": "No data available",
                "source": "berkshire_letters",
            }

        # Search each letter
        results = []
        for year_str, letter_info in self.index.items():
            parsed_file = Path(letter_info["parsed_file"])

            if not parsed_file.exists():
                continue

            # Load text
            with open(parsed_file, encoding="utf-8") as f:
                text = f.read()

            # Simple keyword search
            relevance_score = self._calculate_relevance(query, text)

            if relevance_score > 0:
                excerpts = self._extract_excerpts(query, text, max_excerpts=2)

                results.append(
                    {
                        "year": int(year_str),
                        "relevance_score": relevance_score,
                        "excerpts": excerpts,
                        "url": letter_info["url"],
                    }
                )

        # Sort by relevance
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        results = results[:top_k]

        return {
            "query": query,
            "relevant_excerpts": [
                {"year": r["year"], "excerpts": r["excerpts"], "url": r["url"]} for r in results
            ],
            "years_referenced": [r["year"] for r in results],
            "sentiment": (
                results[0]["excerpts"][0][:300] + "..."
                if results and results[0]["excerpts"]
                else "No relevant excerpts found"
            ),
            "source": "berkshire_letters",
        }

    def _calculate_relevance(self, query: str, text: str) -> float:
        """Calculate relevance score between query and text."""
        query_lower = query.lower()
        text_lower = text.lower()

        # Extract query keywords (ignore common words)
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "is",
            "are",
            "was",
            "were",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
        }
        query_words = [w for w in query_lower.split() if w not in stop_words]

        if not query_words:
            return 0.0

        # Count keyword matches
        total_matches = sum(text_lower.count(word) for word in query_words)

        # Normalize by text length
        text_word_count = len(text_lower.split())
        normalized_score = (total_matches / len(query_words)) * (1000 / max(text_word_count, 1000))

        return normalized_score

    def _extract_excerpts(self, query: str, text: str, max_excerpts: int = 2) -> list[str]:
        """Extract relevant excerpts from text containing query keywords."""
        query_lower = query.lower()
        sentences = re.split(r"[.!?]+", text)

        # Find sentences containing query keywords
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "is",
            "are",
            "was",
            "were",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
        }
        query_words = [w for w in query_lower.split() if w not in stop_words]

        relevant_sentences = []
        for sentence in sentences:
            sentence_lower = sentence.lower()
            if any(word in sentence_lower for word in query_words):
                clean_sentence = sentence.strip()
                if len(clean_sentence) > 50:
                    relevant_sentences.append(clean_sentence)

        # Sort by number of keyword matches
        def count_matches(sentence):
            return sum(1 for word in query_words if word in sentence.lower())

        relevant_sentences.sort(key=count_matches, reverse=True)

        return relevant_sentences[:max_excerpts]


def main():
    """Demo the Berkshire letters collector."""
    print("=" * 80)
    print("BERKSHIRE HATHAWAY SHAREHOLDER LETTERS COLLECTOR - DEMO")
    print("=" * 80)
    print()

    # Initialize collector
    collector = SimpleBerkshireCollector()
    print(f"✓ Collector initialized (cache: {collector.cache_dir})")
    print()

    # Check cache
    if len(collector.index) > 0:
        print(f"✓ Found {len(collector.index)} cached letters")
        print(f"  Years: {sorted([int(y) for y in collector.index])}")
    else:
        print("Downloading sample letters (limited to 5 for demo)...")
        count = collector.download_all_letters(limit=5)
        print(f"✓ Downloaded {count} letters")
    print()

    # Demo search
    if len(collector.index) > 0:
        print("-" * 80)
        print("DEMO SEARCH: 'index funds'")
        print("-" * 80)
        results = collector.search("index funds", top_k=2)
        print(f"Query: {results['query']}")
        print(f"Years referenced: {results['years_referenced']}")
        print(f"\nBuffett's view (excerpt): {results['sentiment'][:250]}...")
        print()

        for i, excerpt in enumerate(results["relevant_excerpts"], 1):
            print(f"{i}. Year {excerpt['year']}:")
            for _j, text in enumerate(excerpt["excerpts"][:1], 1):
                print(f"   {text[:200]}...")
        print()

    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total letters cached: {len(collector.index)}")
    print(f"Cache location: {collector.cache_dir}")
    print()
    print("✓ Demo completed successfully!")
    print()
    print("Full collector available at:")
    print("  src/rag/collectors/berkshire_collector.py")
    print()


if __name__ == "__main__":
    main()
