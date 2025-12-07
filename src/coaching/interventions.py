"""Coaching Interventions.

Defines specific coaching interventions based on Steve Siebold's
"177 Mental Toughness Secrets of the World Class" principles.

Each intervention is mapped to specific Siebold principles and
provides actionable coaching for the trading system.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class InterventionType(str, Enum):
    """Types of coaching interventions."""

    # Preventive (before potential issues)
    PRE_TRADE_PREP = "pre_trade_prep"
    SESSION_START = "session_start"
    RISK_CHECK = "risk_check"

    # Corrective (during issues)
    EMOTIONAL_RESET = "emotional_reset"
    BIAS_CORRECTION = "bias_correction"
    DISCIPLINE_REMINDER = "discipline_reminder"
    CIRCUIT_BREAKER = "circuit_breaker"

    # Recovery (after issues)
    LOSS_PROCESSING = "loss_processing"
    WIN_GROUNDING = "win_grounding"
    SESSION_REVIEW = "session_review"

    # Development (ongoing improvement)
    METACOGNITION = "metacognition"
    CONFIDENCE_BUILDING = "confidence_building"
    PURPOSE_REMINDER = "purpose_reminder"
    LONG_TERM_PERSPECTIVE = "long_term_perspective"  # FIRE-inspired
    SYSTEM_TWO_ACTIVATION = "system_two_activation"  # Kahneman-inspired


class SieboldPrinciple(str, Enum):
    """Key principles from Siebold's book applicable to trading."""

    # Emotional Management
    COMPARTMENTALIZE_EMOTIONS = "compartmentalize_emotions"  # #2
    MASTER_MENTAL_ORGANIZATION = "master_mental_organization"  # #14
    SEEK_BALANCE = "seek_balance"  # #16

    # Mindset
    SUPREME_SELF_CONFIDENCE = "supreme_self_confidence"  # #4
    OPERATE_FROM_ABUNDANCE = "operate_from_abundance"  # #8
    KNOW_WHY_FIGHTING = "know_why_fighting"  # #7
    EMBRACE_METACOGNITION = "embrace_metacognition"  # #5

    # Growth
    ARE_COACHABLE = "are_coachable"  # #6
    SCHOOL_NEVER_OUT = "school_never_out"  # #10
    ZEALOTS_FOR_CHANGE = "zealots_for_change"  # #12

    # Resilience
    NOT_AFRAID_TO_SUFFER = "not_afraid_to_suffer"  # #18
    FAILURE_IS_DATA = "failure_is_data"  # Reframe failure
    ARE_BOLD = "are_bold"  # #11

    # FIRE Movement Principles (Financial Independence, Retire Early)
    COMPOUND_THINKING = "compound_thinking"  # Long-term exponential growth
    DELAYED_GRATIFICATION = "delayed_gratification"  # Sacrifice now for later
    SYSTEMATIC_WEALTH = "systematic_wealth"  # Process over outcomes

    # Kahneman Principles (Thinking, Fast and Slow)
    SYSTEM_TWO_THINKING = "system_two_thinking"  # Slow, deliberate, logical
    LOSS_AVERSION_AWARENESS = "loss_aversion_awareness"  # Losses hurt 2x more
    ANCHORING_AWARENESS = "anchoring_awareness"  # Don't anchor to entry price
    WYSIATI_AWARENESS = "wysiati_awareness"  # What You See Is All There Is
    REGRESSION_TO_MEAN = "regression_to_mean"  # Extremes revert to average


@dataclass
class CoachingIntervention:
    """A specific coaching intervention with content."""

    intervention_type: InterventionType
    principles: list[SieboldPrinciple]
    headline: str
    message: str
    action_items: list[str]
    severity: str = "info"  # info, warning, critical
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "type": self.intervention_type.value,
            "principles": [p.value for p in self.principles],
            "headline": self.headline,
            "message": self.message,
            "action_items": self.action_items,
            "severity": self.severity,
            "timestamp": self.timestamp.isoformat(),
            "context": self.context,
        }


