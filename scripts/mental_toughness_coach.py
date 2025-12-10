#!/usr/bin/env python3
"""Mental Toughness Coach CLI.

Interact with the mental toughness coach for trading psychology support.

Usage:
    python scripts/mental_toughness_coach.py start          # Start session
    python scripts/mental_toughness_coach.py status         # Get current state
    python scripts/mental_toughness_coach.py affirmation    # Get daily affirmation
    python scripts/mental_toughness_coach.py pre-trade      # Pre-trade check
    python scripts/mental_toughness_coach.py post-trade --win --pnl 15.50 --ticker SPY
    python scripts/mental_toughness_coach.py ready          # Check readiness
    python scripts/mental_toughness_coach.py coach "I'm feeling scared"
    python scripts/mental_toughness_coach.py end            # End session
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from coaching import MentalToughnessCoach


def format_intervention(intervention) -> str:
    """Format an intervention for display."""
    severity_icons = {
        "info": "i",
        "warning": "!",
        "critical": "X",
    }
    icon = severity_icons.get(intervention.severity, "i")

    lines = [
        f"\n[{icon}] {intervention.headline}",
        "-" * 60,
        intervention.message,
        "",
        "Action Items:",
    ]
    for i, action in enumerate(intervention.action_items, 1):
        lines.append(f"  {i}. {action}")

    if intervention.context:
        lines.append("")
        lines.append(f"Context: {json.dumps(intervention.context, default=str)}")

    return "\n".join(lines)


def cmd_start(coach: MentalToughnessCoach, args) -> None:
    """Start a coaching session."""
    intervention = coach.start_session()
    print(format_intervention(intervention))
    print("\nSession started. Good luck today!")


def cmd_status(coach: MentalToughnessCoach, args) -> None:
    """Show current psychological state."""
    summary = coach.get_state_summary()
    print("\n=== Mental Toughness Status ===")
    print(f"Zone:            {summary['zone'].upper()}")
    print(f"Confidence:      {summary['confidence']}")
    print(f"Mental Energy:   {summary['mental_energy']}")
    print(f"Readiness:       {summary['readiness_score']}")
    print(f"Trades Today:    {summary['trades_today']}")
    print(f"Win Streak:      {summary['consecutive_wins']}")
    print(f"Loss Streak:     {summary['consecutive_losses']}")

    if summary["active_biases"]:
        print(f"Active Biases:   {', '.join(summary['active_biases'])}")

    print("\nSiebold Principle Scores (0-10):")
    for name, score in summary["siebold_scores"].items():
        print(f"  {name.replace('_', ' ').title()}: {score:.1f}")


def cmd_affirmation(coach: MentalToughnessCoach, args) -> None:
    """Get daily affirmation."""
    affirmation = coach.get_daily_affirmation()
    print("\n=== Daily Affirmation ===")
    print(affirmation)


def cmd_pre_trade(coach: MentalToughnessCoach, args) -> None:
    """Pre-trade mental check."""
    intervention = coach.pre_trade_check(ticker=args.ticker or "")
    if intervention:
        print(format_intervention(intervention))
    else:
        print("\nMental state is clear. You are ready to trade.")


def cmd_post_trade(coach: MentalToughnessCoach, args) -> None:
    """Process trade result."""
    is_win = args.win
    pnl = args.pnl or 0.0
    ticker = args.ticker or ""

    interventions = coach.process_trade_result(
        is_win=is_win,
        pnl=pnl,
        ticker=ticker,
    )

    if interventions:
        for intervention in interventions:
            print(format_intervention(intervention))
    else:
        if is_win:
            print("\nTrade processed. Nice work staying disciplined!")
        else:
            print("\nTrade processed. Remember: losses are tuition.")


def cmd_ready(coach: MentalToughnessCoach, args) -> None:
    """Check if ready to trade."""
    is_ready, intervention = coach.is_ready_to_trade()

    if is_ready:
        print("\n[OK] You are READY to trade.")
        if intervention:
            print("Note: Some caution advised:")
            print(format_intervention(intervention))
    else:
        print("\n[STOP] You are NOT ready to trade.")
        if intervention:
            print(format_intervention(intervention))


def cmd_coach(coach: MentalToughnessCoach, args) -> None:
    """Request coaching for a situation."""
    situation = " ".join(args.situation)
    intervention = coach.request_coaching(situation)
    print(format_intervention(intervention))


def cmd_end(coach: MentalToughnessCoach, args) -> None:
    """End the coaching session."""
    intervention = coach.end_session()
    print(format_intervention(intervention))
    print("\nSession ended. Rest well and come back sharp!")


def cmd_perspective(coach: MentalToughnessCoach, args) -> None:
    """Get FIRE-inspired long-term perspective coaching."""
    intervention = coach.get_long_term_perspective()
    print(format_intervention(intervention))


def cmd_slowdown(coach: MentalToughnessCoach, args) -> None:
    """Activate System 2 thinking (Kahneman)."""
    intervention = coach.activate_system_two()
    print(format_intervention(intervention))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mental Toughness Coach - World-class trading psychology",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Start session
    subparsers.add_parser("start", help="Start a coaching session")

    # Status
    subparsers.add_parser("status", help="Get current psychological state")

    # Affirmation
    subparsers.add_parser("affirmation", help="Get daily affirmation")

    # Pre-trade
    pre_trade = subparsers.add_parser("pre-trade", help="Pre-trade mental check")
    pre_trade.add_argument("--ticker", type=str, help="Ticker symbol")

    # Post-trade
    post_trade = subparsers.add_parser("post-trade", help="Process trade result")
    post_trade.add_argument("--win", action="store_true", help="Trade was a win")
    post_trade.add_argument("--loss", action="store_true", help="Trade was a loss")
    post_trade.add_argument("--pnl", type=float, help="Profit/loss amount")
    post_trade.add_argument("--ticker", type=str, help="Ticker symbol")

    # Ready check
    subparsers.add_parser("ready", help="Check if ready to trade")

    # Request coaching
    coach_parser = subparsers.add_parser("coach", help="Request coaching for a situation")
    coach_parser.add_argument("situation", nargs="+", help="Describe your situation")

    # End session
    subparsers.add_parser("end", help="End the coaching session")

    # Long-term perspective (FIRE-inspired)
    subparsers.add_parser("perspective", help="Get FIRE-inspired long-term perspective")

    # System 2 activation (Kahneman-inspired)
    subparsers.add_parser("slowdown", help="Activate System 2 thinking (Kahneman)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Handle --loss flag
    if hasattr(args, "loss") and args.loss:
        args.win = False

    coach = MentalToughnessCoach()

    commands = {
        "start": cmd_start,
        "status": cmd_status,
        "affirmation": cmd_affirmation,
        "pre-trade": cmd_pre_trade,
        "post-trade": cmd_post_trade,
        "ready": cmd_ready,
        "coach": cmd_coach,
        "end": cmd_end,
        "perspective": cmd_perspective,
        "slowdown": cmd_slowdown,
    }

    cmd_func = commands.get(args.command)
    if cmd_func:
        cmd_func(coach, args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
