#!/usr/bin/env python3
"""
Milestone Alert System

Tracks progress toward Day 30/60/90 milestones and sends alerts.
Integrates with the go-live readiness system.

Usage:
    python3 scripts/milestone_alerts.py              # Check milestones
    python3 scripts/milestone_alerts.py --upcoming   # Show upcoming milestones
    python3 scripts/milestone_alerts.py --summary    # Brief summary

Created: Dec 15, 2025
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def load_system_state() -> dict:
    """Load current system state."""
    state_file = PROJECT_ROOT / "data" / "system_state.json"
    if state_file.exists():
        with open(state_file) as f:
            return json.load(f)
    return {}


def load_deployment_config() -> dict:
    """Load capital deployment configuration."""
    config_file = PROJECT_ROOT / "config" / "capital_deployment.json"
    if config_file.exists():
        with open(config_file) as f:
            return json.load(f)
    return {}


def calculate_options_stats(state: dict) -> dict:
    """Calculate options-specific statistics."""
    closed_trades = state.get("performance", {}).get("closed_trades", [])
    options_trades = [
        t for t in closed_trades
        if "P0" in t.get("symbol", "") or "C0" in t.get("symbol", "")
    ]

    if not options_trades:
        return {"total": 0, "wins": 0, "win_rate": 0, "pl": 0}

    wins = len([t for t in options_trades if t.get("pl", 0) > 0])
    return {
        "total": len(options_trades),
        "wins": wins,
        "win_rate": (wins / len(options_trades) * 100) if options_trades else 0,
        "pl": sum(t.get("pl", 0) for t in options_trades),
    }


def check_milestone_criteria(milestone_day: int, state: dict) -> dict:
    """Check if criteria for a specific milestone are met."""
    total_trades = state.get("performance", {}).get("total_trades", 0)
    total_pl = state.get("account", {}).get("total_pl", 0)
    options = calculate_options_stats(state)

    if milestone_day == 30:
        criteria = [
            {"name": "Total Trades ≥30", "met": total_trades >= 30, "current": total_trades, "required": 30},
            {"name": "Options Win Rate ≥55%", "met": options["win_rate"] >= 55, "current": f"{options['win_rate']:.1f}%", "required": "55%"},
            {"name": "Positive P/L", "met": total_pl > 0, "current": f"${total_pl:.2f}", "required": ">$0"},
        ]
        unlocks = "Phase 1: Micro-Test ($5k real money)"
    elif milestone_day == 60:
        criteria = [
            {"name": "Total Trades ≥60", "met": total_trades >= 60, "current": total_trades, "required": 60},
            {"name": "Options Win Rate ≥60%", "met": options["win_rate"] >= 60, "current": f"{options['win_rate']:.1f}%", "required": "60%"},
            {"name": "Total Profit ≥$200", "met": total_pl >= 200, "current": f"${total_pl:.2f}", "required": "$200"},
        ]
        unlocks = "Phase 2: Small Scale ($15k real money)"
    elif milestone_day == 90:
        criteria = [
            {"name": "Total Trades ≥100", "met": total_trades >= 100, "current": total_trades, "required": 100},
            {"name": "Options Win Rate ≥60%", "met": options["win_rate"] >= 60, "current": f"{options['win_rate']:.1f}%", "required": "60%"},
            {"name": "Options Trades ≥50", "met": options["total"] >= 50, "current": options["total"], "required": 50},
            {"name": "Total Profit ≥$500", "met": total_pl >= 500, "current": f"${total_pl:.2f}", "required": "$500"},
        ]
        unlocks = "Phase 3: Full Deployment (50% real money)"
    else:
        return {"criteria": [], "unlocks": "", "all_met": False}

    all_met = all(c["met"] for c in criteria)
    return {"criteria": criteria, "unlocks": unlocks, "all_met": all_met}


def get_milestone_status(state: dict) -> list[dict]:
    """Get comprehensive milestone status."""
    current_day = state.get("challenge", {}).get("current_day", 0)
    start_date_str = state.get("challenge", {}).get("start_date", "2025-10-29")

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    except ValueError:
        start_date = datetime.now() - timedelta(days=current_day)

    today = datetime.now()

    milestones = []
    for day in [30, 60, 90]:
        target_date = start_date + timedelta(days=day)
        days_until = (target_date - today).days

        if current_day >= day:
            status = "REACHED"
            urgency = "✅"
        elif days_until <= 0:
            status = "OVERDUE"
            urgency = "🔴"
        elif days_until <= 7:
            status = "IMMINENT"
            urgency = "🟠"
        elif days_until <= 14:
            status = "APPROACHING"
            urgency = "🟡"
        else:
            status = "UPCOMING"
            urgency = "⏳"

        criteria_check = check_milestone_criteria(day, state)

        milestones.append({
            "day": day,
            "name": f"Day {day} Review",
            "target_date": target_date.strftime("%Y-%m-%d"),
            "days_until": max(0, days_until),
            "status": status,
            "urgency": urgency,
            "criteria": criteria_check["criteria"],
            "unlocks": criteria_check["unlocks"],
            "ready": criteria_check["all_met"],
            "progress_pct": sum(1 for c in criteria_check["criteria"] if c["met"]) / len(criteria_check["criteria"]) * 100 if criteria_check["criteria"] else 0,
        })

    return milestones


def get_alerts(milestones: list[dict]) -> list[dict]:
    """Generate alerts based on milestone status."""
    alerts = []

    for m in milestones:
        if m["status"] == "OVERDUE" and not m["ready"]:
            alerts.append({
                "level": "CRITICAL",
                "icon": "🚨",
                "message": f"{m['name']} is OVERDUE! {len([c for c in m['criteria'] if not c['met']])} criteria not met.",
                "action": f"Focus on meeting criteria to unlock: {m['unlocks']}"
            })
        elif m["status"] == "IMMINENT" and not m["ready"]:
            alerts.append({
                "level": "WARNING",
                "icon": "⚠️",
                "message": f"{m['name']} in {m['days_until']} days! Not all criteria met yet.",
                "action": f"Work on: {', '.join(c['name'] for c in m['criteria'] if not c['met'])}"
            })
        elif m["status"] == "REACHED" and m["ready"]:
            alerts.append({
                "level": "SUCCESS",
                "icon": "🎉",
                "message": f"{m['name']} COMPLETE! All criteria met.",
                "action": f"You can unlock: {m['unlocks']}"
            })
        elif m["status"] == "REACHED" and not m["ready"]:
            alerts.append({
                "level": "INFO",
                "icon": "📋",
                "message": f"Day {m['day']} reached but criteria not met.",
                "action": f"Continue working toward: {', '.join(c['name'] for c in m['criteria'] if not c['met'])}"
            })

    return alerts


def get_next_actions(milestones: list[dict], state: dict) -> list[str]:
    """Get recommended next actions based on milestone status."""
    current_day = state.get("challenge", {}).get("current_day", 0)
    actions = []

    # Find the next incomplete milestone
    for m in milestones:
        if not m["ready"]:
            failing = [c for c in m["criteria"] if not c["met"]]
            for c in failing[:3]:  # Top 3 priorities
                actions.append(f"Work on: {c['name']} (currently: {c['current']}, need: {c['required']})")
            break

    # Add time-based recommendations
    if current_day < 30:
        actions.append(f"Execute {max(1, (30 - state.get('performance', {}).get('total_trades', 0)) // (30 - current_day))} trades per day to reach 30 by Day 30")

    return actions[:5]  # Max 5 actions


def print_report(state: dict, summary: bool = False, upcoming: bool = False):
    """Print milestone status report."""
    milestones = get_milestone_status(state)
    alerts = get_alerts(milestones)
    actions = get_next_actions(milestones, state)
    current_day = state.get("challenge", {}).get("current_day", 0)

    if summary:
        next_milestone = next((m for m in milestones if m["status"] not in ["REACHED"]), milestones[-1])
        print(f"📅 Day {current_day}/90 | Next: {next_milestone['name']} in {next_milestone['days_until']}d | Ready: {'✅' if next_milestone['ready'] else '❌'} ({next_milestone['progress_pct']:.0f}%)")
        return

    print("=" * 70)
    print("📅 MILESTONE TRACKER")
    print(f"   Current Day: {current_day}/90 | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)

    # Alerts first
    if alerts:
        print("\n🔔 ALERTS")
        print("-" * 50)
        for alert in alerts:
            print(f"\n   {alert['icon']} [{alert['level']}] {alert['message']}")
            print(f"      → {alert['action']}")

    # Milestone details
    print("\n" + "-" * 70)
    print("🏁 MILESTONES")
    print("-" * 70)

    for m in milestones:
        if upcoming and m["status"] == "REACHED":
            continue

        print(f"\n{m['urgency']} {m['name']} ({m['target_date']})")
        print(f"   Status: {m['status']} | Days Until: {m['days_until']} | Ready: {'✅' if m['ready'] else '❌'}")
        print(f"   Progress: [{'█' * int(m['progress_pct'] / 10)}{'░' * (10 - int(m['progress_pct'] / 10))}] {m['progress_pct']:.0f}%")
        print(f"   Unlocks: {m['unlocks']}")

        print("\n   Criteria:")
        for c in m["criteria"]:
            status = "✅" if c["met"] else "❌"
            print(f"      {status} {c['name']}: {c['current']} (need: {c['required']})")

    # Actions
    if actions:
        print("\n" + "-" * 70)
        print("📝 RECOMMENDED ACTIONS")
        print("-" * 70)
        for i, action in enumerate(actions, 1):
            print(f"   {i}. {action}")

    # Timeline
    print("\n" + "-" * 70)
    print("📆 TIMELINE")
    print("-" * 70)

    start_date_str = state.get("challenge", {}).get("start_date", "2025-10-29")
    try:
        _start_date = datetime.strptime(start_date_str, "%Y-%m-%d")  # validates format
    except ValueError:
        _start_date = datetime.now() - timedelta(days=current_day)  # fallback

    timeline_width = 60
    for m in milestones:
        day_pos = int(m["day"] / 90 * timeline_width)
        current_pos = int(current_day / 90 * timeline_width)

        line = ["-"] * timeline_width
        if current_pos < timeline_width:
            line[current_pos] = "●"  # Current position
        line[min(day_pos, timeline_width - 1)] = "◆" if m["ready"] else "○"

        print(f"   Day {m['day']:2d}: {''.join(line[:day_pos + 1])} {m['urgency']}")

    print(f"\n   Legend: ● = Today (Day {current_day}) | ◆ = Milestone Ready | ○ = Milestone Pending")

    print("\n" + "=" * 70)


def save_milestone_snapshot(state: dict):
    """Save milestone data for tracking."""
    milestones = get_milestone_status(state)

    snapshot = {
        "timestamp": datetime.now().isoformat(),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "current_day": state.get("challenge", {}).get("current_day", 0),
        "milestones": [
            {
                "day": m["day"],
                "status": m["status"],
                "ready": m["ready"],
                "progress_pct": m["progress_pct"],
                "days_until": m["days_until"],
            }
            for m in milestones
        ]
    }

    reports_dir = PROJECT_ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)

    with open(reports_dir / f"milestones_{snapshot['date']}.json", "w") as f:
        json.dump(snapshot, f, indent=2)

    return snapshot


def main():
    args = sys.argv[1:]
    summary = "--summary" in args
    upcoming = "--upcoming" in args

    state = load_system_state()

    if not state:
        print("❌ Error: Could not load system_state.json")
        return 1

    print_report(state, summary=summary, upcoming=upcoming)
    save_milestone_snapshot(state)

    return 0


if __name__ == "__main__":
    sys.exit(main())