# ============================================================================
# INTERVENTION TEMPLATES
# ============================================================================

# Pre-Trade Preparation
PRE_TRADE_INTERVENTIONS = [
    CoachingIntervention(
        intervention_type=InterventionType.PRE_TRADE_PREP,
        principles=[
            SieboldPrinciple.EMBRACE_METACOGNITION,
            SieboldPrinciple.MASTER_MENTAL_ORGANIZATION,
        ],
        headline="Pre-Trade Mental Check",
        message=(
            "Champions think about their thinking (Siebold #5). Before this trade: "
            "Am I trading the SETUP or trading my EMOTIONS? Is this a high-quality "
            "opportunity or am I forcing a trade?"
        ),
        action_items=[
            "Verify setup matches documented strategy criteria",
            "Confirm position size aligns with risk rules",
            "Check: Would I take this trade if I were flat today?",
        ],
    ),
    CoachingIntervention(
        intervention_type=InterventionType.PRE_TRADE_PREP,
        principles=[SieboldPrinciple.KNOW_WHY_FIGHTING],
        headline="Purpose Alignment Check",
        message=(
            "Champions know why they're fighting (Siebold #7). This trade should "
            "serve your North Star goal: building a system that compounds to $100+/day. "
            "Does this trade move you toward that goal?"
        ),
        action_items=[
            "Confirm this trade fits the systematic approach",
            "Verify it's not an impulsive deviation from plan",
            "Remember: Each trade is data, not destiny",
        ],
    ),
]

# Session Start
SESSION_START_INTERVENTIONS = [
    CoachingIntervention(
        intervention_type=InterventionType.SESSION_START,
        principles=[
            SieboldPrinciple.OPERATE_FROM_ABUNDANCE,
            SieboldPrinciple.SUPREME_SELF_CONFIDENCE,
        ],
        headline="World-Class Session Start",
        message=(
            "World-class performers operate from love and abundance (Siebold #8). "
            "Today's session begins with a full tank of mental energy. You have a "
            "proven system, clear rules, and unlimited learning opportunities. "
            "Trade with confidence, not desperation."
        ),
        action_items=[
            "Review today's market conditions calmly",
            "Set daily risk limits and honor them",
            "Commit to executing the system, not chasing profits",
        ],
    ),
    CoachingIntervention(
        intervention_type=InterventionType.SESSION_START,
        principles=[SieboldPrinciple.MASTER_MENTAL_ORGANIZATION],
        headline="Mental Organization Ritual",
        message=(
            "The great ones are masters of mental organization (Siebold #14). "
            "Start this session with clear intentions. What setups are you looking for? "
            "What will you NOT trade? Mental clarity precedes trading clarity."
        ),
        action_items=[
            "Review watchlist and priority setups",
            "Identify 'no-trade' conditions for today",
            "Set mental stop: at what point do you walk away?",
        ],
    ),
]

# Emotional Reset (after losses)
EMOTIONAL_RESET_INTERVENTIONS = [
    CoachingIntervention(
        intervention_type=InterventionType.EMOTIONAL_RESET,
        principles=[SieboldPrinciple.COMPARTMENTALIZE_EMOTIONS, SieboldPrinciple.FAILURE_IS_DATA],
        headline="Emotional Compartmentalization Required",
        message=(
            "The world class compartmentalize their emotions (Siebold #2). "
            "That loss is now CLOSED. It exists in the past. The next trade is "
            "independent - it doesn't know about the previous one. "
            "Separate the emotion from the analysis."
        ),
        action_items=[
            "Take 3 deep breaths (physiological reset)",
            "Log the loss with objective analysis: What went wrong?",
            "Ask: If I just sat down fresh, would I take the next trade?",
        ],
        severity="warning",
    ),
    CoachingIntervention(
        intervention_type=InterventionType.EMOTIONAL_RESET,
        principles=[SieboldPrinciple.NOT_AFRAID_TO_SUFFER, SieboldPrinciple.FAILURE_IS_DATA],
        headline="Embrace the Suffering",
        message=(
            "The great ones aren't afraid to suffer (Siebold #18). Losses hurt - "
            "that's normal and healthy. But champions use pain as fuel, not poison. "
            "This loss is TUITION for your trading education. What did it teach you?"
        ),
        action_items=[
            "Write down ONE lesson from this loss",
            "Add to learned_patterns in system state",
            "Transform the pain into process improvement",
        ],
        severity="warning",
    ),
]

