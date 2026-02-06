#!/usr/bin/env python3
"""
Thompson Sampling Feedback Model Trainer

Beta-Bernoulli Thompson Sampling for per-category reliability estimation.
Reads from feedback-log.jsonl and builds a Bayesian model of Claude's
performance across different task categories.

Usage:
    python train_from_feedback.py --train              # Full rebuild from JSONL
    python train_from_feedback.py --incremental        # Update with latest entry
    python train_from_feedback.py --reliability        # Print reliability table
    python train_from_feedback.py --sample             # Sample from posteriors
    python train_from_feedback.py --snapshot           # Save model snapshot
    python train_from_feedback.py --config config.json # Use custom categories

LOCAL ONLY - Do not commit to repository
"""

import argparse
import json
import math
import random
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Configuration
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent
# Project-local JSONL written by the capture hook (schema: signal/intensity/source)
FEEDBACK_LOG = PROJECT_ROOT / ".claude" / "memory" / "feedback" / "feedback-log.jsonl"
# Model file: use the same one thompson_steering.py uses for consistency
MODEL_FILE_GLOBAL = Path.home() / ".claude" / "memory" / "thompson_model.json"
MODEL_FILE_LOCAL = (
    PROJECT_ROOT / ".claude" / "memory" / "feedback" / "feedback_model.json"
)
MODEL_FILE = MODEL_FILE_LOCAL  # train_from_feedback writes its own format here
SNAPSHOTS_DIR = PROJECT_ROOT / ".claude" / "memory" / "feedback" / "model_snapshots"

# Default categories (overridden by --config)
DEFAULT_CATEGORIES = {
    "code_edit": {
        "keywords": [
            "edit",
            "write",
            "implement",
            "refactor",
            "fix",
            "update",
            "create file",
        ],
        "tools": ["Edit", "Write", "MultiEdit"],
    },
    "git": {
        "keywords": [
            "commit",
            "push",
            "branch",
            "merge",
            "pr",
            "pull request",
            "rebase",
            "cherry-pick",
        ],
        "tools": ["Bash"],
    },
    "testing": {
        "keywords": [
            "test",
            "jest",
            "coverage",
            "reassure",
            "perf",
            "spec",
            "mock",
            "assert",
        ],
        "tools": [],
    },
    "pr_review": {
        "keywords": [
            "review",
            "pr comment",
            "resolve",
            "minimize",
            "thread",
            "feedback",
        ],
        "tools": [],
    },
    "search": {
        "keywords": [
            "search",
            "find",
            "grep",
            "glob",
            "explore",
            "where is",
            "look for",
        ],
        "tools": ["Grep", "Glob", "Read"],
    },
    "architecture": {
        "keywords": [
            "architecture",
            "design",
            "pattern",
            "structure",
            "fsd",
            "module",
            "navigation",
        ],
        "tools": [],
    },
    "security": {
        "keywords": [
            "security",
            "secret",
            "vulnerability",
            "injection",
            "xss",
            "owasp",
            "trufflehog",
        ],
        "tools": [],
    },
    "debugging": {
        "keywords": [
            "debug",
            "error",
            "crash",
            "stack trace",
            "log",
            "diagnose",
            "investigate",
        ],
        "tools": [],
    },
}

# Time decay configuration (2026 upgrade: exponential decay with half-life)
# Step decay (legacy)
DECAY_WEIGHTS = {
    7: 1.0,  # < 7 days: full weight
    30: 0.5,  # 7-30 days: half weight
    None: 0.25,  # > 30 days: quarter weight
}

# Exponential decay (2026 best practice)
# Half-life of 30 days: feedback loses half its weight every 30 days
# Matches .claude/memory/metadata.json decay_config (decay_constant=0.023)
# Critical lessons have min floor of 0.01 (never fully forgotten)
HALF_LIFE_DAYS = 30.0
USE_EXPONENTIAL_DECAY = True  # Toggle between step and exponential


def load_config(config_path: Optional[str]) -> Dict:
    """Load category configuration from file or use defaults."""
    if config_path:
        path = Path(config_path)
        if path.exists():
            return json.loads(path.read_text())
    return DEFAULT_CATEGORIES


def load_model() -> Dict:
    """Load existing model or create with uniform priors."""
    if MODEL_FILE.exists():
        try:
            return json.loads(MODEL_FILE.read_text())
        except json.JSONDecodeError:
            pass
    return create_initial_model(DEFAULT_CATEGORIES)


