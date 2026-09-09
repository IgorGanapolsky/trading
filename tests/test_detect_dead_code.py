from pathlib import Path

from scripts.detect_dead_code import find_empty_directories


def test_namespace_package_with_subpackage_is_not_empty(tmp_path: Path) -> None:
    intel = tmp_path / "intel"
    explainx = intel / "explainx"
    explainx.mkdir(parents=True)
    (intel / "__init__.py").write_text('"""Optional intelligence adapters."""\n')
    (explainx / "__init__.py").write_text("from .ceilings import FORBIDDEN_RESETS\n")
    (explainx / "ceilings.py").write_text("FORBIDDEN_RESETS = ()\n")

    findings = find_empty_directories(tmp_path)
    assert findings == []


def test_leaf_empty_init_only_dir_is_flagged(tmp_path: Path) -> None:
    empty = tmp_path / "empty_pkg"
    empty.mkdir()
    (empty / "__init__.py").write_text("#\n")

    findings = find_empty_directories(tmp_path)
    assert len(findings) == 1
    assert "empty_pkg" in findings[0]
