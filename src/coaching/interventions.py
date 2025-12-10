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
    SELF_DECEPTION_CHECK = "self_deception_check"  # Arbinger-inspired


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

    # Arbinger Principles (Leadership and Self-Deception)
    IN_THE_BOX = "in_the_box"  # Self-deception: seeing market/others as objects
    OUT_OF_THE_BOX = "out_of_the_box"  # Clear vision: seeing reality objectively
    SELF_BETRAYAL = "self_betrayal"  # Not following system when you know you should
    SELF_JUSTIFICATION = "self_justification"  # Blaming market for your mistakes
    RESPONSIBILITY_MINDSET = "responsibility_mindset"  # Own your decisions fully

    # Brian Tracy Principles (Focal Point)
    FOCAL_POINT = "focal_point"  # Focus on highest-value activity at any moment
    PARETO_PRINCIPLE = "pareto_principle"  # 80/20 rule - 20% of actions = 80% of results
    CLARITY_OF_PURPOSE = "clarity_of_purpose"  # Know exactly what you want
    SLAM_FORMULA = "slam_formula"  # Simplify, Leverage, Accelerate, Multiply
    WINNING_HABITS = "winning_habits"  # Build automatic positive behaviors

    # Tony Robbins Principles (Money Master the Game + Unshakeable)
    DONT_LOSE_MONEY = "dont_lose_money"  # #1 rule: Protect capital first
    ASYMMETRIC_RISK_REWARD = "asymmetric_risk_reward"  # Risk little to gain a lot
    PSYCHOLOGY_OVER_MECHANICS = "psychology_over_mechanics"  # 80% psychology, 20% mechanics
    UNSHAKEABLE_MINDSET = "unshakeable_mindset"  # Peace of mind in volatility
    BEAR_MARKET_OPPORTUNITY = "bear_market_opportunity"  # Turmoil = opportunity
    MONEY_MACHINE = "money_machine"  # Build income-generating portfolio


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

# ============================================================================
# ARBINGER INTERVENTIONS (Leadership and Self-Deception)
# ============================================================================
# Based on The Arbinger Institute's "Leadership and Self-Deception"
# Core concept: "The Box" - self-deception that prevents seeing reality clearly
# Self-betrayal → Self-justification → Self-deception cycle

