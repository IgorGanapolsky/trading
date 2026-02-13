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
    python train_from_feedback.py --dpo-train          # DPO batch optimization (Feb 2026)
    python train_from_feedback.py --config config.json # Use custom categories

LOCAL ONLY - Do not commit to repository
"""

import sys
import json
import math
import random
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

# Configuration
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent
FEEDBACK_LOG = PROJECT_ROOT / ".claude" / "memory" / "feedback" / "feedback-log.jsonl"
MODEL_FILE = PROJECT_ROOT / ".claude" / "memory" / "feedback" / "feedback_model.json"
SNAPSHOTS_DIR = PROJECT_ROOT / ".claude" / "memory" / "feedback" / "model_snapshots"

# Default categories (overridden by --config)
DEFAULT_CATEGORIES = {
    "code_edit": {
        "keywords": ["edit", "write", "implement", "refactor", "fix", "update", "create file"],
        "tools": ["Edit", "Write", "MultiEdit"],
    },
    "git": {
        "keywords": ["commit", "push", "branch", "merge", "pr", "pull request", "rebase", "cherry-pick"],
        "tools": ["Bash"],
    },
    "testing": {
        "keywords": ["test", "jest", "coverage", "reassure", "perf", "spec", "mock", "assert"],
        "tools": [],
    },
    "pr_review": {
        "keywords": ["review", "pr comment", "resolve", "minimize", "thread", "feedback"],
        "tools": [],
    },
    "search": {
        "keywords": ["search", "find", "grep", "glob", "explore", "where is", "look for"],
        "tools": ["Grep", "Glob", "Read"],
    },
    "architecture": {
        "keywords": ["architecture", "design", "pattern", "structure", "fsd", "module", "navigation"],
        "tools": [],
    },
    "security": {
        "keywords": ["security", "secret", "vulnerability", "injection", "xss", "owasp", "trufflehog"],
        "tools": [],
    },
    "debugging": {
        "keywords": ["debug", "error", "crash", "stack trace", "log", "diagnose", "investigate"],
        "tools": [],
    },
}

# Time decay configuration (2026 upgrade: exponential decay with half-life)
# Step decay (legacy)
DECAY_WEIGHTS = {
    7: 1.0,    # < 7 days: full weight
    30: 0.5,   # 7-30 days: half weight
    None: 0.25  # > 30 days: quarter weight
}

# Exponential decay (2026 best practice)
# Half-life of 30 days: feedback loses half its weight every 30 days
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
            "alpha": 1.0,   # Prior successes + 1
            "beta": 1.0,    # Prior failures + 1
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
        for threshold, weight in sorted(DECAY_WEIGHTS.items(), key=lambda x: (x[0] is None, x[0])):
            if threshold is not None and age_days < threshold:
                return weight
        return DECAY_WEIGHTS[None]


def classify_entry(entry: Dict, categories: Dict) -> List[str]:
    """Classify a feedback entry into categories based on keywords/tools."""
    matched = []

    # Build searchable text from entry
    context = (entry.get("context", "") or "").lower()
    message = (entry.get("message", "") or "").lower()
    user_message = (entry.get("user_message", "") or "").lower()
    assistant_response = (
        entry.get("assistant_response") or entry.get("claude_response") or ""
    )
    assistant_response = (assistant_response or "").lower()
    last_action = (entry.get("last_action", "") or "").lower()
    last_tool = (entry.get("last_tool", "") or "").lower()
    tags = entry.get("tags", [])
    if isinstance(tags, list):
        tags_str = " ".join(t.lower() for t in tags)
    else:
        tags_str = ""

    searchable = f"{context} {message} {user_message} {assistant_response} {last_action} {tags_str}"

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
    """Determine if a feedback entry is positive."""
    if entry.get("reward", 0) > 0:
        return True
    feedback = entry.get("feedback", "").lower()
    return feedback in ("positive", "up", "thumbsup")


def train_full(categories: Dict) -> Dict:
    """Full rebuild: read all entries, compute posteriors."""
    entries = load_feedback_entries()
    model = create_initial_model(categories)
    model["total_entries"] = len(entries)

    # Ensure uncategorized exists
    if "uncategorized" not in model["categories"]:
        model["categories"]["uncategorized"] = {
            "alpha": 1.0, "beta": 1.0, "samples": 0, "last_updated": None
        }

    for entry in entries:
        weight = time_decay_weight(entry.get("timestamp", ""))
        cats = classify_entry(entry, categories)
        positive = is_positive(entry)

        for cat in cats:
            if cat not in model["categories"]:
                model["categories"][cat] = {
                    "alpha": 1.0, "beta": 1.0, "samples": 0, "last_updated": None
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
                "alpha": 1.0, "beta": 1.0, "samples": 0, "last_updated": None
            }
    if "uncategorized" not in model["categories"]:
        model["categories"]["uncategorized"] = {
            "alpha": 1.0, "beta": 1.0, "samples": 0, "last_updated": None
        }

    latest = entries[-1]
    weight = time_decay_weight(latest.get("timestamp", ""))
    cats = classify_entry(latest, categories)
    positive = is_positive(latest)

    for cat in cats:
        if cat not in model["categories"]:
            model["categories"][cat] = {
                "alpha": 1.0, "beta": 1.0, "samples": 0, "last_updated": None
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

META_POLICY_FILE = PROJECT_ROOT / ".claude" / "memory" / "feedback" / "meta_policy_rules.json"


def extract_meta_policy_rules(min_occurrences: int = 3) -> List[Dict[str, Any]]:
    """Extract reusable rules from repeated negative feedback patterns.

    Feb 2026 Upgrade: Recency + intensity weighted confidence.
    - Recent mistakes weigh more than old ones (exponential decay)
    - High-intensity feedback (user frustration) boosts confidence faster
    - Rules include trend analysis (improving vs deteriorating)

    Args:
        min_occurrences: Minimum times a pattern must appear to become a rule

    Returns:
        List of meta-policy rules with condition, action, weighted confidence
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

    # Also count positive entries per category for trend analysis
    positive_entries = [e for e in entries if is_positive(e)]
    category_positives: Dict[str, int] = {}
    for entry in positive_entries:
        cats = classify_entry(entry, DEFAULT_CATEGORIES)
        for cat in cats:
            category_positives[cat] = category_positives.get(cat, 0) + 1

    rules = []
    for category, patterns in category_patterns.items():
        if len(patterns) >= min_occurrences:
            # Feb 2026: Recency + intensity weighted confidence
            weighted_sum = 0.0
            total_weight = 0.0
            recent_count = 0  # Last 7 days
            recent_positive = 0

            for e in patterns:
                recency = time_decay_weight(e.get("timestamp", ""))
                intensity = e.get("intensity", 3) / 5.0  # Normalize to 0-1
                weight = recency * (0.5 + 0.5 * intensity)  # Blend recency + intensity
                weighted_sum += weight
                total_weight += 1.0

                # Track recent entries
                try:
                    ts = e.get("timestamp", "").replace("Z", "").split("+")[0]
                    entry_time = datetime.fromisoformat(ts)
                    if (datetime.now() - entry_time).days <= 7:
                        recent_count += 1
                except (ValueError, AttributeError):
                    pass

            # Count recent positives for trend
            for e in positive_entries:
                cats = classify_entry(e, DEFAULT_CATEGORIES)
                if category in cats:
                    try:
                        ts = e.get("timestamp", "").replace("Z", "").split("+")[0]
                        entry_time = datetime.fromisoformat(ts)
                        if (datetime.now() - entry_time).days <= 7:
                            recent_positive += 1
                    except (ValueError, AttributeError):
                        pass

            # Weighted confidence: base + recency-weighted adjustment
            avg_weighted = weighted_sum / total_weight if total_weight > 0 else 0
            confidence = min(0.95, 0.4 + (avg_weighted * 0.3) + (len(patterns) * 0.05))

            # Trend: improving or deteriorating
            total_positives = category_positives.get(category, 0)
            pos_ratio = total_positives / (total_positives + len(patterns)) if (total_positives + len(patterns)) > 0 else 0
            if recent_count == 0 and recent_positive > 0:
                trend = "improving"
            elif recent_count > 2 and recent_positive == 0:
                trend = "deteriorating"
            elif recent_count > recent_positive:
                trend = "needs_attention"
            else:
                trend = "stable"

            rule = {
                "id": f"rule_{category}_{len(patterns)}",
                "category": category,
                "occurrences": len(patterns),
                "confidence": round(confidence, 3),
                "weighted_confidence": round(avg_weighted, 4),
                "trend": trend,
                "recent_negatives_7d": recent_count,
                "recent_positives_7d": recent_positive,
                "positive_ratio": round(pos_ratio, 3),
                "created": datetime.now().isoformat(),
                "condition": f"When working on {category} tasks",
                "action": f"Pay extra attention - {len(patterns)} past mistakes in this area",
                "examples": [
                    e.get("context", e.get("message", ""))[:100]
                    for e in sorted(patterns, key=lambda x: x.get("timestamp", ""), reverse=True)[:3]
                ],
            }

            # Category-specific rules
            if category == "git":
                rule["action"] = "VERIFY git operations before executing - check branch, status, diff"
            elif category == "code_edit":
                rule["action"] = "READ the file first, understand context before editing"
            elif category == "testing":
                rule["action"] = "Run tests after changes, don't assume they pass"
            elif category == "pr_review":
                rule["action"] = "Address ALL review comments, don't just minimize"
            elif category == "debugging":
                rule["action"] = "Verify the fix actually works - don't claim success without evidence"

            rules.append(rule)

    # Sort by confidence descending (most urgent first)
    rules.sort(key=lambda r: r["confidence"], reverse=True)
    return rules


