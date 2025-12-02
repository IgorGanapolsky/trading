#!/usr/bin/env python3
"""
Quick Fibonacci Scaling Demo

Shows current level and what happens at different profit levels.
"""

# Simplified Fibonacci calculator (no dependencies)
FIBONACCI_SEQUENCE = [1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 100]


def get_level(profit):
    """Get Fibonacci level for given profit."""
    if profit <= 0:
        return 1
    level = 1
    for fib in FIBONACCI_SEQUENCE:
        if profit >= fib * 30:
            level = fib
        else:
            break
    return level


def show_scaling():
    """Show scaling at key profit levels."""
    print("=" * 70)
    print("FIBONACCI SCALING - QUICK REFERENCE")
    print("=" * 70)

    print("\n💰 Your Current Status:")
    print("  Profit: $5.50")
    print(f"  Current Level: ${get_level(5.5)}/day")
    print("  Next Milestone: $60 profit → $2/day")
    print("  Progress: 9.2% ($54.50 to go)")

    print("\n📈 Scaling Roadmap:")
    print(f"{'Profit $':<12} {'Daily Amount':<15} {'Milestone':<30}")
    print("-" * 70)

    milestones = [
        (0, "$1/day", "Start here"),
        (5.5, "$1/day", "👉 YOU ARE HERE"),
        (60, "$2/day", "First scale-up"),
        (90, "$3/day", "Second scale-up"),
        (150, "$5/day", ""),
        (240, "$8/day", ""),
        (390, "$13/day", ""),
        (630, "$21/day", ""),
        (1020, "$34/day", ""),
        (1650, "$55/day", ""),
        (2670, "$89/day", ""),
        (3000, "$100/day", "Maximum level"),
    ]

    for profit, amount, note in milestones:
        print(f"${profit:<11.2f} {amount:<14} {note:<30}")

    print("\n" + "=" * 70)
    print("Key: Each level funded ONLY by profits from previous level")
    print("Formula: Scale when cumulative_profit >= next_level × 30 days")
    print("=" * 70)


if __name__ == "__main__":
    show_scaling()