def create_initial_model(categories: Dict) -> Dict:
    """Create model with uniform Beta(1,1) priors for all categories."""
    model = {
        "version": 1,
        "created": datetime.now().isoformat(),
        "updated": datetime.now().isoformat(),
        "total_entries": 0,
        "categories": {},
    }
    for cat_name in categories:
        model["categories"][cat_name] = {
            "alpha": 1.0,  # Prior successes + 1
            "beta": 1.0,  # Prior failures + 1
            "samples": 0,
            "last_updated": None,
        }
    return model


def save_model(model: Dict):
    """Save model to disk."""
    MODEL_FILE.parent.mkdir(parents=True, exist_ok=True)
    model["updated"] = datetime.now().isoformat()
    MODEL_FILE.write_text(json.dumps(model, indent=2))


def time_decay_weight(timestamp_str: str) -> float:
    """Compute time decay weight for a feedback entry.

    2026 Upgrade: Supports both step decay and exponential decay.
    Exponential decay uses half-life formula: weight = 2^(-age/half_life)
    """
    try:
        ts_clean = timestamp_str.replace("Z", "").split("+")[0]
        entry_time = datetime.fromisoformat(ts_clean)
    except (ValueError, AttributeError):
        return DECAY_WEIGHTS[None]

    age_days = (datetime.now() - entry_time).days

    if USE_EXPONENTIAL_DECAY:
        # Exponential decay: weight = 2^(-age/half_life)
        # At age=0: weight=1.0, at age=half_life: weight=0.5, etc.
        weight = 2 ** (-age_days / HALF_LIFE_DAYS)
        return max(weight, 0.01)  # Floor at 1% to prevent zero weights
    else:
        # Legacy step decay
        for threshold, weight in sorted(
            DECAY_WEIGHTS.items(), key=lambda x: (x[0] is None, x[0])
        ):
            if threshold is not None and age_days < threshold:
                return weight
        return DECAY_WEIGHTS[None]


def classify_entry(entry: Dict, categories: Dict) -> List[str]:
    """Classify a feedback entry into categories based on keywords/tools."""
    matched = []

    # Build searchable text from entry
    context = (entry.get("context", "") or "").lower()
    message = (entry.get("message", "") or "").lower()
    last_action = (entry.get("last_action", "") or "").lower()
    last_tool = (entry.get("last_tool", "") or "").lower()
    tags = entry.get("tags", [])
    if isinstance(tags, list):
        tags_str = " ".join(t.lower() for t in tags)
    else:
        tags_str = ""

    searchable = f"{context} {message} {last_action} {tags_str}"

    for cat_name, cat_config in categories.items():
        keywords = cat_config.get("keywords", [])
        tools = cat_config.get("tools", [])

        # Check keyword match
        keyword_match = any(kw.lower() in searchable for kw in keywords)

        # Check tool match
        tool_match = any(t.lower() in last_tool for t in tools) if tools else False

        if keyword_match or tool_match:
            matched.append(cat_name)

    return matched if matched else ["uncategorized"]


def load_feedback_entries() -> List[Dict]:
    """Load all feedback entries from JSONL."""
    if not FEEDBACK_LOG.exists():
        return []

    entries = []
    with open(FEEDBACK_LOG) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def is_positive(entry: Dict) -> bool:
    """Determine if a feedback entry is positive.

    Handles multiple JSONL schemas:
    - Local hook: {"signal": "positive"/"negative", "intensity": 0.5}
    - Global hook: {"signal": "positive"/"negative_strong", ...}
    - Legacy: {"feedback": "positive", "reward": 1}
    """
    # Check reward field first (legacy schema)
    if entry.get("reward", 0) > 0:
        return True
    # Check signal field (current hook schema)
    signal = (entry.get("signal", "") or "").lower()
    if signal.startswith("positive"):
        return True
    # Check feedback field (legacy schema)
    feedback = (entry.get("feedback", "") or "").lower()
    if feedback in ("positive", "up", "thumbsup"):
        return True
    # Check type field (global JSONL schema)
    entry_type = (entry.get("type", "") or "").lower()
    if entry_type == "positive":
        return True
    return False