def save_meta_policy_rules(rules: List[Dict[str, Any]]):
    """Save extracted rules to disk."""
    META_POLICY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(META_POLICY_FILE, "w") as f:
        json.dump({
            "updated": datetime.now().isoformat(),
            "rule_count": len(rules),
            "rules": rules,
        }, f, indent=2)


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


# ============================================
# DPO-STYLE BATCH OPTIMIZATION (Feb 2026)
# Direct Preference Optimization without explicit reward model.
# Builds preference pairs from positive/negative feedback,
# then adjusts category priors more aggressively than
# simple counting — mimicking DPO's closed-form update.
#
# Reference: Rafailov et al. 2023 (arXiv:2305.18290)
# ============================================

DPO_MODEL_FILE = PROJECT_ROOT / ".claude" / "memory" / "feedback" / "dpo_model.json"
DPO_BETA = 0.1  # Temperature parameter (lower = more aggressive preference following)


def _override_dpo_beta(value: float):
    """Override DPO_BETA at module level."""
    global DPO_BETA
    DPO_BETA = value


def build_preference_pairs(categories: Dict) -> Dict[str, List[Tuple[Dict, Dict]]]:
    """Build (chosen, rejected) preference pairs per category.

    For each category, pair the most recent positive entry with the most
    recent negative entry. This creates implicit preference data without
    needing explicit A/B comparisons.
    """
    entries = load_feedback_entries()
    if not entries:
        return {}

    # Classify entries by category and sentiment
    cat_positives: Dict[str, List[Dict]] = {}
    cat_negatives: Dict[str, List[Dict]] = {}

    for entry in entries:
        cats = classify_entry(entry, categories)
        for cat in cats:
            if is_positive(entry):
                cat_positives.setdefault(cat, []).append(entry)
            else:
                cat_negatives.setdefault(cat, []).append(entry)

    # Build pairs: each positive paired with closest-in-time negative
    pairs: Dict[str, List[Tuple[Dict, Dict]]] = {}
    all_cats = set(list(cat_positives.keys()) + list(cat_negatives.keys()))

    for cat in all_cats:
        pos = cat_positives.get(cat, [])
        neg = cat_negatives.get(cat, [])
        if not pos or not neg:
            continue

        cat_pairs = []
        # Sort by timestamp
        pos_sorted = sorted(pos, key=lambda e: e.get("timestamp", ""))
        neg_sorted = sorted(neg, key=lambda e: e.get("timestamp", ""))

        # Pair each positive with the nearest negative (greedy matching)
        used_neg = set()
        for p in pos_sorted:
            best_neg = None
            best_dist = float("inf")
            for i, n in enumerate(neg_sorted):
                if i in used_neg:
                    continue
                try:
                    p_ts = datetime.fromisoformat(p.get("timestamp", "").replace("Z", "").split("+")[0])
                    n_ts = datetime.fromisoformat(n.get("timestamp", "").replace("Z", "").split("+")[0])
                    dist = abs((p_ts - n_ts).total_seconds())
                except (ValueError, AttributeError):
                    dist = float("inf")
                if dist < best_dist:
                    best_dist = dist
                    best_neg = i
            if best_neg is not None:
                used_neg.add(best_neg)
                cat_pairs.append((p, neg_sorted[best_neg]))

        if cat_pairs:
            pairs[cat] = cat_pairs

    return pairs


