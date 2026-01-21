#!/usr/bin/env python3
"""Clean up old documents from Vertex AI RAG corpus.

This script deletes outdated December 2025 lessons from the Vertex AI RAG corpus
to fix the issue where RAG returns old content instead of current 2026 guidance.

Root Cause (Jan 11, 2026):
- Vertex AI corpus accumulated old December 2025 incident reports
- These documents match queries semantically due to keywords like "trading", "CI", "failure"
- Old verbose incident reports rank higher than new concise content
- CEO testing via Vertex AI console sees old content (bypasses our webhook)

Solution:
1. List all documents in the RAG corpus
2. Delete documents with "dec" + "2025" or "dec11", "dec12" etc in filename
3. Keep all January 2026+ content
4. Re-upload trading_rules_2026.md with high priority metadata

Usage:
    # Dry run - show what would be deleted
    python3 scripts/cleanup_vertex_rag.py --dry-run

    # Actually delete old documents
    python3 scripts/cleanup_vertex_rag.py --execute

    # Delete and re-upload important 2026 content
    python3 scripts/cleanup_vertex_rag.py --execute --refresh
"""

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Documents to delete (Dec 2025 old incidents)
DELETE_PATTERNS = [
    r"dec\d+.*2025",  # dec11_2025, dec23_2025, etc
    r"ll_0[0-6]\d",  # ll_001 through ll_069 (December lessons)
    r"november.*2025",
    r"oct.*2025",
]

# Documents to keep (2026 content)
KEEP_PATTERNS = [
    r"jan.*2026",
    r"trading_rules",
    r"2026",
    r"ll_[789]\d",  # ll_070+ (January 2026 lessons)
    r"ll_1[0-3]\d",  # ll_100-139 (January 2026)
]


def get_vertex_rag_client():
    """Initialize Vertex AI and return corpus info."""
    try:
        from google.cloud import aiplatform

        # Check for service account key
        sa_key = os.getenv("GCP_SA_KEY")
        if sa_key:
            import tempfile

            # Write SA key to temp file for auth
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                f.write(sa_key)
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = f.name

            # Extract project ID
            sa_data = json.loads(sa_key)
            project_id = sa_data.get("project_id", "igor-trading-2025-v2")
        else:
            project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "igor-trading-2025-v2")

        aiplatform.init(project=project_id, location="us-central1")
        logger.info(f"Connected to project: {project_id}")

        return project_id

    except ImportError as e:
        logger.error(f"Vertex AI SDK not available: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize Vertex AI: {e}")
        return None


def list_corpus_files(corpus_name: str) -> list[dict]:
    """List all files in the RAG corpus."""
    try:
        from vertexai.preview import rag

        files = rag.list_files(corpus_name=corpus_name)
        file_list = []

        for f in files:
            file_list.append(
                {
                    "name": f.name,
                    "display_name": getattr(f, "display_name", "unknown"),
                    "state": getattr(f, "state", "unknown"),
                }
            )

        logger.info(f"Found {len(file_list)} files in corpus")
        return file_list

    except Exception as e:
        logger.error(f"Failed to list corpus files: {e}")
        return []


def should_delete(filename: str) -> bool:
    """Determine if a file should be deleted based on patterns."""
    filename_lower = filename.lower()

    # Check keep patterns first (whitelist)
    if any(re.search(pattern, filename_lower) for pattern in KEEP_PATTERNS):
        return False

    # Check delete patterns (blacklist)
    return any(re.search(pattern, filename_lower) for pattern in DELETE_PATTERNS)


def delete_file(corpus_name: str, file_name: str) -> bool:
    """Delete a file from the RAG corpus."""
    try:
        from vertexai.preview import rag

        rag.delete_file(name=file_name)
        logger.info(f"✅ Deleted: {file_name}")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to delete {file_name}: {e}")
        return False


