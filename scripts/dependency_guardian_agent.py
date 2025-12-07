#!/usr/bin/env python3
"""
Dependency Guardian Agent - Autonomous Dependency Management

Prevents dependency conflicts by:
1. Checking PyPI for updates and compatibility
2. Detecting deprecated packages
3. Testing dependency resolution
4. Generating actionable reports

Usage:
    python3 scripts/dependency_guardian_agent.py

Exit Codes:
    0: All dependencies healthy
    1: Issues detected (updates/deprecations/conflicts)
    2: Critical errors (network/parsing failures)
"""

import json
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class PackageInfo:
    """Information about a package from PyPI"""

    name: str
    current_version: str
    latest_version: str
    release_date: str | None = None
    requires_python: str | None = None
    is_deprecated: bool = False
    deprecation_reason: str | None = None
    is_outdated: bool = False
    pypi_url: str = ""


@dataclass
class GuardianReport:
    """Complete dependency health report"""

    timestamp: str
    python_version: str
    total_packages: int
    healthy: list[PackageInfo] = field(default_factory=list)
    outdated: list[PackageInfo] = field(default_factory=list)
    deprecated: list[PackageInfo] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)


KNOWN_DEPRECATED = {
    "alpaca-trade-api": "Migrate to alpaca-py (modern SDK)",
    "flask-cors": "Use flask.cors built-in instead",
}


def fetch_pypi_info(package_name: str, timeout: int = 10) -> dict | None:
    """Fetch package info from PyPI JSON API"""
    url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return json.loads(response.read())
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
        print(f"⚠️  Failed to fetch {package_name}: {e}")
        return None


def parse_requirements(req_file: Path) -> list[tuple[str, str]]:
    """Parse requirements.txt and extract package names with versions"""
    packages = []

    with open(req_file) as f:
        for line in f:
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue

            # Extract package name and version
            if "==" in line:
                pkg, ver = line.split("==", 1)
                pkg = pkg.strip()
                ver = ver.split("#")[0].strip()  # Remove inline comments
                packages.append((pkg, ver))
            elif ">=" in line or "<=" in line or ">" in line or "<" in line:
                # Handle version constraints
                for sep in [">=", "<=", ">", "<", "!="]:
                    if sep in line:
                        pkg = line.split(sep)[0].strip()
                        packages.append((pkg, "constrained"))
                        break

    return packages


def check_package(name: str, current_version: str) -> PackageInfo:
    """Check single package against PyPI"""
    print(f"🔍 Analyzing {name} {current_version}...")

    pypi_data = fetch_pypi_info(name)

    if not pypi_data:
        return PackageInfo(
            name=name,
            current_version=current_version,
            latest_version="unknown",
            pypi_url=f"https://pypi.org/project/{name}/",
        )

    info = pypi_data.get("info", {})
    latest_version = info.get("version", current_version)
    requires_python = info.get("requires_python", None)

    # Check for deprecation
    is_deprecated = False
    deprecation_reason = None

    if name in KNOWN_DEPRECATED:
        is_deprecated = True
        deprecation_reason = KNOWN_DEPRECATED[name]
    elif "deprecated" in info.get("description", "").lower():
        is_deprecated = True
        deprecation_reason = "Package description mentions: deprecated"

    # Check if outdated
    is_outdated = current_version != latest_version and current_version != "constrained"

    # Get latest release date
    releases = pypi_data.get("releases", {})
    release_date = None
    if latest_version in releases and releases[latest_version]:
        release_date = releases[latest_version][0].get("upload_time_iso_8601", None)

    pkg_info = PackageInfo(
        name=name,
        current_version=current_version,
        latest_version=latest_version,
        release_date=release_date,
        requires_python=requires_python,
        is_deprecated=is_deprecated,
        deprecation_reason=deprecation_reason,
        is_outdated=is_outdated,
        pypi_url=f"https://pypi.org/project/{name}/",
    )

    if is_deprecated:
        print(f"   🚨 DEPRECATED: {deprecation_reason}")
    elif is_outdated:
        print(f"   📦 Update available: {latest_version}")
    else:
        print("   ✅ Up-to-date")

    return pkg_info


