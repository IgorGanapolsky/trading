from pathlib import Path

from scripts.audit_repository_hygiene import (
    LOCAL_PATH_PATTERN,
    lesson_id,
    normalize_lesson_id,
    physical_line_count,
    scan,
)


def test_physical_line_count_handles_empty_and_missing_newline() -> None:
    assert physical_line_count(b"") == 0
    assert physical_line_count(b"one\n") == 1
    assert physical_line_count(b"one\ntwo") == 2


def test_normalize_and_extract_lesson_id() -> None:
    assert normalize_lesson_id("ll_0280") == "LL-280"
    assert (
        lesson_id("rag_knowledge/lessons_learned/ll_999_wrong.md", "---\nid: LL-327\n---\n")
        == "LL-327"
    )
    assert lesson_id("rag_knowledge/lessons_learned/ll_327_title.md", "# Title") == "LL-327"


def test_local_path_pattern_rejects_machine_paths_not_ellipsis() -> None:
    assert LOCAL_PATH_PATTERN.search("/Users/igorganapolsky/workspace/git/igor/trading")
    assert LOCAL_PATH_PATTERN.search("see /Users/someone/.config/foo")
    assert LOCAL_PATH_PATTERN.search("/Users/.../trading") is None


def test_scan_flags_absolute_user_path_outside_tests(tmp_path: Path, monkeypatch) -> None:
    """Regression for PR #4515: RAG lessons with /Users/<user>/ fail hygiene CI."""
    from scripts import audit_repository_hygiene as hyg

    lessons = tmp_path / "rag_knowledge" / "lessons_learned"
    lessons.mkdir(parents=True)
    (lessons / "ll_999_bad.md").write_text(
        "# LL-999\nRan from /Users/igorganapolsky/workspace/git/igor/trading\n",
        encoding="utf-8",
    )
    (lessons / "ll_998_ok.md").write_text(
        "# LL-998\nExample path /Users/.../trading is scrubbed\n",
        encoding="utf-8",
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "fixture.py").write_text('PATH = "/Users/igorganapolsky/x"\n', encoding="utf-8")

    monkeypatch.setattr(
        hyg,
        "candidate_paths",
        lambda _repo: [
            "rag_knowledge/lessons_learned/ll_999_bad.md",
            "rag_knowledge/lessons_learned/ll_998_ok.md",
            "tests/fixture.py",
        ],
    )

    report = scan(tmp_path)
    absolute = [f for f in report["findings"] if f["kind"] == "absolute-user-path"]
    assert len(absolute) == 1
    assert absolute[0]["path"] == "rag_knowledge/lessons_learned/ll_999_bad.md"
    assert report["errors"] >= 1


def test_check_staged_absolute_paths_helper(tmp_path: Path) -> None:
    from scripts.check_staged_absolute_paths import check_paths

    docs = tmp_path / "docs"
    docs.mkdir()
    bad = docs / "note.md"
    bad.write_text("root=/Users/igorganapolsky/workspace\n", encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "ok.py").write_text('p="/Users/igorganapolsky/x"\n', encoding="utf-8")

    assert check_paths(tmp_path, ["docs/note.md", "tests/ok.py"]) == ["docs/note.md"]


def test_check_staged_reads_index_not_working_tree(tmp_path: Path) -> None:
    """Staged blob with /Users path must fail even if working tree was scrubbed."""
    import subprocess

    from scripts.check_staged_absolute_paths import check_paths, main

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "test"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    note = docs / "note.md"
    note.write_text("root=/Users/igorganapolsky/workspace\n", encoding="utf-8")
    subprocess.run(["git", "add", "docs/note.md"], cwd=tmp_path, check=True, capture_output=True)
    # Working tree cleaned after staging — index still has the bad path.
    note.write_text("root=/Users/.../workspace\n", encoding="utf-8")

    assert check_paths(tmp_path, ["docs/note.md"], from_index=True) == ["docs/note.md"]
    assert check_paths(tmp_path, ["docs/note.md"], from_index=False) == []
    assert main(["--repo-root", str(tmp_path)]) == 1
