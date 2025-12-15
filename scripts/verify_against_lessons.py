#!/usr/bin/env python3
"""
Verify code changes against RAG Lessons Learned.

Usage:
    python3 scripts/verify_against_lessons.py [files...]
    python3 scripts/verify_against_lessons.py --all  (checks all staged/modified files)

This script queries the RAG system for lessons learned related to the modified files.
If critical lessons are found, it alerts the user (and can block the commit).
"""

import argparse
import logging
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("verify_lessons")

def get_changed_files() -> List[str]:
    """Get list of changed files (staged + unstaged)."""
    try:
        # Staged
        staged = subprocess.check_output(
            ["git", "diff", "--name-only", "--cached"], text=True
        ).splitlines()
        # Unstaged
        unstaged = subprocess.check_output(
            ["git", "diff", "--name-only"], text=True
        ).splitlines()
        return list(set(staged + unstaged))
    except subprocess.CalledProcessError:
        logger.warning("Not a git repository or git error.")
        return []

def get_keywords_from_path(file_path: str) -> str:
    """Extract search keywords from file path."""
    path = Path(file_path)
    # Use filename stem and parent directory as keywords
    keywords = f"{path.stem} {path.parent.name}"
    # Add 'python' or language if applicable
    if path.suffix == ".py":
        keywords += " python"
    return keywords

def query_lessons(query: str, limit: int = 3) -> List[Dict[str, Any]]:
    """Query lessons learned (RAG or Fallback)."""
    # Try UnifiedRAG
    try:
        from src.rag.unified_rag import UnifiedRAG, CHROMA_AVAILABLE
        if CHROMA_AVAILABLE:
            rag = UnifiedRAG()
            results = rag.query_lessons(query, n_results=limit)
            
            cleaned_results = []
            if results["documents"]:
                for i, doc in enumerate(results["documents"][0]):
                    cleaned_results.append({
                        "content": doc,
                        "metadata": results["metadatas"][0][i],
                        "id": results["ids"][0][i]
                    })
            return cleaned_results
    except ImportError:
        pass
    except Exception:
        pass # Fallback

    # Fallback: Keyword search
    lessons_dir = PROJECT_ROOT / "rag_knowledge" / "lessons_learned"
    if not lessons_dir.exists():
        return []

    results = []
    query_terms = query.lower().split()
    
    for md_file in lessons_dir.glob("*.md"):
        try:
            content = md_file.read_text(errors="replace")
            content_lower = content.lower()
            score = sum(1 for term in query_terms if term in content_lower)
            
            if score > 0:
                results.append({
                    "content": content,
                    "metadata": {"source": md_file.name, "severity": "unknown"},
                    "score": score
                })
        except:
            pass
            
    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return results[:limit]

def main():
    parser = argparse.ArgumentParser(description="Verify changes against Lessons Learned")
    parser.add_argument("files", nargs="*", help="Files to check")
    parser.add_argument("--all", action="store_true", help="Check all changed files")
    parser.add_argument("--strict", action="store_true", help="Fail on critical lessons")
    args = parser.parse_args()

    files = args.files
    if args.all or not files:
        files = get_changed_files()

    if not files:
        logger.info("No files to check.")
        return 0

    logger.info(f"Checking {len(files)} files against RAG Lessons Learned...")
    
    found_issues = False
    
    for file_path in files:
        if not Path(file_path).exists():
            continue
            
        # Skip some files
        if file_path.endswith(".md") or file_path.endswith(".json") or "test" in file_path:
            continue

        keywords = get_keywords_from_path(file_path)
        lessons = query_lessons(keywords, limit=2)
        
        if lessons:
            print(f"\n📂 {file_path} (Keywords: {keywords})")
            for lesson in lessons:
                severity = lesson["metadata"].get("severity", "medium").lower()
                icon = "🔴" if severity in ["high", "critical"] else "⚠️"
                source = lesson["metadata"].get("source", "unknown")
                
                print(f"  {icon} [{severity.upper()}] {source}")
                print(f"     {lesson['content'][:150].replace(chr(10), ' ')}...")
                
                if severity in ["high", "critical"]:
                    found_issues = True

    print()
    if found_issues:
        logger.warning("🔴 Critical lessons found! Please review above warnings.")
        if args.strict:
            return 1
    else:
        logger.info("✅ No critical lessons found for these changes.")

    return 0

if __name__ == "__main__":
    sys.exit(main())