# Bias Correction
BIAS_CORRECTION_INTERVENTIONS = {
    "overconfidence": CoachingIntervention(
        intervention_type=InterventionType.BIAS_CORRECTION,
        principles=[SieboldPrinciple.EMBRACE_METACOGNITION, SieboldPrinciple.SEEK_BALANCE],
        headline="Overconfidence Alert",
        message=(
            "METACOGNITION CHECK: Your winning streak is excellent, but world-class "
            "performers stay grounded (Siebold #16). Overconfidence is the enemy. "
            "The market doesn't care about your streak. Each trade must stand alone."
        ),
        action_items=[
            "Reduce position size by 20% for next trade",
            "Re-verify setup quality - don't lower your standards",
            "Remember: The market humbles everyone eventually",
        ],
        severity="warning",
    ),
    "revenge_trading": CoachingIntervention(
        intervention_type=InterventionType.BIAS_CORRECTION,
        principles=[SieboldPrinciple.COMPARTMENTALIZE_EMOTIONS, SieboldPrinciple.ARE_COACHABLE],
        headline="Revenge Trading Risk Detected",
        message=(
            "DANGER: Revenge trading is the most destructive pattern in trading. "
            "You're trying to 'get back' at the market. The market doesn't care. "
            "Champions are coachable (Siebold #6) - accept this feedback: STOP."
        ),
        action_items=[
            "Mandatory 30-minute break from trading",
            "Review the losses objectively - were they valid setups?",
            "If you MUST trade, reduce size by 50%",
        ],
        severity="critical",
    ),
    "fomo": CoachingIntervention(
        intervention_type=InterventionType.BIAS_CORRECTION,
        principles=[
            SieboldPrinciple.OPERATE_FROM_ABUNDANCE,
            SieboldPrinciple.SUPREME_SELF_CONFIDENCE,
        ],
        headline="FOMO Detected",
        message=(
            "You're feeling fear of missing out. World-class performers operate from "
            "abundance (Siebold #8) - there are ALWAYS more opportunities. "
            "Chasing moves is amateur behavior. Let it go."
        ),
        action_items=[
            "Close the chart for this ticker",
            "The best trades come to you - you don't chase them",
            "Trust: Your system will find the next opportunity",
        ],
        severity="warning",
    ),
    "loss_aversion": CoachingIntervention(
        intervention_type=InterventionType.BIAS_CORRECTION,
        principles=[SieboldPrinciple.FAILURE_IS_DATA, SieboldPrinciple.NOT_AFRAID_TO_SUFFER],
        headline="Loss Aversion Detected",
        message=(
            "You're feeling the sting of losses more than the pleasure of gains. "
            "This is human nature but world-class performers transcend it. "
            "Reframe: Losses are the COST OF DOING BUSINESS. They're tuition."
        ),
        action_items=[
            "Review your overall win rate - focus on the SYSTEM, not individual trades",
            "Calculate expectancy: Even with 40% win rate, you can be profitable",
            "Remember: Every professional trader has losing days",
        ],
        severity="info",
    ),
}

# Circuit Breaker (emergency stop)
CIRCUIT_BREAKER_INTERVENTIONS = [
    CoachingIntervention(
        intervention_type=InterventionType.CIRCUIT_BREAKER,
        principles=[SieboldPrinciple.SEEK_BALANCE, SieboldPrinciple.MASTER_MENTAL_ORGANIZATION],
        headline="CIRCUIT BREAKER ACTIVATED",
        message=(
            "TRADING HALT. You've hit your psychological circuit breaker. "
            "The world class seek balance (Siebold #16). Right now, the highest-EV "
            "action is NOT TRADING. Protect your capital and your psychology."
        ),
        action_items=[
            "STOP trading immediately - no exceptions",
            "Close all charts and trading platforms",
            "30-minute minimum break: walk, breathe, reset",
            "Review session only after emotional reset",
        ],
        severity="critical",
    ),
]

