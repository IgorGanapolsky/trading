#!/usr/bin/env python3
"""
Smoke tests for Autonomous Security Fix Agent

Quick validation that the agent can:
1. Parse requirements.txt correctly
2. Fetch PyPI data
3. Identify vulnerable versions
4. Calculate safe versions
5. Update requirements.txt (dry-run)

Run with: python3 tests/test_security_fix_agent_smoke.py
"""

import sys
import tempfile
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.autonomous_security_fix_agent import (
    fetch_pypi_latest,
    find_safe_version,
    parse_vulnerable_range,
    update_requirements_file,
)


def test_parse_vulnerable_range():
    """Test parsing vulnerable version ranges"""
    print("🧪 Test 1: Parse vulnerable ranges...")

    # Test case 1: Standard range
    min_v, max_v = parse_vulnerable_range(">= 0, < 24.3.0")
    assert min_v is None or min_v == "0", f"Expected min=None or '0', got {min_v}"
    assert max_v == "24.3.0", f"Expected max='24.3.0', got {max_v}"
    print("   ✅ Standard range parsing works")

    # Test case 2: Range with min version
    min_v, max_v = parse_vulnerable_range(">= 1.0.0, < 1.2.0")
    assert min_v == "1.0.0", f"Expected min='1.0.0', got {min_v}"
    assert max_v == "1.2.0", f"Expected max='1.2.0', got {max_v}"
    print("   ✅ Range with min version works")

    # Test case 3: Empty range
    min_v, max_v = parse_vulnerable_range("")
    assert min_v is None, f"Expected min=None, got {min_v}"
    assert max_v is None, f"Expected max=None, got {max_v}"
    print("   ✅ Empty range handling works")

    return True


def test_fetch_pypi_latest():
    """Test fetching latest version from PyPI"""
    print("\n🧪 Test 2: Fetch PyPI latest version...")

    # Test with a well-known package
    latest = fetch_pypi_latest("black")
    assert latest is not None, "Failed to fetch latest version from PyPI"
    assert len(latest.split(".")) >= 2, f"Invalid version format: {latest}"
    print(f"   ✅ Fetched latest black version: {latest}")

    return True


def test_find_safe_version():
    """Test finding safe version outside vulnerable range"""
    print("\n🧪 Test 3: Find safe version...")

    # Test case: Black vulnerability (>= 0, < 24.3.0)
    safe_version = find_safe_version("black", ">= 0, < 24.3.0", "24.2.0")
    assert safe_version is not None, "Failed to find safe version"
    assert safe_version >= "24.3.0", f"Safe version {safe_version} should be >= 24.3.0"
    print(f"   ✅ Found safe version: {safe_version}")

    return True


def test_update_requirements_file():
    """Test updating requirements.txt"""
    print("\n🧪 Test 4: Update requirements.txt...")

    # Create temporary requirements file
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("black==24.2.0\n")
        f.write("pytest==7.4.0\n")
        temp_file = Path(f.name)

    try:
        # Update black version
        success = update_requirements_file(temp_file, "black", "24.3.0")
        assert success, "Failed to update requirements file"

        # Verify update
        content = temp_file.read_text()
        assert "black==24.3.0" in content or "black>=24.3.0" in content, (
            f"Black version not updated correctly. Content: {content}"
        )
        assert "pytest==7.4.0" in content, "Other packages should remain unchanged"
        print("   ✅ Requirements file updated correctly")

        return True
    finally:
        # Cleanup
        temp_file.unlink()


def test_imports():
    """Test that all imports work"""
    print("\n🧪 Test 5: Import validation...")

    try:
        from scripts.autonomous_security_fix_agent import (
            FixResult,
            SecurityAlert,
            fetch_dependabot_alerts,
            fix_security_alert,
        )

        # Verify imports to avoid F401
        assert SecurityAlert
        assert FixResult
        assert fetch_dependabot_alerts
        assert fix_security_alert

        print("   ✅ All imports successful")
        return True
    except ImportError as e:
        print(f"   ❌ Import failed: {e}")
        return False


def main():
    """Run all smoke tests"""
    print("=" * 60)
    print("SMOKE TESTS: Autonomous Security Fix Agent")
    print("=" * 60)
    print()

    tests = [
        ("Parse vulnerable ranges", test_parse_vulnerable_range),
        ("Fetch PyPI latest", test_fetch_pypi_latest),
        ("Find safe version", test_find_safe_version),
        ("Update requirements file", test_update_requirements_file),
        ("Import validation", test_imports),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
                print(f"   ❌ {test_name} failed")
        except Exception as e:
            failed += 1
            print(f"   ❌ {test_name} raised exception: {e}")
            import traceback

            traceback.print_exc()

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"Total: {len(tests)}")

    if failed == 0:
        print("\n🎉 All smoke tests passed!")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