def train_full(categories: Dict) -> Dict:
    """Full rebuild: read all entries, compute posteriors."""
    entries = load_feedback_entries()
    model = create_initial_model(categories)
    model["total_entries"] = len(entries)

    # Ensure uncategorized exists
    if "uncategorized" not in model["categories"]:
        model["categories"]["uncategorized"] = {
            "alpha": 1.0,
            "beta": 1.0,
            "samples": 0,
            "last_updated": None,
        }

    for entry in entries:
        weight = time_decay_weight(entry.get("timestamp", ""))
        cats = classify_entry(entry, categories)
        positive = is_positive(entry)

        for cat in cats:
            if cat not in model["categories"]:
                model["categories"][cat] = {
                    "alpha": 1.0,
                    "beta": 1.0,
                    "samples": 0,
                    "last_updated": None,
                }

            if positive:
                model["categories"][cat]["alpha"] += weight
            else:
                model["categories"][cat]["beta"] += weight

            model["categories"][cat]["samples"] += 1
            model["categories"][cat]["last_updated"] = entry.get("timestamp")

    save_model(model)
    return model


def train_incremental(categories: Dict) -> Dict:
    """Incremental update: process only the latest entry."""
    entries = load_feedback_entries()
    if not entries:
        return load_model()

    model = load_model()

    # Ensure all categories exist
    for cat_name in categories:
        if cat_name not in model["categories"]:
            model["categories"][cat_name] = {
                "alpha": 1.0,
                "beta": 1.0,
                "samples": 0,
                "last_updated": None,
            }
    if "uncategorized" not in model["categories"]:
        model["categories"]["uncategorized"] = {
            "alpha": 1.0,
            "beta": 1.0,
            "samples": 0,
            "last_updated": None,
        }

    latest = entries[-1]
    weight = time_decay_weight(latest.get("timestamp", ""))
    cats = classify_entry(latest, categories)
    positive = is_positive(latest)

    for cat in cats:
        if cat not in model["categories"]:
            model["categories"][cat] = {
                "alpha": 1.0,
                "beta": 1.0,
                "samples": 0,
                "last_updated": None,
            }

        if positive:
            model["categories"][cat]["alpha"] += weight
        else:
            model["categories"][cat]["beta"] += weight

        model["categories"][cat]["samples"] += 1
        model["categories"][cat]["last_updated"] = latest.get("timestamp")

    model["total_entries"] = len(entries)
    save_model(model)
    return model


def compute_reliability(model: Dict) -> List[Tuple[str, float, float, float, int]]:
    """Compute reliability (posterior mean) for each category."""
    results = []
    for cat_name, params in model.get("categories", {}).items():
        alpha = params["alpha"]
        beta_val = params["beta"]
        samples = params["samples"]

        # Posterior mean of Beta distribution: alpha / (alpha + beta)
        reliability = alpha / (alpha + beta_val) if (alpha + beta_val) > 0 else 0.5

        # 95% credible interval width (approximate)
        # For Beta(a,b): variance = ab / ((a+b)^2 * (a+b+1))
        total = alpha + beta_val
        if total > 0 and (total + 1) > 0:
            variance = (alpha * beta_val) / (total * total * (total + 1))
            ci_width = 2 * 1.96 * math.sqrt(variance)
        else:
            ci_width = 1.0

        results.append((cat_name, alpha, beta_val, reliability, samples, ci_width))

    return sorted(results, key=lambda x: -x[3])


def sample_posteriors(model: Dict) -> Dict[str, float]:
    """Thompson Sampling: draw from each category's posterior."""
    samples = {}
    for cat_name, params in model.get("categories", {}).items():
        alpha = max(params["alpha"], 0.01)
        beta_val = max(params["beta"], 0.01)
        samples[cat_name] = random.betavariate(alpha, beta_val)
    return samples


def save_snapshot(model: Dict) -> Path:
    """Save a timestamped snapshot for lift comparison."""
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_file = SNAPSHOTS_DIR / f"model_{timestamp}.json"
    snapshot_file.write_text(json.dumps(model, indent=2))
    return snapshot_file


# ============================================
# META-POLICY RULES (2026 Best Practice)
# Consolidate repeated mistakes into reusable rules
# Based on: Meta-Policy Reflexion (arXiv:2509.03990)
# ============================================

META_POLICY_FILE = (
    PROJECT_ROOT / ".claude" / "memory" / "feedback" / "meta_policy_rules.json"
)