# Win Grounding (after wins, prevent overconfidence)
WIN_GROUNDING_INTERVENTIONS = [
    CoachingIntervention(
        intervention_type=InterventionType.WIN_GROUNDING,
        principles=[SieboldPrinciple.SEEK_BALANCE, SieboldPrinciple.SCHOOL_NEVER_OUT],
        headline="Win Processing",
        message=(
            "Excellent execution. Now ground yourself. School is never out for the "
            "great ones (Siebold #10). What made this trade work? Can you replicate it? "
            "Don't let this win inflate your risk-taking."
        ),
        action_items=[
            "Log what made this setup high-quality",
            "Maintain same position sizing for next trade",
            "Stay humble - the market giveth and taketh away",
        ],
    ),
]

# Session Review
SESSION_REVIEW_INTERVENTIONS = [
    CoachingIntervention(
        intervention_type=InterventionType.SESSION_REVIEW,
        principles=[SieboldPrinciple.EMBRACE_METACOGNITION, SieboldPrinciple.ARE_COACHABLE],
        headline="End-of-Session Reflection",
        message=(
            "Champions embrace metacognition (Siebold #5). Review this session: "
            "Did you execute YOUR system or deviate? Were your entries/exits "
            "rules-based or emotional? What will you do differently tomorrow?"
        ),
        action_items=[
            "Grade each trade: A (perfect execution) to F (emotional)",
            "Identify ONE thing to improve tomorrow",
            "Acknowledge what you did WELL",
            "Reset mentally - tomorrow is a fresh start",
        ],
    ),
]

# Purpose Reminder (for motivation)
PURPOSE_REMINDER_INTERVENTIONS = [
    CoachingIntervention(
        intervention_type=InterventionType.PURPOSE_REMINDER,
        principles=[SieboldPrinciple.KNOW_WHY_FIGHTING, SieboldPrinciple.ARE_BOLD],
        headline="Remember Your North Star",
        message=(
            "Champions know why they're fighting (Siebold #7). Your North Star: "
            "Build a compound engineering system that reaches $100+/day. "
            "This isn't about today's P/L - it's about building something that "
            "gets smarter every day. Stay the course."
        ),
        action_items=[
            "Focus on PROCESS, not profits",
            "Each trade improves the system",
            "Trust the compound engineering approach",
        ],
    ),
]

# ============================================================================
# FIRE MOVEMENT INTERVENTIONS (Long-Term Perspective)
# ============================================================================
# Based on Financial Independence, Retire Early principles
# Origin: "Your Money or Your Life" (1992), Mr. Money Mustache blog (2011)

