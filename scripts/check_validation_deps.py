#!/usr/bin/env python3
"""
Check if all dependencies for 5-year validation are installed.

Usage:
    python scripts/check_validation_deps.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

REQUIRED_PACKAGES = {
    "numpy": "Numerical computing",
    "pandas": "Data manipulation",
    "yfinance": "Financial data fetching",
    "scipy": "Scientific computing (for confidence intervals)",
}

REQUIRED_MODULES = {
    "src.backtesting.walk_forward_matrix": "Walk-forward validation framework",
    "src.strategies.core_strategy": "Core trading strategy",
}


def check_packages():
    """Check if all required packages are installed."""
    print("Checking required packages...\n")

    missing = []
    installed = []

    for package, description in REQUIRED_PACKAGES.items():
        try:
            __import__(package)
            print(f"✅ {package:<15} - {description}")
            installed.append(package)
        except ImportError:
            print(f"❌ {package:<15} - {description}")
            missing.append(package)

    return missing, installed


def check_modules():
    """Check if required project modules exist."""
    print("\nChecking project modules...\n")

    missing = []
    available = []

    for module, description in REQUIRED_MODULES.items():
        try:
            __import__(module)
            print(f"✅ {module:<45} - {description}")
            available.append(module)
        except ImportError as e:
            print(f"❌ {module:<45} - {description}")
            print(f"   Error: {e}")
            missing.append(module)

    return missing, available


def main():
    print("=" * 80)
    print("5-Year Validation Dependency Check")
    print("=" * 80)
    print()

    # Check packages
    missing_packages, installed_packages = check_packages()

    # Check modules
    missing_modules, available_modules = check_modules()

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    total_packages = len(REQUIRED_PACKAGES)
    total_modules = len(REQUIRED_MODULES)

    print(f"\nPackages: {len(installed_packages)}/{total_packages} installed")
    print(f"Modules: {len(available_modules)}/{total_modules} available")

    if missing_packages or missing_modules:
        print("\n❌ FAILED - Missing dependencies")

        if missing_packages:
            print("\nMissing packages:")
            for pkg in missing_packages:
                print(f"  - {pkg}")
            print("\nTo install missing packages:")
            print("  pip install -r requirements.txt")
            print("  # or")
            print(f"  pip install {' '.join(missing_packages)}")

        if missing_modules:
            print("\nMissing modules:")
            for mod in missing_modules:
                print(f"  - {mod}")
            print("\nEnsure you're running from the project root directory.")

        sys.exit(1)
    else:
        print("\n✅ PASSED - All dependencies available")
        print("\nYou can now run:")
        print("  python scripts/run_5year_validation.py")
        sys.exit(0)


if __name__ == "__main__":
    main()
