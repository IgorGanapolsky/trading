from src.safety.milestone_controller import compute_milestone_snapshot


def main():
    """
    Formally assess the North Star probability.
    Uses the system's own milestone and probability logic.
    """
    print("🔭 Formally assessing North Star trajectory...")

    status = compute_milestone_snapshot()
    ns = status.get("north_star_probability", {})

    print("\n" + "=" * 60)
    print("NORTH STAR PROBABILITY REPORT")
    print("=" * 60)
    print("Goal: $6,000/month after-tax")
    score = float(ns.get("score", ns.get("probability_score", 0.0)) or 0.0)
    label = str(ns.get("label", ns.get("probability_label", "unknown")) or "unknown")
    print(f"Confidence Score: {score:.1f}%")
    print(f"Label: {label.upper()}")
    print(f"Target Mode: {ns.get('target_mode', 'N/A')}")
    print(
        f"Estimated Monthly (Current Expectancy): ${ns.get('estimated_monthly_after_tax_from_expectancy', 0):.2f}"
    )
    print(f"Monthly Target Progress: {ns.get('monthly_target_progress_pct', 0):.2f}%")

    print("\n" + "=" * 60)
    print("CTO HONEST ASSESSMENT")
    print("=" * 60)
    if score > 80:
        print("✅ SYSTEM IS PROVEN. Trajectory is high-certainty.")
    elif score > 50:
        print("🟡 SYSTEM IS CAPABLE. Trajectory is positive but requires scaling.")
    else:
        print("🔴 SYSTEM IS UNPROVEN. We have the 'Brain' but lack the 'History'.")
        print("\nDeficiencies found:")
        print("1. Data Starvation: Need 30+ real trades to prove win rate.")
        print("2. Capital Gap: Current $101K is only 30% of required $350K base.")
        print("3. Tax Erosion: SPY is taxed higher than SPX (need to pivot in Phase 2).")


if __name__ == "__main__":
    main()