LONG_TERM_PERSPECTIVE_INTERVENTIONS = [
    CoachingIntervention(
        intervention_type=InterventionType.LONG_TERM_PERSPECTIVE,
        principles=[SieboldPrinciple.COMPOUND_THINKING, SieboldPrinciple.KNOW_WHY_FIGHTING],
        headline="The Power of Compound Growth",
        message=(
            "FIRE PRINCIPLE: Today's $5.50 P/L is noise. You're building a SYSTEM. "
            "At 62% win rate with proper position sizing, $1/day becomes $100/day "
            "through compound engineering. Einstein called compound interest the "
            "8th wonder of the world. Your edge compounds. Your skills compound. "
            "Your capital compounds. Stay patient."
        ),
        action_items=[
            "Zoom out: Where will you be in 90 days at this trajectory?",
            "Each trade is a data point, not a destination",
            "Trust the math: Win rate + edge + time = wealth",
        ],
    ),
    CoachingIntervention(
        intervention_type=InterventionType.LONG_TERM_PERSPECTIVE,
        principles=[
            SieboldPrinciple.DELAYED_GRATIFICATION,
            SieboldPrinciple.OPERATE_FROM_ABUNDANCE,
        ],
        headline="Delayed Gratification is Your Superpower",
        message=(
            "FIRE PRINCIPLE: Average people need instant gratification. The wealthy "
            "understand delayed gratification. You're in Day 9 of 90 - the R&D phase. "
            "This is the ACCUMULATION period. Every trade teaches the system something. "
            "The payoff comes later, but it comes exponentially."
        ),
        action_items=[
            "Don't judge the harvest while planting seeds",
            "Focus on execution quality, not daily P/L",
            "Remember: Month 6 target is $100+/day - stay the course",
        ],
    ),
    CoachingIntervention(
        intervention_type=InterventionType.LONG_TERM_PERSPECTIVE,
        principles=[SieboldPrinciple.SYSTEMATIC_WEALTH, SieboldPrinciple.SCHOOL_NEVER_OUT],
        headline="Systems Beat Goals",
        message=(
            "FIRE PRINCIPLE: Goals are for amateurs. SYSTEMS are for professionals. "
            "You don't have a 'make money today' goal - you have a SYSTEM that "
            "compounds intelligence daily. The system is working even when individual "
            "trades lose. Trust the process. The 4% rule works because systems work."
        ),
        action_items=[
            "Ask: Is the SYSTEM improving? (Not: Did I profit today?)",
            "Log what the system learned from each trade",
            "Refine the edge, don't chase the outcome",
        ],
    ),
    CoachingIntervention(
        intervention_type=InterventionType.LONG_TERM_PERSPECTIVE,
        principles=[SieboldPrinciple.COMPOUND_THINKING, SieboldPrinciple.SEEK_BALANCE],
        headline="Your FIRE Number is Building",
        message=(
            "FIRE PRINCIPLE: Financial independence = 25x annual expenses. "
            "You're not just trading - you're building a wealth engine. "
            "At $100/day (your North Star), that's $36,500/year passive income. "
            "25x = $912,500 equivalent. Each day the system improves, "
            "you're building toward that number."
        ),
        action_items=[
            "Think in years, not days",
            "Small daily improvements = massive long-term results",
            "Your future self will thank today's discipline",
        ],
    ),
    CoachingIntervention(
        intervention_type=InterventionType.LONG_TERM_PERSPECTIVE,
        principles=[SieboldPrinciple.DELAYED_GRATIFICATION, SieboldPrinciple.NOT_AFRAID_TO_SUFFER],
        headline="The R&D Phase is Your CoastFIRE",
        message=(
            "FIRE PRINCIPLE: CoastFIRE means front-loading the hard work so "
            "compound growth does the rest. You're in Days 1-90 - the front-loading "
            "phase. The losses NOW are investments in the system. By Month 6, "
            "the system trades FOR you. This temporary discomfort buys permanent freedom."
        ),
        action_items=[
            "Embrace the struggle - it's building your edge",
            "Document everything for future compound returns",
            "90 days of discipline = years of passive income",
        ],
    ),
    CoachingIntervention(
        intervention_type=InterventionType.LONG_TERM_PERSPECTIVE,
        principles=[SieboldPrinciple.SYSTEMATIC_WEALTH, SieboldPrinciple.OPERATE_FROM_ABUNDANCE],
        headline="Abundance Mindset: Infinite Opportunities",
        message=(
            "FIRE PRINCIPLE: Scarcity thinking leads to bad decisions. "
            "The market offers UNLIMITED opportunities every single day. "
            "Missing one trade means nothing. Revenge trading means everything (bad). "
            "Operate from abundance: There's always another setup tomorrow."
        ),
        action_items=[
            "Let go of 'missed' opportunities - more are coming",
            "Quality > Quantity in trade selection",
            "Patience is a wealth-building superpower",
        ],
    ),
]