def test_dependency_resolution(req_file: Path) -> list[str]:
    """Test if dependencies can be resolved without conflicts"""
    print("\n🔍 Testing dependency resolution...")

    conflicts = []

    try:
        result = subprocess.run(
            ["python3", "-m", "pip", "install", "--dry-run", "-r", str(req_file)],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            error_output = result.stderr or result.stdout

            if "ResolutionImpossible" in error_output or "Cannot install" in error_output:
                # Extract conflict details
                for line in error_output.split("\n"):
                    if "ERROR:" in line or "Cannot install" in line:
                        conflicts.append(line.strip())
                print("   ❌ Dependency conflicts detected")
            else:
                print("   ✅ No conflicts detected")
        else:
            print("   ✅ All dependencies resolve successfully")

    except subprocess.TimeoutExpired:
        conflicts.append("Dependency resolution timed out (>120s)")
        print("   ⚠️  Resolution test timed out")
    except Exception as e:
        conflicts.append(f"Resolution test failed: {str(e)}")
        print(f"   ⚠️  Resolution test error: {e}")

    return conflicts


def generate_markdown_report(report: GuardianReport, output_dir: Path) -> Path:
    """Generate comprehensive markdown report"""
    timestamp_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    report_file = output_dir / f"dependency_guardian_{timestamp_str}.md"

    output_dir.mkdir(parents=True, exist_ok=True)

    with open(report_file, "w") as f:
        f.write("# 🤖 Dependency Guardian Report\n\n")
        f.write(f"**Generated**: {report.timestamp}\n")
        f.write(f"**Python Version**: {report.python_version}\n\n")

        f.write("## 📊 Summary\n\n")
        f.write("| Metric | Count | Status |\n")
        f.write("|--------|-------|--------|\n")
        f.write(f"| Total Dependencies | {report.total_packages} | ℹ️ |\n")
        f.write(f"| Healthy | {len(report.healthy)} | ✅ |\n")
        f.write(f"| Outdated | {len(report.outdated)} | 📦 |\n")
        f.write(f"| Deprecated | {len(report.deprecated)} | 🚨 |\n")
        f.write(
            f"| Conflicts | {len(report.conflicts)} | {'❌' if report.conflicts else '✅'} |\n\n"
        )

        # Recommendations
        f.write("## 🎯 Recommendations\n\n")

        if report.deprecated:
            f.write("### 🚨 **CRITICAL**: Deprecated Packages (Immediate Action Required)\n\n")
            for pkg in report.deprecated:
                f.write(f"- **{pkg.name}** ({pkg.current_version}): {pkg.deprecation_reason}\n")
                f.write(f"  - [PyPI]({pkg.pypi_url})\n")
            f.write("\n")

        if report.conflicts:
            f.write("### ⚠️  **HIGH**: Dependency Conflicts\n\n")
            for conflict in report.conflicts:
                f.write(f"- {conflict}\n")
            f.write("\n")

        if report.outdated:
            f.write(
                f"### 📦 **MEDIUM**: {len(report.outdated)} Packages Have Updates Available\n\n"
            )
            f.write("| Package | Current | Latest | Released |\n")
            f.write("|---------|---------|--------|----------|\n")
            for pkg in report.outdated[:10]:  # Show top 10
                release_date = pkg.release_date[:10] if pkg.release_date else "unknown"
                f.write(
                    f"| [{pkg.name}]({pkg.pypi_url}) | {pkg.current_version} | {pkg.latest_version} | {release_date} |\n"
                )
            f.write("\n")

        if report.healthy:
            f.write(f"## ✅ Healthy Packages ({len(report.healthy)})\n\n")
            f.write("<details><summary>Click to expand</summary>\n\n")
            for pkg in report.healthy[:20]:  # Show top 20
                f.write(f"- {pkg.name} {pkg.current_version}\n")
            f.write("\n</details>\n\n")

        f.write("---\n\n")
        f.write("*Generated by Dependency Guardian Agent - Autonomous Dependency Management*\n")

    return report_file


def main():
    """Main entry point"""
    print("🚀 Dependency Guardian Agent Starting...")

    # Find requirements.txt
    repo_root = Path(__file__).parent.parent
    req_file = repo_root / "requirements.txt"

    if not req_file.exists():
        print(f"❌ requirements.txt not found at {req_file}")
        return 2

    print(f"📋 Requirements file: {req_file}")

    # Get Python version
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    print(f"🐍 Python version: {python_version}")

    # Parse requirements
    packages = parse_requirements(req_file)
    print(f"📦 Found {len(packages)} dependencies to analyze\n")

    # Analyze each package
    report = GuardianReport(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
        python_version=python_version,
        total_packages=len(packages),
    )

    for name, version in packages:
        pkg_info = check_package(name, version)

        if pkg_info.is_deprecated:
            report.deprecated.append(pkg_info)
        elif pkg_info.is_outdated:
            report.outdated.append(pkg_info)
        else:
            report.healthy.append(pkg_info)

    # Test dependency resolution
    report.conflicts = test_dependency_resolution(req_file)

    # Generate report
    output_dir = repo_root / "reports"
    report_file = generate_markdown_report(report, output_dir)

    print("\n📊 DEPENDENCY GUARDIAN SUMMARY")
    print("=" * 60)
    print(f"Total Dependencies: {report.total_packages}")
    print(f"Healthy: {len(report.healthy)} ✅")
    print(f"Outdated: {len(report.outdated)} 📦")
    print(f"Deprecated: {len(report.deprecated)} 🚨")
    print(f"Conflicts: {len(report.conflicts)} {'⚠️ ' if report.conflicts else '✅'}")
    print()
    print("🎯 Recommendations:")
    if report.deprecated:
        print(
            f"   🚨 **CRITICAL**: {len(report.deprecated)} deprecated packages require immediate migration"
        )
    if report.conflicts:
        print(f"   ⚠️  **HIGH**: {len(report.conflicts)} dependency conflicts detected")
    if report.outdated:
        print(f"   📦 {len(report.outdated)} packages have updates available")
    print()
    print(f"📄 Full report saved to: {report_file}")
    print("=" * 60)

    # Return exit code
    if report.deprecated or report.conflicts:
        return 1  # Issues found
    elif report.outdated:
        return 1  # Updates available
    else:
        return 0  # All healthy


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Critical error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(2)
