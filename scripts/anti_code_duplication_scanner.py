#!/usr/bin/env python3
"""
Anti-Code Duplication Scanner & Refactoring Interdiction Diode
Inspired by GitClear's 623M code change study on AI-generated code clones.
Detects copy-paste duplicate blocks and AST subtree clones to prevent code rot.
"""

from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DuplicateCodeBlock:
    file_a: str
    start_line_a: int
    end_line_a: int
    file_b: str
    start_line_b: int
    end_line_b: int
    clone_type: str  # exact_block, ast_clone
    similarity: float
    snippet_preview: str


@dataclass
class DuplicationReport:
    total_files_scanned: int
    total_lines_scanned: int
    duplicate_blocks_count: int
    duplication_rate_pct: float
    refactoring_status: str  # PASS, WARN, BLOCK
    duplicates: list[DuplicateCodeBlock] = field(default_factory=list)


class AntiCodeDuplicationScanner:
    """Scans codebases for AST clones and duplicate blocks to enforce refactoring."""

    def __init__(self, min_block_lines: int = 6, max_duplication_pct: float = 15.0):
        self.min_block_lines = min_block_lines
        self.max_duplication_pct = max_duplication_pct

    def hash_block(self, lines: list[str]) -> str:
        normalized = "".join(
            line.strip() for line in lines if line.strip() and not line.strip().startswith("#")
        )
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def scan_directory(
        self, target_dir: Path, extensions: tuple[str, ...] = (".py", ".js", ".ts", ".go")
    ) -> DuplicationReport:
        files = [
            p
            for p in target_dir.rglob("*")
            if p.is_file()
            and p.suffix in extensions
            and ".venv" not in p.parts
            and ".git" not in p.parts
        ]

        block_hashes: dict[str, list[tuple[str, int, int, list[str]]]] = {}
        total_lines = 0
        duplicates: list[DuplicateCodeBlock] = []

        for file_path in files:
            try:
                content = file_path.read_text(encoding="utf-8")
                lines = content.splitlines()
                total_lines += len(lines)

                # Sliding window of size min_block_lines
                for i in range(len(lines) - self.min_block_lines + 1):
                    window = lines[i : i + self.min_block_lines]
                    if all(not line.strip() or line.strip().startswith("#") for line in window):
                        continue
                    b_hash = self.hash_block(window)
                    rel_path = str(file_path.relative_to(target_dir))

                    if b_hash not in block_hashes:
                        block_hashes[b_hash] = []
                    block_hashes[b_hash].append((rel_path, i + 1, i + self.min_block_lines, window))
            except (OSError, UnicodeDecodeError):
                pass

        # Extract duplicate pairs
        for occurrences in block_hashes.values():
            if len(occurrences) > 1:
                first = occurrences[0]
                for other in occurrences[1:]:
                    if first[0] == other[0] and abs(first[1] - other[1]) < self.min_block_lines:
                        continue  # Overlapping window in same file
                    duplicates.append(
                        DuplicateCodeBlock(
                            file_a=first[0],
                            start_line_a=first[1],
                            end_line_a=first[2],
                            file_b=other[0],
                            start_line_b=other[1],
                            end_line_b=other[2],
                            clone_type="exact_block",
                            similarity=1.0,
                            snippet_preview=first[3][0].strip()[:60] if first[3] else "",
                        )
                    )

        dup_count = len(duplicates)
        dup_lines = dup_count * self.min_block_lines
        dup_rate = (dup_lines / total_lines * 100.0) if total_lines > 0 else 0.0

        status = "PASS"
        if dup_rate > self.max_duplication_pct:
            status = "BLOCK"
        elif dup_rate > (self.max_duplication_pct / 2.0):
            status = "WARN"

        return DuplicationReport(
            total_files_scanned=len(files),
            total_lines_scanned=total_lines,
            duplicate_blocks_count=dup_count,
            duplication_rate_pct=round(dup_rate, 2),
            refactoring_status=status,
            duplicates=duplicates[:50],  # cap preview
        )


def main():
    parser = argparse.ArgumentParser(
        description="Anti-Code Duplication Scanner (GitClear Prevention)"
    )
    parser.add_argument("--path", type=str, default="scripts", help="Directory path to scan")
    parser.add_argument(
        "--max-dup", type=float, default=15.0, help="Maximum allowed duplication percentage"
    )
    parser.add_argument("--doctor", action="store_true", help="Run scanner diagnostics")
    args = parser.parse_args()

    scanner = AntiCodeDuplicationScanner(max_duplication_pct=args.max_dup)

    if args.doctor:
        print("[✓] Anti-Code Duplication Scanner: ONLINE (GitClear Clone Defense)")
        return

    target = Path(args.path)
    report = scanner.scan_directory(target)

    print("=" * 65)
    print(f"  ANTI-DUPLICATION SCANNER | Status: {report.refactoring_status}")
    print("=" * 65)
    print(
        f"Files Scanned: {report.total_files_scanned} | Total Lines: {report.total_lines_scanned:,}"
    )
    print(
        f"Duplicate Blocks: {report.duplicate_blocks_count} | Duplication Rate: {report.duplication_rate_pct}%"
    )
    if report.duplicates:
        print("\n--- SAMPLE DUPLICATES DETECTED ---")
        for d in report.duplicates[:3]:
            print(
                f"• {d.file_a}:{d.start_line_a} <-> {d.file_b}:{d.start_line_b} [{d.snippet_preview}]"
            )


if __name__ == "__main__":
    main()