# ============================================================================
# KAHNEMAN INTERVENTIONS (System 2 Thinking)
# ============================================================================
# Based on Daniel Kahneman's "Thinking, Fast and Slow" (Nobel Prize Economics)
# System 1: Fast, intuitive, emotional (causes trading errors)
# System 2: Slow, deliberate, logical (what we need for trading)

SYSTEM_TWO_INTERVENTIONS = [
    CoachingIntervention(
        intervention_type=InterventionType.SYSTEM_TWO_ACTIVATION,
        principles=[SieboldPrinciple.SYSTEM_TWO_THINKING, SieboldPrinciple.EMBRACE_METACOGNITION],
        headline="SLOW DOWN: Activate System 2",
        message=(
            "KAHNEMAN: Your System 1 (fast, emotional) is trying to make this decision. "
            "STOP. Engage System 2 (slow, logical). System 1 is great for catching a ball, "
            "terrible for trading. Take 30 seconds. Breathe. Now ask: Does this trade "
            "meet ALL my criteria, or am I feeling pressure to act?"
        ),
        action_items=[
            "Pause for 30 seconds before ANY trade decision",
            "Verbalize your reasoning out loud (activates System 2)",
            "Check: Am I trading the SETUP or trading my EMOTIONS?",
        ],
        severity="warning",
    ),
    CoachingIntervention(
        intervention_type=InterventionType.SYSTEM_TWO_ACTIVATION,
        principles=[
            SieboldPrinciple.LOSS_AVERSION_AWARENESS,
            SieboldPrinciple.NOT_AFRAID_TO_SUFFER,
        ],
        headline="Loss Aversion Alert",
        message=(
            "KAHNEMAN: Humans feel losses 2x more intensely than equivalent gains. "
            "A $10 loss FEELS like a $20 gain. Your brain is lying to you. "
            "This asymmetry causes holding losers too long and cutting winners too early. "
            "The rational move often FEELS wrong. Trust your system, not your feelings."
        ),
        action_items=[
            "Ask: Would I enter this position TODAY at this price?",
            "If NO: Exit. The sunk cost is irrelevant.",
            "Remember: A loss realized is better than a loss compounded",
        ],
    ),
    CoachingIntervention(
        intervention_type=InterventionType.SYSTEM_TWO_ACTIVATION,
        principles=[SieboldPrinciple.ANCHORING_AWARENESS, SieboldPrinciple.EMBRACE_METACOGNITION],
        headline="Anchoring Bias Detected",
        message=(
            "KAHNEMAN: You're ANCHORED to a reference point (likely your entry price). "
            "The market doesn't care what you paid. Your entry price is IRRELEVANT "
            "to where the stock goes next. Evaluate this position as if you just "
            "discovered it today. Would you buy it NOW at the current price?"
        ),
        action_items=[
            "Forget your entry price - it's a sunk cost",
            "Evaluate: Is this a GOOD position at TODAY's price?",
            "The market owes you nothing. Trade what IS, not what WAS.",
        ],
    ),
    CoachingIntervention(
        intervention_type=InterventionType.SYSTEM_TWO_ACTIVATION,
        principles=[SieboldPrinciple.WYSIATI_AWARENESS, SieboldPrinciple.ARE_COACHABLE],
        headline="WYSIATI Warning: Limited Information",
        message=(
            "KAHNEMAN: 'What You See Is All There Is' - your brain builds confident "
            "stories from limited data. You're seeing a FRACTION of relevant information. "
            "The chart, the news, your analysis - it's incomplete. Overconfidence comes "
            "from coherent stories, not complete information. Stay humble."
        ),
        action_items=[
            "Ask: What am I NOT seeing that could matter?",
            "Reduce position size when uncertainty is high",
            "The less you know, the smaller you should bet",
        ],
    ),
    CoachingIntervention(
        intervention_type=InterventionType.SYSTEM_TWO_ACTIVATION,
        principles=[SieboldPrinciple.REGRESSION_TO_MEAN, SieboldPrinciple.SEEK_BALANCE],
        headline="Regression to Mean: Streaks End",
        message=(
            "KAHNEMAN: Extreme results regress to the mean. Hot streaks cool off. "
            "Cold streaks warm up. This isn't mystical - it's mathematics. "
            "Your recent performance (good OR bad) is partially luck. "
            "Don't increase risk after wins or despair after losses. The mean is coming."
        ),
        action_items=[
            "After wins: Don't increase risk - regression is coming",
            "After losses: Don't despair - regression is coming",
            "Stay consistent. The system works over MANY trades.",
        ],
    ),
    CoachingIntervention(
        intervention_type=InterventionType.SYSTEM_TWO_ACTIVATION,
        principles=[
            SieboldPrinciple.SYSTEM_TWO_THINKING,
            SieboldPrinciple.MASTER_MENTAL_ORGANIZATION,
        ],
        headline="The Planning Fallacy",
        message=(
            "KAHNEMAN: We systematically underestimate time, costs, and risks while "
            "overestimating benefits. 'This trade is different' is usually wrong. "
            "Your best prediction of how THIS trade will go is how SIMILAR trades went. "
            "Use base rates, not hopes. What's your historical win rate on setups like this?"
        ),
        action_items=[
            "Check historical win rate for this setup type",
            "Size the position based on ACTUAL data, not hope",
            "Remember: You're not special. Base rates apply to you.",
        ],
    ),
    CoachingIntervention(
        intervention_type=InterventionType.SYSTEM_TWO_ACTIVATION,
        principles=[SieboldPrinciple.SYSTEM_TWO_THINKING, SieboldPrinciple.SUPREME_SELF_CONFIDENCE],
        headline="Substitution: Easy Question for Hard One",
        message=(
            "KAHNEMAN: When faced with a hard question, System 1 secretly substitutes "
            "an easier one. 'Is this a good trade?' becomes 'Do I FEEL good about this trade?' "
            "Feelings are not analysis. Force yourself to answer the ACTUAL question: "
            "Does this meet my documented criteria? Yes or No. Nothing else matters."
        ),
        action_items=[
            "Write down your ACTUAL criteria for entry",
            "Check each criterion with Yes/No (no maybes)",
            "If any criterion is No, the answer is No.",
        ],
    ),
]