def extract_meta_policy_rules(min_occurrences: int = 3) -> List[Dict[str, Any]]:
    """Extract reusable rules from repeated negative feedback patterns.

    2026 Best Practice: Instead of just tracking individual mistakes,
    consolidate similar mistakes into actionable rules that transfer
    across tasks. This is the Reflexion pattern elevated to meta-level.

    Args:
        min_occurrences: Minimum times a pattern must appear to become a rule

    Returns:
        List of meta-policy rules with condition, action, confidence
    """
    entries = load_feedback_entries()
    negative_entries = [e for e in entries if not is_positive(e)]

    if len(negative_entries) < min_occurrences:
        return []

    # Group by category
    category_patterns: Dict[str, List[Dict]] = {}
    for entry in negative_entries:
        cats = classify_entry(entry, DEFAULT_CATEGORIES)
        for cat in cats:
            if cat not in category_patterns:
                category_patterns[cat] = []
            category_patterns[cat].append(entry)

    rules = []
    for category, patterns in category_patterns.items():
        if len(patterns) >= min_occurrences:
            # Create rule based on category
            rule = {
                "id": f"rule_{category}_{len(patterns)}",
                "category": category,
                "occurrences": len(patterns),
                "confidence": min(0.95, 0.5 + (len(patterns) * 0.1)),
                "created": datetime.now().isoformat(),
                "condition": f"When working on {category} tasks",
                "action": f"Pay extra attention - {len(patterns)} past mistakes in this area",
                "examples": [
                    e.get("context", e.get("message", ""))[:100] for e in patterns[:3]
                ],
            }

            # Category-specific rules
            if category == "git":
                rule["action"] = (
                    "VERIFY git operations before executing - check branch, status, diff"
                )
            elif category == "code_edit":
                rule["action"] = (
                    "READ the file first, understand context before editing"
                )
            elif category == "testing":
                rule["action"] = "Run tests after changes, don't assume they pass"
            elif category == "pr_review":
                rule["action"] = "Address ALL review comments, don't just minimize"
            elif category == "debugging":
                rule["action"] = (
                    "Verify the fix actually works - don't claim success without evidence"
                )

            rules.append(rule)

    return rules


def save_meta_policy_rules(rules: List[Dict[str, Any]]):
    """Save extracted rules to disk."""
    META_POLICY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(META_POLICY_FILE, "w") as f:
        json.dump(
            {
                "updated": datetime.now().isoformat(),
                "rule_count": len(rules),
                "rules": rules,
            },
            f,
            indent=2,
        )


def load_meta_policy_rules() -> List[Dict[str, Any]]:
    """Load existing meta-policy rules."""
    if not META_POLICY_FILE.exists():
        return []
    try:
        with open(META_POLICY_FILE) as f:
            data = json.load(f)
            return data.get("rules", [])
    except (json.JSONDecodeError, KeyError):
        return []


def print_meta_policy_rules():
    """Print meta-policy rules for session context."""
    rules = load_meta_policy_rules()

    print()
    print("=" * 60)
    print("META-POLICY RULES (Consolidated from Feedback)")
    print("=" * 60)

    if not rules:
        print("\n  No rules extracted yet. Need more feedback data.")
        print("  Run --extract-rules after accumulating feedback.")
    else:
        for rule in rules:
            conf_bar = "#" * int(rule["confidence"] * 10)
            print(
                f"\n  [{rule['category'].upper()}] Confidence: [{conf_bar}] {rule['confidence']:.0%}"
            )
            print(f"  Condition: {rule['condition']}")
            print(f"  Action: {rule['action']}")
            print(f"  Based on: {rule['occurrences']} past mistakes")

    print("\n" + "=" * 60)


def print_reliability_table(model: Dict):
    """Print formatted reliability table."""
    results = compute_reliability(model)

    print()
    print("=" * 78)
    print("THOMPSON SAMPLING RELIABILITY TABLE")
    print("=" * 78)
    print()
    print(f"  Model updated: {model.get('updated', 'never')}")
    print(f"  Total entries: {model.get('total_entries', 0)}")
    print()
    print(
        f"  {'Category':<20s} | {'Alpha':>7s} | {'Beta':>7s} | {'Reliability':>12s} | {'Samples':>7s} | {'CI Width':>8s}"
    )
    print("  " + "-" * 74)

    for cat, alpha, beta_val, reliability, samples, ci_width in results:
        # Visual bar
        bar_len = int(reliability * 10)
        bar = "#" * bar_len + "-" * (10 - bar_len)

        print(
            f"  {cat:<20s} | {alpha:>7.1f} | {beta_val:>7.1f} | [{bar}] {reliability:>4.0%} | {samples:>7d} | {ci_width:>7.3f}"
        )

    print()
    print("=" * 78)

    # Summary
    if results:
        best = results[0]
        worst = results[-1]
        print(f"  Best:  {best[0]} ({best[3]:.0%})")
        print(f"  Worst: {worst[0]} ({worst[3]:.0%})")
        print()

        # Categories needing attention (reliability < 50% with 3+ samples)
        weak = [r for r in results if r[3] < 0.5 and r[4] >= 3]
        if weak:
            print("  Categories needing improvement:")
            for cat, _, _, rel, samp, _ in weak:
                print(f"    - {cat}: {rel:.0%} ({samp} samples)")
            print()

    print("=" * 78)