SELF_DECEPTION_INTERVENTIONS = [
    CoachingIntervention(
        intervention_type=InterventionType.SELF_DECEPTION_CHECK,
        principles=[SieboldPrinciple.IN_THE_BOX, SieboldPrinciple.RESPONSIBILITY_MINDSET],
        headline="Are You 'In The Box'?",
        message=(
            "ARBINGER: When you're 'in the box', you see the market as an enemy to defeat, "
            "blame external factors for losses, and justify deviations from your system. "
            "Signs you're in the box: 'The market is rigged', 'Market makers hunted my stop', "
            "'This time is different'. These are self-justifications, not analysis."
        ),
        action_items=[
            "Ask: Am I blaming something external for my results?",
            "Check: Did I follow my system EXACTLY, or did I deviate?",
            "Reframe: The market is neutral. MY decisions created MY results.",
        ],
        severity="warning",
    ),
    CoachingIntervention(
        intervention_type=InterventionType.SELF_DECEPTION_CHECK,
        principles=[SieboldPrinciple.OUT_OF_THE_BOX, SieboldPrinciple.EMBRACE_METACOGNITION],
        headline="Get 'Out of The Box'",
        message=(
            "ARBINGER: Being 'out of the box' means seeing reality objectively. "
            "The market is not your enemy - it's an aggregate of millions of decisions. "
            "Your losses are not persecution - they're feedback. Your wins are not validation - "
            "they're data points. See clearly. Trade clearly."
        ),
        action_items=[
            "View losses as tuition, not injustice",
            "View wins as data, not destiny",
            "See the market as a teacher, not an adversary",
        ],
    ),
    CoachingIntervention(
        intervention_type=InterventionType.SELF_DECEPTION_CHECK,
        principles=[SieboldPrinciple.SELF_BETRAYAL, SieboldPrinciple.ARE_COACHABLE],
        headline="Self-Betrayal Detected",
        message=(
            "ARBINGER: Self-betrayal is when you KNOW what you should do but don't do it. "
            "You sensed you should follow your stop loss - but didn't. "
            "You sensed you should skip this trade - but entered anyway. "
            "You sensed the position was too large - but you sized up. "
            "This is the ROOT of all trading psychology problems."
        ),
        action_items=[
            "Identify: What did I KNOW I should do that I didn't?",
            "Acknowledge: I betrayed my own system/judgment",
            "Commit: Next time, I will honor my sense of what's right",
        ],
        severity="warning",
    ),
    CoachingIntervention(
        intervention_type=InterventionType.SELF_DECEPTION_CHECK,
        principles=[SieboldPrinciple.SELF_JUSTIFICATION, SieboldPrinciple.FAILURE_IS_DATA],
        headline="Self-Justification Warning",
        message=(
            "ARBINGER: After self-betrayal comes self-justification. You inflate your own virtue "
            "('I was being aggressive, not greedy') and demonize others ('The algos are cheating'). "
            "This distorts reality and guarantees you'll repeat the mistake. "
            "The cure: RADICAL HONESTY. What actually happened? What did YOU do?"
        ),
        action_items=[
            "Strip away the story - what are the raw facts?",
            "Own it fully: 'I made this decision. I created this result.'",
            "No excuses, no blame - just data for improvement",
        ],
        severity="warning",
    ),
    CoachingIntervention(
        intervention_type=InterventionType.SELF_DECEPTION_CHECK,
        principles=[
            SieboldPrinciple.RESPONSIBILITY_MINDSET,
            SieboldPrinciple.SUPREME_SELF_CONFIDENCE,
        ],
        headline="100% Responsibility Mindset",
        message=(
            "ARBINGER: World-class performers take 100% responsibility for their results. "
            "Not 50/50 with the market. Not 80/20 with news events. 100% YOU. "
            "This isn't about blame - it's about POWER. If it's your fault, you can fix it. "
            "If it's the market's fault, you're helpless. Choose power. Choose responsibility."
        ),
        action_items=[
            "Reframe every loss: 'What could I have done differently?'",
            "Reject victim language: 'The market made me...' → 'I chose to...'",
            "Embrace control: Your system, your rules, your results",
        ],
    ),
    CoachingIntervention(
        intervention_type=InterventionType.SELF_DECEPTION_CHECK,
        principles=[
            SieboldPrinciple.OUT_OF_THE_BOX,
            SieboldPrinciple.OPERATE_FROM_ABUNDANCE,
        ],
        headline="See The Market As People",
        message=(
            "ARBINGER: The market isn't a machine or enemy - it's millions of people making "
            "decisions based on their hopes, fears, and analysis. When you 'lose', someone else "
            "'won' - they're not evil, they just had different information or timing. "
            "This perspective reduces anger and increases learning."
        ),
        action_items=[
            "Remember: Every trade has a counterparty with their own reasons",
            "Ask: What might they know that I don't?",
            "Respect the collective wisdom while trusting your edge",
        ],
    ),
]

# ============================================================================
# BRIAN TRACY INTERVENTIONS (Focal Point)
# ============================================================================
# Based on Brian Tracy's "Focal Point: A Proven System to Simplify Your Life,
# Double Your Productivity, and Achieve All Your Goals"
# Core concept: Find your focal point - the highest-value activity at any moment

