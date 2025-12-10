# Mental Toughness Coach Skill

World-class trading psychology based on Steve Siebold's "177 Mental Toughness Secrets of the World Class".

## Overview

This skill provides real-time psychological coaching during trading. It monitors emotional state, detects cognitive biases, and provides interventions to maintain peak mental performance.

## Key Siebold Principles Applied

1. **Compartmentalize Emotions (#2)** - Don't let losses bleed into future trades
2. **Supreme Self Confidence (#4)** - Trust your system completely
3. **Embrace Metacognition (#5)** - Think about your thinking
4. **Are Coachable (#6)** - Accept feedback and adapt
5. **Know Why Fighting (#7)** - Clear purpose (North Star)
6. **Operate from Abundance (#8)** - Trade from confidence, not fear
7. **School Never Out (#10)** - Continuous learning
8. **Not Afraid to Suffer (#18)** - Losses are tuition

## Usage

### CLI Commands

```bash
# Start a coaching session (beginning of trading day)
python scripts/mental_toughness_coach.py start

# Check current psychological state
python scripts/mental_toughness_coach.py status

# Get daily affirmation
python scripts/mental_toughness_coach.py affirmation

# Pre-trade mental check
python scripts/mental_toughness_coach.py pre-trade --ticker SPY

# Process trade results
python scripts/mental_toughness_coach.py post-trade --win --pnl 15.50 --ticker SPY
python scripts/mental_toughness_coach.py post-trade --loss --pnl -8.25 --ticker QQQ

# Check if ready to trade
python scripts/mental_toughness_coach.py ready

# Request coaching for specific situations
python scripts/mental_toughness_coach.py coach "I'm feeling scared after that loss"
python scripts/mental_toughness_coach.py coach "I want to revenge trade"

# End session with review
python scripts/mental_toughness_coach.py end
```

### Programmatic Usage

```python
from src.coaching import MentalToughnessCoach

# Initialize coach
coach = MentalToughnessCoach()

# Start session
intervention = coach.start_session()
print(intervention.headline, intervention.message)

# Before each trade
intervention = coach.pre_trade_check(ticker="SPY")
if intervention:
    print(f"Coaching: {intervention.message}")

# After each trade
interventions = coach.process_trade_result(
    is_win=False,
    pnl=-8.25,
    ticker="SPY"
)
for i in interventions:
    print(f"[{i.severity}] {i.headline}: {i.message}")

# Check readiness
is_ready, intervention = coach.is_ready_to_trade()
if not is_ready:
    print(f"NOT READY: {intervention.message}")

# Request coaching
intervention = coach.request_coaching("I'm feeling overconfident")
print(intervention.message)
```

## Emotional Zones

- **FLOW**: Optimal performance state - clear to trade
- **CHALLENGE**: Healthy stress, focused - trade with awareness
- **CAUTION**: Elevated emotions - trade with reduced size
- **DANGER**: Emotional decision-making likely - consider pause
- **TILT**: Full emotional breakdown - STOP trading

## Detected Biases

The coach monitors for:
- **Overconfidence** - After winning streaks
- **Loss Aversion** - Feeling losses 2x more than gains
- **Revenge Trading** - Trying to recover losses quickly
- **FOMO** - Fear of missing out
- **Recency Bias** - Over-weighting recent events

## Integration Points

The coach integrates with:
- Pre-trade validation in orchestrator
- Post-trade processing in position manager
- Daily reporting system
- Telemetry/audit trail

## Files

- `src/coaching/__init__.py` - Module exports
- `src/coaching/mental_toughness_coach.py` - Main coach class
- `src/coaching/psychology_state.py` - State tracking
- `src/coaching/interventions.py` - Coaching interventions
- `scripts/mental_toughness_coach.py` - CLI interface
- `data/psychology_state.json` - Persistent state
- `data/audit_trail/coaching_log.jsonl` - Intervention log