def print_samples(model: Dict):
    """Print Thompson-sampled probabilities."""
    samples = sample_posteriors(model)

    print()
    print("=" * 50)
    print("THOMPSON SAMPLING (Single Draw)")
    print("=" * 50)
    print()

    for cat, prob in sorted(samples.items(), key=lambda x: -x[1]):
        bar = "#" * int(prob * 20) + "-" * (20 - int(prob * 20))
        print(f"  {cat:<20s} [{bar}] {prob:.3f}")

    print()
    print("  (Each run produces different samples - this is expected)")
    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(
        description="Thompson Sampling Feedback Model Trainer (2026)"
    )
    parser.add_argument("--train", action="store_true", help="Full rebuild from JSONL")
    parser.add_argument(
        "--incremental", action="store_true", help="Update with latest entry"
    )
    parser.add_argument(
        "--reliability", action="store_true", help="Print reliability table"
    )
    parser.add_argument("--sample", action="store_true", help="Sample from posteriors")
    parser.add_argument("--snapshot", action="store_true", help="Save model snapshot")
    parser.add_argument(
        "--extract-rules", action="store_true", help="Extract meta-policy rules (2026)"
    )
    parser.add_argument(
        "--show-rules", action="store_true", help="Show meta-policy rules"
    )
    parser.add_argument("--config", type=str, help="Path to custom categories JSON")
    parser.add_argument(
        "--json", action="store_true", help="Output as JSON (for hook consumption)"
    )

    args = parser.parse_args()

    categories = load_config(args.config)

    if args.train:
        model = train_full(categories)
        if args.json:
            print(json.dumps({"status": "trained", "entries": model["total_entries"]}))
        else:
            print(f"Trained model from {model['total_entries']} entries.")
            print(f"Saved to: {MODEL_FILE}")
        print_reliability_table(model)

    elif args.incremental:
        model = train_incremental(categories)
        if args.json:
            print(json.dumps({"status": "updated", "entries": model["total_entries"]}))
        else:
            print(
                f"Incremental update complete. Total entries: {model['total_entries']}"
            )

    elif args.reliability:
        model = load_model()
        if args.json:
            results = compute_reliability(model)
            output = {
                "updated": model.get("updated"),
                "total_entries": model.get("total_entries", 0),
                "categories": {
                    cat: {
                        "alpha": a,
                        "beta": b,
                        "reliability": r,
                        "samples": s,
                        "ci_width": ci,
                    }
                    for cat, a, b, r, s, ci in results
                },
            }
            print(json.dumps(output, indent=2))
        else:
            print_reliability_table(model)

    elif args.sample:
        model = load_model()
        if args.json:
            samples = sample_posteriors(model)
            print(json.dumps(samples, indent=2))
        else:
            print_samples(model)

    elif args.snapshot:
        model = load_model()
        snapshot_file = save_snapshot(model)
        if args.json:
            print(json.dumps({"snapshot": str(snapshot_file)}))
        else:
            print(f"Snapshot saved: {snapshot_file}")

    elif args.extract_rules:
        rules = extract_meta_policy_rules()
        save_meta_policy_rules(rules)
        if args.json:
            print(
                json.dumps(
                    {"status": "extracted", "rule_count": len(rules), "rules": rules}
                )
            )
        else:
            print(f"Extracted {len(rules)} meta-policy rules.")
            print(f"Saved to: {META_POLICY_FILE}")
            print_meta_policy_rules()

    elif args.show_rules:
        if args.json:
            rules = load_meta_policy_rules()
            print(json.dumps({"rules": rules}, indent=2))
        else:
            print_meta_policy_rules()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