FOCAL_POINT_INTERVENTIONS = [
    CoachingIntervention(
        intervention_type=InterventionType.PURPOSE_REMINDER,
        principles=[SieboldPrinciple.FOCAL_POINT, SieboldPrinciple.KNOW_WHY_FIGHTING],
        headline="Find Your Focal Point",
        message=(
            "TRACY: At any moment, there is ONE activity that will provide the greatest benefit. "
            "In trading, your focal point is EXECUTING YOUR SYSTEM - not checking P/L, not reading "
            "news, not second-guessing entries. What is the single most valuable thing you can do "
            "RIGHT NOW to move toward $100+/day? Do that. Ignore everything else."
        ),
        action_items=[
            "Identify: What is MY highest-value activity right now?",
            "Execute: Do ONLY that activity until complete",
            "Resist: All distractions from your focal point",
        ],
    ),
    CoachingIntervention(
        intervention_type=InterventionType.PURPOSE_REMINDER,
        principles=[SieboldPrinciple.PARETO_PRINCIPLE, SieboldPrinciple.SYSTEMATIC_WEALTH],
        headline="The 80/20 Rule in Trading",
        message=(
            "TRACY: 20% of your activities produce 80% of your results. In trading: "
            "20% of your setups generate 80% of your profits. 20% of your analysis matters. "
            "80% of market noise is irrelevant. IDENTIFY your high-value 20% and focus there. "
            "Eliminate or minimize the 80% that's just busy-work disguised as trading."
        ),
        action_items=[
            "Audit: Which setups have generated most profits historically?",
            "Focus: Trade ONLY your best setups, not every opportunity",
            "Eliminate: News-checking, over-analysis, ticker-watching",
        ],
    ),
    CoachingIntervention(
        intervention_type=InterventionType.PURPOSE_REMINDER,
        principles=[SieboldPrinciple.CLARITY_OF_PURPOSE, SieboldPrinciple.EMBRACE_METACOGNITION],
        headline="Clarity Creates Success",
        message=(
            "TRACY: 'Successful people have tremendous clarity about who they are, what they want, "
            "and how they are going to get it.' Your clarity: You are building a compound engineering "
            "trading system. You want $100+/day passive income. You achieve it through systematic "
            "execution of validated strategies. This clarity should drive EVERY decision."
        ),
        action_items=[
            "State your trading identity: 'I am a systematic trader'",
            "State your goal: '$100+/day through compound engineering'",
            "State your method: 'Execute validated strategies without emotion'",
        ],
    ),
    CoachingIntervention(
        intervention_type=InterventionType.PURPOSE_REMINDER,
        principles=[SieboldPrinciple.SLAM_FORMULA, SieboldPrinciple.COMPOUND_THINKING],
        headline="The SLAM Formula for Trading",
        message=(
            "TRACY's SLAM Formula applied to trading:\n"
            "• SIMPLIFY: Reduce to 2-3 high-quality setups, eliminate complexity\n"
            "• LEVERAGE: Use RL agents, automation, multi-LLM analysis\n"
            "• ACCELERATE: Execute decisions quickly once criteria are met\n"
            "• MULTIPLY: Let compounding do the heavy lifting over time"
        ),
        action_items=[
            "Simplify: What can I REMOVE from my trading process?",
            "Leverage: What tools/automation am I underutilizing?",
            "Accelerate: Where am I hesitating when I should act?",
            "Multiply: Am I letting profits compound or withdrawing?",
        ],
    ),
    CoachingIntervention(
        intervention_type=InterventionType.PURPOSE_REMINDER,
        principles=[SieboldPrinciple.WINNING_HABITS, SieboldPrinciple.SCHOOL_NEVER_OUT],
        headline="Build Winning Trading Habits",
        message=(
            "TRACY: 'Habits shape behavior.' Your trading success depends on automatic habits: "
            "Morning market prep at 9:00 AM. Execute at 9:35 AM. Review at market close. "
            "Log every trade. Never revenge trade. Never skip stops. These habits, repeated daily, "
            "become your trading character. Character determines destiny."
        ),
        action_items=[
            "Morning routine: Market conditions check, setup identification",
            "Execution routine: Criteria met → Trade. Not met → No trade.",
            "Evening routine: Log trades, grade execution, identify improvements",
        ],
    ),
    CoachingIntervention(
        intervention_type=InterventionType.PURPOSE_REMINDER,
        principles=[
            SieboldPrinciple.RESPONSIBILITY_MINDSET,
            SieboldPrinciple.FOCAL_POINT,
        ],
        headline="Stop Doing Low-Value Activities",
        message=(
            "TRACY: There are four ways to improve - do more of some things, less of others, "
            "start new things, and STOP some things entirely. What should you STOP in trading? "
            "Checking P/L every 5 minutes. Reading news during market hours. Trading out of boredom. "
            "Discussing trades in chat rooms. These activities feel productive but destroy focus."
        ),
        action_items=[
            "STOP: Checking P/L more than once per hour",
            "STOP: Trading setups not in your documented strategy",
            "STOP: Seeking validation from others for your trades",
            "START: Trusting your system and executing mechanically",
        ],
    ),
]