def dpo_log_ratio(chosen_weight: float, rejected_weight: float, beta: float = DPO_BETA) -> float:
    """Compute DPO implicit reward difference.

    DPO loss: -log(sigmoid(beta * (log pi(chosen) - log pi(rejected))))
    We use time-decay weights as proxy for log-probabilities.

    Returns adjustment to apply to category alpha/beta parameters.
    """
    # Avoid log(0)
    chosen_weight = max(chosen_weight, 0.01)
    rejected_weight = max(rejected_weight, 0.01)

    log_ratio = math.log(chosen_weight) - math.log(rejected_weight)
    sigmoid = 1.0 / (1.0 + math.exp(-beta * log_ratio))

    # Scale adjustment: larger preference gap → larger update
    adjustment = (sigmoid - 0.5) * 2  # Range: -1 to 1
    return adjustment


def train_dpo(categories: Dict) -> Dict:
    """DPO-style batch optimization (Feb 2026 upgrade).

    Instead of simple counting, uses preference pairs to compute
    direct policy updates. Works alongside Thompson Sampling:
    - Thompson Sampling: online exploration (per-feedback updates)
    - DPO: batch exploitation (accumulated preference pairs)

    The DPO adjustment is applied on top of the Thompson model.
    """
    pairs = build_preference_pairs(categories)
    if not pairs:
        print("No preference pairs found. Need both positive and negative feedback per category.")
        return load_model()

    model = load_model()

    dpo_adjustments = {}

    for cat, cat_pairs in pairs.items():
        if cat not in model["categories"]:
            continue

        total_adjustment = 0.0
        for chosen, rejected in cat_pairs:
            chosen_weight = time_decay_weight(chosen.get("timestamp", ""))
            rejected_weight = time_decay_weight(rejected.get("timestamp", ""))

            # Compute DPO-style adjustment
            adj = dpo_log_ratio(chosen_weight, rejected_weight)
            total_adjustment += adj

        # Average adjustment over all pairs
        avg_adjustment = total_adjustment / len(cat_pairs) if cat_pairs else 0

        # Apply DPO adjustment to model parameters
        # Positive adjustment → boost alpha (more reliable)
        # Negative adjustment → boost beta (less reliable)
        if avg_adjustment > 0:
            boost = avg_adjustment * len(cat_pairs) * 0.5  # Scale by pair count
            model["categories"][cat]["alpha"] += boost
        else:
            penalty = abs(avg_adjustment) * len(cat_pairs) * 0.5
            model["categories"][cat]["beta"] += penalty

        dpo_adjustments[cat] = {
            "pairs": len(cat_pairs),
            "avg_adjustment": round(avg_adjustment, 4),
            "direction": "boost" if avg_adjustment > 0 else "penalize",
        }

    # Save DPO metadata
    dpo_meta = {
        "updated": datetime.now().isoformat(),
        "beta": DPO_BETA,
        "total_pairs": sum(len(p) for p in pairs.values()),
        "categories": dpo_adjustments,
    }
    DPO_MODEL_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DPO_MODEL_FILE, "w") as f:
        json.dump(dpo_meta, f, indent=2)

    save_model(model)
    return model