def upload_priority_content(corpus_name: str) -> int:
    """Upload/re-upload high-priority 2026 content."""
    try:
        from vertexai.preview import rag

        uploaded = 0
        priority_files = [
            "rag_knowledge/trading_rules_2026.md",
            "rag_knowledge/lessons_learned/ll_130_investment_strategy_review_jan11.md",
            "rag_knowledge/lessons_learned/ll_131_self_healing_gap_blog_sync_jan11.md",
            "rag_knowledge/lessons_learned/ll_132_rag_stuck_on_old_content_jan11.md",
            "rag_knowledge/lessons_learned/ll_133_lying_claimed_fix_without_verification_jan11.md",
        ]

        for file_path in priority_files:
            path = Path(file_path)
            if path.exists():
                try:
                    rag.import_files(
                        corpus_name=corpus_name,
                        paths=[str(path)],
                    )
                    logger.info(f"✅ Uploaded: {file_path}")
                    uploaded += 1
                except Exception as e:
                    logger.warning(f"⚠️ Failed to upload {file_path}: {e}")

        return uploaded

    except Exception as e:
        logger.error(f"Failed to upload priority content: {e}")
        return 0


def main():
    parser = argparse.ArgumentParser(
        description="Clean up old documents from Vertex AI RAG corpus",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete old documents",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-upload high-priority 2026 content after cleanup",
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="Just list all files in the corpus",
    )

    args = parser.parse_args()

    if not args.dry_run and not args.execute and not args.list_only:
        print("ERROR: Must specify --dry-run, --execute, or --list-only")
        print("Use --dry-run first to see what would be deleted")
        return 1

    print("=" * 70)
    print("VERTEX AI RAG CORPUS CLEANUP")
    print("Fix for: RAG returning December 2025 content instead of 2026")
    print("=" * 70)
    print()

    # Initialize Vertex AI
    project_id = get_vertex_rag_client()
    if not project_id:
        print("ERROR: Could not initialize Vertex AI")
        return 1

    # Get corpus
    try:
        from vertexai.preview import rag

        corpus_name = None
        corpora = rag.list_corpora()
        for corpus in corpora:
            if corpus.display_name == "trading-system-rag":
                corpus_name = corpus.name
                break

        if not corpus_name:
            print("RAG corpus 'trading-system-rag' not found - creating it...")
            try:
                corpus = rag.create_corpus(
                    display_name="trading-system-rag",
                    description="Trade history, lessons learned, and market insights for Igor's trading system",
                )
                corpus_name = corpus.name
                print(f"✅ Created RAG corpus: {corpus_name}")
            except Exception as create_err:
                print(f"ERROR: Failed to create corpus: {create_err}")
                return 1

        print(f"Corpus: {corpus_name}")
        print()

    except Exception as e:
        print(f"ERROR: Failed to get corpus: {e}")
        return 1

    # List all files
    files = list_corpus_files(corpus_name)

    if args.list_only:
        print(f"\nAll files in corpus ({len(files)}):")
        print("-" * 50)
        for f in files:
            print(f"  {f['display_name']} ({f['state']})")
        return 0

    # Categorize files
    to_delete = []
    to_keep = []

    for f in files:
        display_name = f.get("display_name", f.get("name", ""))
        if should_delete(display_name):
            to_delete.append(f)
        else:
            to_keep.append(f)

    print(f"Files to DELETE: {len(to_delete)}")
    print(f"Files to KEEP: {len(to_keep)}")
    print()

    if to_delete:
        print("Files marked for deletion:")
        print("-" * 50)
        for f in to_delete[:20]:  # Show first 20
            print(f"  ❌ {f['display_name']}")
        if len(to_delete) > 20:
            print(f"  ... and {len(to_delete) - 20} more")
        print()

    if args.dry_run:
        print("DRY RUN - No changes made")
        print("Use --execute to actually delete files")
        return 0

    if args.execute:
        print("EXECUTING CLEANUP...")
        print()

        deleted = 0
        for f in to_delete:
            if delete_file(corpus_name, f["name"]):
                deleted += 1

        print()
        print(f"Deleted {deleted}/{len(to_delete)} files")

        if args.refresh:
            print()
            print("Uploading priority 2026 content...")
            uploaded = upload_priority_content(corpus_name)
            print(f"Uploaded {uploaded} priority files")

        print()
        print("=" * 70)
        print("CLEANUP COMPLETE")
        print("Please test Vertex AI RAG queries to verify fix")
        print("=" * 70)

        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
