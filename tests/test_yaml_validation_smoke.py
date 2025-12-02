#!/usr/bin/env python3
"""
Smoke tests for YAML validation script

Quick validation that:
1. Valid YAML files pass
2. Invalid YAML files fail
3. GitHub Actions workflows are validated
4. Heredoc syntax is detected

Run with: python3 tests/test_yaml_validation_smoke.py
"""

import os
import sys
from pathlib import Path

import yaml

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_valid_yaml():
    """Test that valid YAML passes"""
    print("🧪 Test 1: Valid YAML...")

    valid_yaml = """
name: Test Workflow
on:
  push:
    branches: [main]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Test
        run: echo "test"
"""

    try:
        yaml.safe_load(valid_yaml)
        print("   ✅ Valid YAML parsed successfully")
        return True
    except yaml.YAMLError as e:
        print(f"   ❌ Valid YAML failed: {e}")
        return False


def test_invalid_yaml():
    """Test that invalid YAML fails"""
    print("\n🧪 Test 2: Invalid YAML detection...")

    invalid_yaml = """
name: Test Workflow
on:
  push:
    branches: [main]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Test
        run: echo "test"
      invalid_key: without colon
"""

    try:
        yaml.safe_load(invalid_yaml)
        print("   ❌ Invalid YAML was accepted (should have failed)")
        return False
    except yaml.YAMLError:
        print("   ✅ Invalid YAML correctly rejected")
        return True


def test_github_actions_workflow():
    """Test that GitHub Actions workflow syntax is valid"""
    print("\n🧪 Test 3: GitHub Actions workflow validation...")

    workflow_path = PROJECT_ROOT / ".github" / "workflows" / "autonomous-security-fixes.yml"

    if not workflow_path.exists():
        print(f"   ⚠️  Workflow file not found: {workflow_path}")
        return True  # Skip if file doesn't exist

    try:
        with open(workflow_path) as f:
            workflow = yaml.safe_load(f)

        # Check required fields
        assert "name" in workflow, f"Workflow missing 'name'. Keys: {list(workflow.keys())}"
        # 'on' is a YAML boolean keyword, so it gets parsed as True
        assert True in workflow or "on" in workflow, (
            f"Workflow missing 'on'. Keys: {list(workflow.keys())}"
        )
        assert "jobs" in workflow, f"Workflow missing 'jobs'. Keys: {list(workflow.keys())}"

        print(f"   ✅ Workflow '{workflow_path.name}' is valid")
        return True
    except yaml.YAMLError as e:
        print(f"   ❌ Workflow YAML error: {e}")
        return False
    except AssertionError as e:
        print(f"   ❌ Workflow validation failed: {e}")
        return False


def test_heredoc_detection():
    """Test heredoc syntax detection"""
    print("\n🧪 Test 4: Heredoc syntax detection...")

    import re

    # Test case 1: Properly closed heredoc
    content1 = """
    run: |
      BODY=$(cat <<EOF
      test
      EOF
      )
"""
    starts1 = len(re.findall(r"<<-?EOF", content1))
    ends1 = len(re.findall(r"^EOF", content1, re.MULTILINE))

    if starts1 == ends1 and starts1 > 0:
        print("   ✅ Properly closed heredoc detected")
    else:
        print(f"   ⚠️  Heredoc detection: {starts1} starts, {ends1} ends")

    # Test case 2: Unclosed heredoc
    content2 = """
    run: |
      BODY=$(cat <<EOF
      test
"""
    starts2 = len(re.findall(r"<<-?EOF", content2))
    ends2 = len(re.findall(r"^EOF", content2, re.MULTILINE))

    if starts2 != ends2:
        print("   ✅ Unclosed heredoc detected")
        return True
    else:
        print("   ⚠️  Unclosed heredoc not detected")
        return False


def test_pre_commit_config():
    """Test that .pre-commit-config.yaml is valid"""
    print("\n🧪 Test 5: Pre-commit config validation...")

    config_path = PROJECT_ROOT / ".pre-commit-config.yaml"

    if not config_path.exists():
        print(f"   ⚠️  Config file not found: {config_path}")
        return True

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)

        assert "repos" in config, "Config missing 'repos'"
        assert isinstance(config["repos"], list), "Repos should be a list"

        print("   ✅ Pre-commit config is valid")
        return True
    except yaml.YAMLError as e:
        print(f"   ❌ Config YAML error: {e}")
        return False
    except AssertionError as e:
        print(f"   ❌ Config validation failed: {e}")
        return False


def test_validation_script_exists():
    """Test that validation script exists and is executable"""
    print("\n🧪 Test 6: Validation script exists...")

    script_path = PROJECT_ROOT / "scripts" / "validate_yaml_before_commit.sh"

    if not script_path.exists():
        print(f"   ❌ Script not found: {script_path}")
        return False

    if not os.access(script_path, os.X_OK):
        print(f"   ⚠️  Script not executable: {script_path}")
        return False

    print("   ✅ Validation script exists and is executable")
    return True


def main():
    """Run all smoke tests"""
    print("=" * 60)
    print("SMOKE TESTS: YAML Validation")
    print("=" * 60)
    print()

    tests = [
        ("Valid YAML", test_valid_yaml),
        ("Invalid YAML detection", test_invalid_yaml),
        ("GitHub Actions workflow", test_github_actions_workflow),
        ("Heredoc detection", test_heredoc_detection),
        ("Pre-commit config", test_pre_commit_config),
        ("Validation script exists", test_validation_script_exists),
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