def get_intervention_for_bias(bias_type: str) -> CoachingIntervention | None:
    """Get appropriate intervention for a detected bias."""
    return BIAS_CORRECTION_INTERVENTIONS.get(bias_type.lower())


def get_random_session_start() -> CoachingIntervention:
    """Get a random session start intervention."""
    return random.choice(SESSION_START_INTERVENTIONS)


def get_random_pre_trade() -> CoachingIntervention:
    """Get a random pre-trade intervention."""
    return random.choice(PRE_TRADE_INTERVENTIONS)


def get_random_emotional_reset() -> CoachingIntervention:
    """Get a random emotional reset intervention."""
    return random.choice(EMOTIONAL_RESET_INTERVENTIONS)


def get_circuit_breaker() -> CoachingIntervention:
    """Get circuit breaker intervention."""
    return CIRCUIT_BREAKER_INTERVENTIONS[0]


def get_random_win_grounding() -> CoachingIntervention:
    """Get win grounding intervention."""
    return random.choice(WIN_GROUNDING_INTERVENTIONS)


def get_session_review() -> CoachingIntervention:
    """Get session review intervention."""
    return SESSION_REVIEW_INTERVENTIONS[0]


def get_purpose_reminder() -> CoachingIntervention:
    """Get purpose reminder intervention."""
    return PURPOSE_REMINDER_INTERVENTIONS[0]


def get_random_long_term_perspective() -> CoachingIntervention:
    """Get a random FIRE-inspired long-term perspective intervention."""
    return random.choice(LONG_TERM_PERSPECTIVE_INTERVENTIONS)


def get_random_system_two() -> CoachingIntervention:
    """Get a random Kahneman System 2 intervention."""
    return random.choice(SYSTEM_TWO_INTERVENTIONS)