# ============================================================================
# TONY ROBBINS INTERVENTIONS (Money Master the Game + Unshakeable)
# ============================================================================
# Based on Tony Robbins' financial freedom books combining investing wisdom
# from 50+ billionaires with psychology of wealth creation
# Core insight: 80% of success is psychology, 20% is mechanics

TONY_ROBBINS_INTERVENTIONS = [
    CoachingIntervention(
        intervention_type=InterventionType.PURPOSE_REMINDER,
        principles=[SieboldPrinciple.DONT_LOSE_MONEY, SieboldPrinciple.SEEK_BALANCE],
        headline="Rule #1: Don't Lose Money",
        message=(
            "ROBBINS: Every billionaire investor shares ONE obsession: Don't lose money. "
            "Warren Buffett's Rule #1: Never lose money. Rule #2: Never forget Rule #1. "
            "Why? A 50% loss requires a 100% gain just to break even. Protect your capital FIRST. "
            "In trading, this means: Honor stop losses. Size positions correctly. Never risk ruin."
        ),
        action_items=[
            "Set stop losses BEFORE entering any trade",
            "Never risk more than 1-2% of capital on a single trade",
            "Ask: 'What's the worst case?' before every entry",
        ],
    ),
    CoachingIntervention(
        intervention_type=InterventionType.PURPOSE_REMINDER,
        principles=[SieboldPrinciple.ASYMMETRIC_RISK_REWARD, SieboldPrinciple.ARE_BOLD],
        headline="Asymmetric Risk/Reward",
        message=(
            "ROBBINS: The wealthy risk a LITTLE to make a LOT. They seek asymmetric opportunities "
            "where the upside far exceeds the downside. In trading: If you risk $1 to potentially "
            "make $3, you only need to win 33% of the time to break even. At 62% win rate, you're "
            "printing money. Always calculate risk/reward BEFORE entering."
        ),
        action_items=[
            "Minimum 2:1 reward-to-risk ratio on every trade",
            "Calculate exact profit target and stop loss before entry",
            "Pass on trades where reward doesn't justify risk",
        ],
    ),
    CoachingIntervention(
        intervention_type=InterventionType.PURPOSE_REMINDER,
        principles=[
            SieboldPrinciple.PSYCHOLOGY_OVER_MECHANICS,
            SieboldPrinciple.EMBRACE_METACOGNITION,
        ],
        headline="80% Psychology, 20% Mechanics",
        message=(
            "ROBBINS: '80% of success is psychology, 20% is mechanics.' You can have the best "
            "strategy in the world, but if your psychology is broken, you'll sabotage yourself. "
            "The parts of your brain that process financial losses are the SAME parts that respond "
            "to mortal threats. Your brain is designed to make dumb investing decisions. Override it."
        ),
        action_items=[
            "Acknowledge: Your emotions are trying to sabotage you",
            "Use automation to remove emotion from execution",
            "Pre-commit to decisions BEFORE the market opens",
        ],
    ),
    CoachingIntervention(
        intervention_type=InterventionType.PURPOSE_REMINDER,
        principles=[SieboldPrinciple.UNSHAKEABLE_MINDSET, SieboldPrinciple.NOT_AFRAID_TO_SUFFER],
        headline="Become Unshakeable",
        message=(
            "ROBBINS: Being 'unshakeable' means maintaining peace of mind in volatility, uncertainty, "
            "and chaos - while PROFITING from the fear that paralyzes others. The unshakeable trader "
            "doesn't panic during drawdowns, doesn't get euphoric during wins, and executes the system "
            "regardless of recent results. Volatility is your friend, not your enemy."
        ),
        action_items=[
            "Expect volatility - it's normal, not an emergency",
            "Have a plan for drawdowns BEFORE they happen",
            "Use fear as a signal to LOOK for opportunities, not run",
        ],
    ),
    CoachingIntervention(
        intervention_type=InterventionType.PURPOSE_REMINDER,
        principles=[
            SieboldPrinciple.BEAR_MARKET_OPPORTUNITY,
            SieboldPrinciple.OPERATE_FROM_ABUNDANCE,
        ],
        headline="Bear Markets = Opportunity",
        message=(
            "ROBBINS: 'Market turmoil isn't something to fear. It's the greatest opportunity to "
            "leapfrog to financial freedom.' Every bear market in US history has been followed by "
            "a bull market - without exception. The wealthy buy when others are panicking. "
            "90% of surviving a bear market is PREPARATION, 10% is emotional reaction."
        ),
        action_items=[
            "Have cash ready to deploy during market panics",
            "View corrections as sales, not disasters",
            "Remember: Today's crisis is tomorrow's opportunity",
        ],
    ),
    CoachingIntervention(
        intervention_type=InterventionType.PURPOSE_REMINDER,
        principles=[SieboldPrinciple.MONEY_MACHINE, SieboldPrinciple.COMPOUND_THINKING],
        headline="Build Your Money Machine",
        message=(
            "ROBBINS: 'You're never going to EARN your way to financial freedom. The real route "
            "is to invest and let it compound over years. That's how you make money your slave "
            "instead of being a slave to money.' Your trading system IS your money machine. "
            "Each day it gets smarter. Each trade compounds the edge. Build the machine."
        ),
        action_items=[
            "Think of your system as a machine that produces income",
            "Reinvest profits to compound the machine's power",
            "Your job: Maintain and improve the machine, not work harder",
        ],
    ),
    CoachingIntervention(
        intervention_type=InterventionType.BIAS_CORRECTION,
        principles=[
            SieboldPrinciple.PSYCHOLOGY_OVER_MECHANICS,
            SieboldPrinciple.LOSS_AVERSION_AWARENESS,
        ],
        headline="The 6 Psychological Mistakes",
        message=(
            "ROBBINS' 6 mistakes that destroy wealth:\n"
            "1. CONFIRMATION BIAS: Seeking info that confirms your view\n"
            "2. RECENCY BIAS: Over-weighting recent events\n"
            "3. OVERCONFIDENCE: Thinking you know more than you do\n"
            "4. GREED & IMPATIENCE: Wanting returns too fast\n"
            "5. HOME BIAS: Over-concentrating in familiar assets\n"
            "6. LOSS AVERSION: Feeling losses 2x more than gains"
        ),
        action_items=[
            "Which of these 6 biases is affecting you RIGHT NOW?",
            "Name it to tame it - awareness reduces impact",
            "Use rules and automation to override these biases",
        ],
        severity="warning",
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


def get_random_self_deception() -> CoachingIntervention:
    """Get a random Arbinger self-deception intervention."""
    return random.choice(SELF_DECEPTION_INTERVENTIONS)


def get_random_focal_point() -> CoachingIntervention:
    """Get a random Brian Tracy Focal Point intervention."""
    return random.choice(FOCAL_POINT_INTERVENTIONS)


def get_random_tony_robbins() -> CoachingIntervention:
    """Get a random Tony Robbins (Money/Unshakeable) intervention."""
    return random.choice(TONY_ROBBINS_INTERVENTIONS)
