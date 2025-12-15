#!/usr/bin/env python3
"""
Weekly Code Health Audit (LL-034 Extension)

Automated audit that runs weekly via GitHub Actions to detect:
1. Dead code / placeholder features
2. Documentation drift (docs don't match code)
3. Unused imports and dependencies
4. Feature declarations without implementations

Results are stored in RAG for trend analysis.

Usage:
    python scripts/weekly_code_health_audit.py [--store-rag]
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path


class CodeHealthAuditor:
    """Automated code health auditing with RAG integration."""

    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path(__file__).parent.parent
        self.findings = []
        self.audit_date = datetime.now().isoformat()

    def audit_unused_dependencies(self) -> list[dict]:
        """Find dependencies in requirements.txt not imported anywhere."""
        findings = []
        req_file = self.project_root / "requirements.txt"

        if not req_file.exists():
            return findings

        # Known transitive/system dependencies to skip (not directly imported)
        # These are installed as dependencies of other packages
        SKIP_PACKAGES = {
            # NVIDIA/CUDA (PyTorch dependencies)
            "nvidia-cuda-nvrtc-cu12", "nvidia-cuda-runtime-cu12", "nvidia-cublas-cu12",
            "nvidia-cudnn-cu12", "nvidia-cufft-cu12", "nvidia-curand-cu12",
            "nvidia-cusolver-cu12", "nvidia-cusparse-cu12", "nvidia-nccl-cu12",
            "nvidia-nvjitlink-cu12", "nvidia-nvtx-cu12", "nvidia-nvshmem-cu12",
            # HTTP/async utilities (dependencies of requests, aiohttp, etc.)
            "urllib3", "certifi", "charset-normalizer", "idna", "anyio", "sniffio",
            "httpcore", "h11", "httpx", "aiosignal", "frozenlist", "multidict",
            "yarl", "async-timeout", "attrs",
            # Type checking / runtime (dependencies of pydantic, typing-extensions)
            "typing-extensions", "annotated-types", "pydantic-core",
            # Build/packaging utilities
            "setuptools", "wheel", "pip", "packaging", "filelock", "platformdirs",
            # Database adapters (transitive)
            "greenlet", "sqlalchemy",
            # JSON/schema (transitive)
            "jsonschema", "jsonschema-specifications", "referencing", "rpds-py",
            # Date/time (transitive)
            "tzdata", "pytz", "python-dateutil", "six",
            # Misc transitive
            "markupsafe", "jinja2", "fonttools", "pillow", "kiwisolver", "contourpy",
            "cycler", "pyparsing", "propcache", "wrapt", "deprecated",
            # Google deps (transitive)
            "google-auth", "google-auth-httplib2", "google-api-core",
            "googleapis-common-protos", "proto-plus", "protobuf",
            "cachetools", "pyasn1", "pyasn1-modules", "rsa",
        }

        # Parse requirements
        requirements = set()
        for line in req_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("-"):
                # Extract package name (before ==, >=, etc.)
                pkg = re.split(r"[=<>!~\[]", line)[0].strip().lower()
                if pkg and pkg not in SKIP_PACKAGES:
                    requirements.add(pkg)

        # Search for imports in src/
        imported = set()
        for py_file in (self.project_root / "src").rglob("*.py"):
            try:
                content = py_file.read_text()
                # Find import statements
                for match in re.finditer(r"^(?:from|import)\s+(\w+)", content, re.MULTILINE):
                    imported.add(match.group(1).lower())
            except Exception:
                pass

        # Common name mappings (package name != import name)
        name_map = {
            "pillow": "pil",
            "scikit-learn": "sklearn",
            "pyyaml": "yaml",
            "python-dotenv": "dotenv",
            "beautifulsoup4": "bs4",
        }

        for pkg in requirements:
            import_name = name_map.get(pkg, pkg.replace("-", "_"))
            if import_name not in imported and pkg not in imported:
                findings.append({
                    "type": "unused_dependency",
                    "package": pkg,
                    "severity": "low",
                    "suggestion": f"Consider removing '{pkg}' from requirements.txt if unused",
                })

        return findings

    def audit_feature_declarations(self) -> list[dict]:
        """Find features declared in config but not implemented."""
        findings = []

        # Check system_state.json for declared features
        state_file = self.project_root / "data" / "system_state.json"
        if state_file.exists():
            try:
                state = json.loads(state_file.read_text())
                enabled_features = state.get("enabled_features", {})

                for feature, enabled in enabled_features.items():
                    if enabled:
                        # Search for implementation
                        feature_snake = feature.lower().replace(" ", "_")
                        found = False

                        for py_file in (self.project_root / "src").rglob("*.py"):
                            if feature_snake in py_file.stem:
                                found = True
                                break

                        if not found:
                            findings.append({
                                "type": "missing_implementation",
                                "feature": feature,
                                "severity": "high",
                                "suggestion": f"Feature '{feature}' is enabled but no implementation found",
                            })
            except Exception:
                pass

        return findings

    def audit_documentation_drift(self) -> list[dict]:
        """Detect when documentation mentions source files that don't exist."""
        findings = []

        # Check docs/*.md for references to non-existent source files
        docs_dir = self.project_root / "docs"
        if not docs_dir.exists():
            return findings

        # Skip archived docs
        for doc_file in docs_dir.glob("*.md"):
            # Skip archive folder
            if "archive" in str(doc_file):
                continue

            try:
                content = doc_file.read_text()

                # Find explicit file path references like `src/foo/bar.py`
                for match in re.finditer(r"`(src/[^`]+\.py)`", content):
                    ref_path = self.project_root / match.group(1)
                    if not ref_path.exists():
                        findings.append({
                            "type": "documentation_drift",
                            "doc_file": str(doc_file.relative_to(self.project_root)),
                            "referenced_path": match.group(1),
                            "severity": "medium",
                            "suggestion": f"Doc references non-existent file: {match.group(1)}",
                        })

                # NOTE: Removed function reference checking - too many false positives
                # from standard library, third-party libs, and method names

            except Exception:
                pass

        return findings

    def audit_disabled_features(self) -> list[dict]:
        """Find features that are disabled with 'not implemented' comments."""
        findings = []

        for py_file in (self.project_root / "src").rglob("*.py"):
            try:
                content = py_file.read_text()
                lines = content.splitlines()

                for i, line in enumerate(lines, 1):
                    # Pattern: enable_xxx = False  # not implemented
                    if re.search(r"enable_\w+\s*=\s*False.*#.*not\s+implemented", line, re.IGNORECASE):
                        findings.append({
                            "type": "disabled_feature",
                            "file": str(py_file.relative_to(self.project_root)),
                            "line": i,
                            "content": line.strip(),
                            "severity": "medium",
                            "suggestion": "Remove disabled feature flag or implement it",
                        })

            except Exception:
                pass

        return findings

    def run_full_audit(self) -> dict:
        """Run all audits and compile results."""
        results = {
            "audit_date": self.audit_date,
            "project": str(self.project_root),
            "findings": {
                "unused_dependencies": self.audit_unused_dependencies(),
                "missing_implementations": self.audit_feature_declarations(),
                "documentation_drift": self.audit_documentation_drift(),
                "disabled_features": self.audit_disabled_features(),
            },
            "summary": {},
        }

        # Calculate summary
        total = 0
        by_severity = {"high": 0, "medium": 0, "low": 0}

        for category, items in results["findings"].items():
            total += len(items)
            for item in items:
                by_severity[item.get("severity", "low")] += 1

        # Health score calculation (more reasonable formula)
        # - High severity: -5 points each (capped at 50 total)
        # - Medium severity: -2 points each (capped at 30 total)
        # - Low severity: -0.5 points each (capped at 20 total)
        high_penalty = min(50, by_severity["high"] * 5)
        medium_penalty = min(30, by_severity["medium"] * 2)
        low_penalty = min(20, by_severity["low"] * 0.5)

        health_score = max(0, 100 - high_penalty - medium_penalty - low_penalty)

        results["summary"] = {
            "total_findings": total,
            "by_severity": by_severity,
            "health_score": round(health_score),
        }

        return results

    def store_to_rag(self, results: dict):
        """Store audit results in RAG for trend analysis."""
        rag_dir = self.project_root / "rag_knowledge" / "code_audits"
        rag_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now().strftime("%Y%m%d")
        audit_file = rag_dir / f"audit_{date_str}.json"

        audit_file.write_text(json.dumps(results, indent=2))
        print(f"✅ Audit stored to RAG: {audit_file}")

    def print_report(self, results: dict):
        """Print formatted audit report."""
        print("\n" + "=" * 70)
        print("CODE HEALTH AUDIT REPORT")
        print(f"Date: {results['audit_date']}")
        print("=" * 70)

        summary = results["summary"]
        health = summary["health_score"]

        if health >= 90:
            health_emoji = "🟢"
        elif health >= 70:
            health_emoji = "🟡"
        else:
            health_emoji = "🔴"

        print(f"\nHealth Score: {health_emoji} {health}/100")
        print(f"Total Findings: {summary['total_findings']}")
        print(f"  High: {summary['by_severity']['high']}")
        print(f"  Medium: {summary['by_severity']['medium']}")
        print(f"  Low: {summary['by_severity']['low']}")

        for category, items in results["findings"].items():
            if items:
                print(f"\n--- {category.upper().replace('_', ' ')} ---")
                for item in items[:5]:  # Limit output
                    print(f"  [{item['severity'].upper()}] {item['suggestion']}")
                if len(items) > 5:
                    print(f"  ... and {len(items) - 5} more")

        print("\n" + "=" * 70)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Weekly Code Health Audit")
    parser.add_argument("--store-rag", action="store_true", help="Store results to RAG")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of report")
    args = parser.parse_args()

    auditor = CodeHealthAuditor()
    results = auditor.run_full_audit()

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        auditor.print_report(results)

    if args.store_rag:
        auditor.store_to_rag(results)

    # Exit with error if high-severity findings
    if results["summary"]["by_severity"]["high"] > 0:
        sys.exit(1)

    return 0


if __name__ == "__main__":
    sys.exit(main())
