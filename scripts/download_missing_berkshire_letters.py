#!/usr/bin/env python3
"""
Download Missing Berkshire Hathaway Shareholder Letters.

Downloads the missing years (1977-2009, 2024) that were not available
during the initial collection due to network restrictions.

Usage:
    python scripts/download_missing_berkshire_letters.py
    python scripts/download_missing_berkshire_letters.py --year 2024  # Download specific year
    python scripts/download_missing_berkshire_letters.py --all        # Download all missing

After downloading, run:
    python scripts/ingest_berkshire_letters.py

Letter URLs (for manual download if needed):
- https://www.berkshirehathaway.com/letters/1977.html
- https://www.berkshirehathaway.com/letters/1978.html
- ...
- https://www.berkshirehathaway.com/letters/2024ltr.pdf
"""

import argparse
import logging
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Letter URL patterns
BASE_URL = "https://www.berkshirehathaway.com"
LETTERS_INDEX = f"{BASE_URL}/letters/letters.html"

# Known URL patterns for different years
LETTER_PATTERNS = {
    # Early years (1977-1997) are typically HTML
    **{year: f"{BASE_URL}/letters/{year}.html" for year in range(1977, 1998)},
    # Later years (1998-2023) are typically PDF
    **{year: f"{BASE_URL}/letters/{year}ltr.pdf" for year in range(1998, 2024)},
    # 2024 has the 'ltr' suffix
    2024: f"{BASE_URL}/letters/2024ltr.pdf",
}


def get_headers():
    """Standard headers to avoid 403 errors."""
    return {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }


def get_missing_years(parsed_dir: Path) -> list[int]:
    """Get list of years not yet downloaded."""
    existing = {int(f.stem) for f in parsed_dir.glob("*.txt")}
    all_years = set(range(1977, 2025))
    return sorted(all_years - existing)


def download_letter(year: int, cache_dir: Path) -> bool:
    """Download a single letter."""
    raw_dir = cache_dir / "raw"
    parsed_dir = cache_dir / "parsed"
    raw_dir.mkdir(parents=True, exist_ok=True)
    parsed_dir.mkdir(parents=True, exist_ok=True)

    # Try known URL pattern
    url = LETTER_PATTERNS.get(year)
    if not url:
        logger.error(f"No URL pattern for year {year}")
        return False

    try:
        logger.info(f"Downloading {year} letter from {url}...")
        response = requests.get(url, headers=get_headers(), timeout=30)
        response.raise_for_status()

        # Determine file type
        is_pdf = url.endswith(".pdf") or "pdf" in response.headers.get("Content-Type", "").lower()
        ext = "pdf" if is_pdf else "html"
        raw_file = raw_dir / f"{year}.{ext}"

        # Save raw file
        with open(raw_file, "wb") as f:
            f.write(response.content)
        logger.info(f"  Saved raw file: {raw_file}")

        # Parse content
        if is_pdf:
            text = parse_pdf(raw_file)
        else:
            text = parse_html(response.text)

        if not text:
            logger.warning(f"  Could not extract text from {year} letter")
            return False

        # Save parsed text
        parsed_file = parsed_dir / f"{year}.txt"
        with open(parsed_file, "w", encoding="utf-8") as f:
            f.write(text)

        logger.info(f"  ✓ {year}: {len(text):,} chars, {len(text.split()):,} words")
        return True

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            # Try alternate URL patterns
            alternates = [
                f"{BASE_URL}/letters/{year}ltr.pdf",
                f"{BASE_URL}/letters/{year}.pdf",
                f"{BASE_URL}/letters/{year}.html",
                f"{BASE_URL}/letters/{year}ltr.html",
            ]
            for alt_url in alternates:
                if alt_url != url:
                    try:
                        response = requests.get(alt_url, headers=get_headers(), timeout=30)
                        if response.status_code == 200:
                            logger.info(f"  Found at alternate URL: {alt_url}")
                            # Save and parse...
                            return download_letter_from_response(year, alt_url, response, cache_dir)
                    except Exception:
                        pass
        logger.error(f"  ✗ HTTP Error downloading {year}: {e}")
        return False
    except Exception as e:
        logger.error(f"  ✗ Error downloading {year}: {e}")
        return False


def download_letter_from_response(year: int, url: str, response, cache_dir: Path) -> bool:
    """Save letter from an already-fetched response."""
    raw_dir = cache_dir / "raw"
    parsed_dir = cache_dir / "parsed"

    is_pdf = url.endswith(".pdf") or "pdf" in response.headers.get("Content-Type", "").lower()
    ext = "pdf" if is_pdf else "html"
    raw_file = raw_dir / f"{year}.{ext}"

    with open(raw_file, "wb") as f:
        f.write(response.content)

    if is_pdf:
        text = parse_pdf(raw_file)
    else:
        text = parse_html(response.text)

    if text:
        parsed_file = parsed_dir / f"{year}.txt"
        with open(parsed_file, "w", encoding="utf-8") as f:
            f.write(text)
        logger.info(f"  ✓ {year}: {len(text):,} chars")
        return True
    return False


def parse_pdf(file_path: Path) -> str:
    """Parse PDF to text."""
    try:
        import PyPDF2

        text_parts = []
        with open(file_path, "rb") as f:
            pdf_reader = PyPDF2.PdfReader(f)
            for page in pdf_reader.pages:
                text_parts.append(page.extract_text())
        return "\n\n".join(text_parts)
    except ImportError:
        logger.error("PyPDF2 not installed - run: pip install PyPDF2")
        return ""
    except Exception as e:
        logger.error(f"Error parsing PDF: {e}")
        return ""


def parse_html(html_content: str) -> str:
    """Parse HTML to text."""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        for script in soup(["script", "style"]):
            script.decompose()
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        return "\n".join(chunk for chunk in chunks if chunk)
    except Exception as e:
        logger.error(f"Error parsing HTML: {e}")
        return ""


def main():
    parser = argparse.ArgumentParser(
        description="Download missing Berkshire Hathaway shareholder letters"
    )
    parser.add_argument("--year", type=int, help="Download specific year")
    parser.add_argument("--all", action="store_true", help="Download all missing years")
    parser.add_argument(
        "--list", action="store_true", help="List missing years without downloading"
    )
    args = parser.parse_args()

    cache_dir = Path("data/rag/berkshire_letters")
    parsed_dir = cache_dir / "parsed"

    missing = get_missing_years(parsed_dir)

    if args.list:
        logger.info(f"Missing years ({len(missing)}): {missing}")
        return

    if not args.year and not args.all:
        logger.info(
            f"Missing {len(missing)} years: {missing[:10]}{'...' if len(missing) > 10 else ''}"
        )
        logger.info("\nUsage:")
        logger.info("  --list        List all missing years")
        logger.info("  --year 2024   Download specific year")
        logger.info("  --all         Download all missing years")
        return

    if args.year:
        if args.year not in missing:
            logger.info(f"Year {args.year} already downloaded or out of range")
            return
        success = download_letter(args.year, cache_dir)
        sys.exit(0 if success else 1)

    if args.all:
        logger.info(f"Downloading {len(missing)} missing letters...")
        success_count = 0
        for year in missing:
            if download_letter(year, cache_dir):
                success_count += 1

        logger.info(f"\n✓ Downloaded {success_count}/{len(missing)} letters")
        if success_count > 0:
            logger.info("\nRun this to ingest into RAG:")
            logger.info("  python scripts/ingest_berkshire_letters.py")


if __name__ == "__main__":
    main()