def print_dpo_results(model: Dict):
    """Print DPO training results."""
    if not DPO_MODEL_FILE.exists():
        print("\nNo DPO model found. Run --dpo-train first.")
        return

    with open(DPO_MODEL_FILE) as f:
        dpo_meta = json.load(f)

    print()
    print("=" * 60)
    print("DPO BATCH OPTIMIZATION RESULTS (Feb 2026)")
    print("=" * 60)
    print(f"  Beta (temperature): {dpo_meta.get('beta', DPO_BETA)}")
    print(f"  Total preference pairs: {dpo_meta.get('total_pairs', 0)}")
    print(f"  Updated: {dpo_meta.get('updated', 'never')}")
    print()

    for cat, adj in sorted(
        dpo_meta.get("categories", {}).items(),
        key=lambda x: abs(x[1].get("avg_adjustment", 0)),
        reverse=True,
    ):
        direction = adj.get("direction", "none")
        arrow = "+" if direction == "boost" else "-"
        bar_val = abs(adj.get("avg_adjustment", 0)) * 10
        bar = "#" * min(10, int(bar_val)) + "-" * max(0, 10 - int(bar_val))
        print(f"  {cat:<20s} [{bar}] {arrow}{abs(adj.get('avg_adjustment', 0)):.4f} ({adj.get('pairs', 0)} pairs)")

    print()
    print("  DPO adjusts Thompson Sampling priors based on preference pairs.")
    print("  Run --reliability to see combined effect.")
    print("=" * 60)


