#!/usr/bin/env python3
"""
Auto-download missing Berkshire letters on startup.

This script runs automatically during system initialization to attempt
downloading any missing Buffett shareholder letters. It's designed to
be idempotent and network-failure tolerant.

Called by: init.sh or session startup
"""

import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)


def get_missing_years() -> list[int]:
    """Get list of years not yet downloaded."""
    parsed_dir = Path("data/rag/berkshire_letters/parsed")
    if not parsed_dir.exists():
        return list(range(1977, 2025))

    existing = {int(f.stem) for f in parsed_dir.glob("*.txt")}
    all_years = set(range(1977, 2025))
    return sorted(all_years - existing)


def attempt_download() -> dict:
    """Attempt to download missing letters."""
    missing = get_missing_years()

    if not missing:
        logger.info("All Berkshire letters already downloaded (1977-2024)")
        return {"status": "complete", "missing": 0}

    logger.info(f"Attempting to download {len(missing)} missing letters...")

    # Import the download function
    try:
        from scripts.download_missing_berkshire_letters import download_letter

        cache_dir = Path("data/rag/berkshire_letters")
        downloaded = 0
        failed = []

        for year in missing:
            try:
                if download_letter(year, cache_dir):
                    downloaded += 1
                    logger.info(f"  Downloaded {year}")
            except Exception as e:
                failed.append(year)
                # Don't log every failure - network might be blocked

        if downloaded > 0:
            logger.info(f"Downloaded {downloaded} new letters")

            # Ingest into RAG
            try:
                from scripts.ingest_berkshire_letters import ingest_berkshire_letters
                result = ingest_berkshire_letters()
                logger.info(f"Ingested into RAG: {result.get('letters_ingested', 0)} letters")
            except Exception as e:
                logger.warning(f"Could not ingest into RAG: {e}")

        return {
            "status": "partial" if failed else "success",
            "downloaded": downloaded,
            "remaining": len(missing) - downloaded,
        }

    except Exception as e:
        # Network likely blocked - this is expected in some environments
        logger.debug(f"Download attempt failed (expected if network restricted): {e}")
        return {"status": "blocked", "missing": len(missing)}


def main():
    """Run auto-download check."""
    missing = get_missing_years()

    if not missing:
        print("All 48 Berkshire letters (1977-2024) available")
        return

    print(f"Missing {len(missing)} Berkshire letters - attempting download...")
    result = attempt_download()

    if result["status"] == "complete":
        print("All letters now available")
    elif result["status"] == "blocked":
        print(f"Network restricted - {result['missing']} letters still missing")
        print("Will retry on next startup")
    else:
        print(f"Downloaded {result.get('downloaded', 0)}, {result.get('remaining', 0)} remaining")


if __name__ == "__main__":
    main()