def print_meta_policy_rules():
    """Print meta-policy rules for session context."""
    rules = load_meta_policy_rules()

    print()
    print("=" * 60)
    print("META-POLICY RULES (Recency + Intensity Weighted)")
    print("=" * 60)

    if not rules:
        print("\n  No rules extracted yet. Need more feedback data.")
        print("  Run --extract-rules after accumulating feedback.")
    else:
        for rule in rules:
            conf_bar = "#" * int(rule["confidence"] * 10)
            trend = rule.get("trend", "unknown")
            trend_icon = {"improving": "+", "deteriorating": "!", "needs_attention": "?", "stable": "="}
            trend_char = trend_icon.get(trend, "?")
            print(f"\n  [{rule['category'].upper()}] Confidence: [{conf_bar}] {rule['confidence']:.0%} (trend: {trend_char} {trend})")
            print(f"  Condition: {rule['condition']}")
            print(f"  Action: {rule['action']}")
            print(f"  Based on: {rule['occurrences']} negatives | Positive ratio: {rule.get('positive_ratio', 0):.0%}")
            recent_neg = rule.get("recent_negatives_7d", 0)
            recent_pos = rule.get("recent_positives_7d", 0)
            if recent_neg or recent_pos:
                print(f"  Last 7d: {recent_neg} neg / {recent_pos} pos")

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
    print(f"  {'Category':<20s} | {'Alpha':>7s} | {'Beta':>7s} | {'Reliability':>12s} | {'Samples':>7s} | {'CI Width':>8s}")
    print("  " + "-" * 74)

    for cat, alpha, beta_val, reliability, samples, ci_width in results:
        # Visual bar
        bar_len = int(reliability * 10)
        bar = "#" * bar_len + "-" * (10 - bar_len)

        print(f"  {cat:<20s} | {alpha:>7.1f} | {beta_val:>7.1f} | [{bar}] {reliability:>4.0%} | {samples:>7d} | {ci_width:>7.3f}")

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
    parser = argparse.ArgumentParser(description="Thompson Sampling Feedback Model Trainer (2026)")
    parser.add_argument("--train", action="store_true", help="Full rebuild from JSONL")
    parser.add_argument("--incremental", action="store_true", help="Update with latest entry")
    parser.add_argument("--reliability", action="store_true", help="Print reliability table")
    parser.add_argument("--sample", action="store_true", help="Sample from posteriors")
    parser.add_argument("--snapshot", action="store_true", help="Save model snapshot")
    parser.add_argument("--extract-rules", action="store_true", help="Extract meta-policy rules (2026)")
    parser.add_argument("--show-rules", action="store_true", help="Show meta-policy rules")
    parser.add_argument("--dpo-train", action="store_true", help="DPO batch optimization (Feb 2026)")
    parser.add_argument("--dpo-beta", type=float, default=DPO_BETA, help="DPO temperature parameter")
    parser.add_argument("--config", type=str, help="Path to custom categories JSON")
    parser.add_argument("--json", action="store_true", help="Output as JSON (for hook consumption)")

    args = parser.parse_args()

    categories = load_config(args.config)

    if args.train:
        model = train_full(categories)
        # Auto-run DPO batch optimization on full train (Feb 2026: autonomous)
        dpo_model = train_dpo(categories)
        # Auto-extract meta-policy rules with recency+intensity weighting
        rules = extract_meta_policy_rules()
        save_meta_policy_rules(rules)
        if args.json:
            print(json.dumps({"status": "trained", "entries": model["total_entries"], "dpo": True, "rules": len(rules)}))
        else:
            print(f"Trained model from {model['total_entries']} entries.")
            print(f"DPO batch optimization applied. Meta-policy rules: {len(rules)}.")
            print(f"Saved to: {MODEL_FILE}")
        print_reliability_table(dpo_model)

    elif args.incremental:
        model = train_incremental(categories)
        if args.json:
            print(json.dumps({"status": "updated", "entries": model["total_entries"]}))
        else:
            print(f"Incremental update complete. Total entries: {model['total_entries']}")

    elif args.reliability:
        model = load_model()
        if args.json:
            results = compute_reliability(model)
            output = {
                "updated": model.get("updated"),
                "total_entries": model.get("total_entries", 0),
                "categories": {
                    cat: {"alpha": a, "beta": b, "reliability": r, "samples": s, "ci_width": ci}
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
            print(json.dumps({"status": "extracted", "rule_count": len(rules), "rules": rules}))
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

    elif args.dpo_train:
        # Override DPO_BETA via module-level reassignment
        _override_dpo_beta(args.dpo_beta)
        model = train_dpo(categories)
        if args.json:
            dpo_meta = {}
            if DPO_MODEL_FILE.exists():
                with open(DPO_MODEL_FILE) as f:
                    dpo_meta = json.load(f)
            print(json.dumps({"status": "dpo_trained", **dpo_meta}))
        else:
            print(f"DPO batch optimization complete.")
            print(f"Saved to: {DPO_MODEL_FILE}")
            print_dpo_results(model)
            print_reliability_table(model)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
