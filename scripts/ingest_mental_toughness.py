#!/usr/bin/env python3
"""
Ingest Mental Toughness Coach content into RAG vector store.

This script ingests the trading psychology wisdom from:
- Steve Siebold's "177 Mental Toughness Secrets of the World Class"
- FIRE Movement (Financial Independence, Retire Early) principles
- Daniel Kahneman's "Thinking, Fast and Slow" concepts

Usage:
    python scripts/ingest_mental_toughness.py
"""

import logging
import sys
from typing import Any

sys.path.append(".")

from src.rag.vector_db.chroma_client import get_rag_db

logger = logging.getLogger(__name__)


def get_mental_toughness_content() -> list[dict[str, Any]]:
    """
    Extract all mental toughness content for RAG ingestion.

    Returns:
        List of documents with content and metadata
    """
    documents = []

    # ===========================================================================
    # SIEBOLD PRINCIPLES (177 Mental Toughness Secrets)
    # ===========================================================================
    siebold_principles = [
        {
            "id": "siebold_compartmentalize",
            "title": "Compartmentalize Emotions (Siebold #2)",
            "content": """
The world class compartmentalize their emotions. In trading, this means:
- Don't let losses bleed into future trades
- Each trade is independent - it doesn't know about the previous one
- Separate the emotion from the analysis
- After a loss, take 3 deep breaths (physiological reset)
- Log the loss with objective analysis: What went wrong?
- Ask: If I just sat down fresh, would I take the next trade?
The great ones process emotions quickly and move forward with clarity.
            """,
            "source": "siebold_177_secrets",
            "principle_number": 2,
            "category": "emotional_management",
        },
        {
            "id": "siebold_confidence",
            "title": "Supreme Self-Confidence (Siebold #4)",
            "content": """
The great ones possess supreme self-confidence. In trading:
- Trust your system completely
- Each trade is executed with confidence, regardless of recent results
- You are a world-class trader in development
- Confidence comes from preparation, not outcomes
- Your edge is real - the math proves it over time
- Don't let temporary setbacks shake your conviction in the process
Self-confidence isn't arrogance - it's trust in your preparation.
            """,
            "source": "siebold_177_secrets",
            "principle_number": 4,
            "category": "mindset",
        },
        {
            "id": "siebold_metacognition",
            "title": "Embrace Metacognition (Siebold #5)",
            "content": """
The world class embrace metacognition - thinking about their thinking. In trading:
- Before each decision, ask: Am I trading my system or my emotions?
- Question your decisions constantly
- Clarity precedes action
- Monitor your mental state as closely as you monitor the market
- Recognize when your thinking is biased or emotional
- Champions think about their thinking before making decisions
Metacognition is the ultimate competitive advantage.
            """,
            "source": "siebold_177_secrets",
            "principle_number": 5,
            "category": "mindset",
        },
        {
            "id": "siebold_coachable",
            "title": "Champions Are Coachable (Siebold #6)",
            "content": """
The great ones are coachable. In trading:
- Accept feedback and adjust
- Don't let ego prevent learning
- Every loss teaches something - extract the lesson
- Be open to changing your approach when data suggests you should
- The market is the ultimate teacher - listen to it
- Seek mentorship and learn from those ahead of you
Coachability accelerates growth exponentially.
            """,
            "source": "siebold_177_secrets",
            "principle_number": 6,
            "category": "growth",
        },
        {
            "id": "siebold_why_fighting",
            "title": "Know Why You're Fighting (Siebold #7)",
            "content": """
Champions know why they're fighting. In trading:
- Clear purpose: North Star goal of $100+/day through compound engineering
- This isn't about today's P/L - it's about building something
- Each trade moves you toward financial independence
- When motivation wavers, reconnect with your why
- Purpose provides resilience through drawdowns
- You're building a wealth engine, not gambling
Purpose transforms difficult days into meaningful progress.
            """,
            "source": "siebold_177_secrets",
            "principle_number": 7,
            "category": "mindset",
        },
        {
            "id": "siebold_abundance",
            "title": "Operate from Love and Abundance (Siebold #8)",
            "content": """
The world class operate from love and abundance, not fear and scarcity. In trading:
- There are unlimited opportunities in the market
- Don't chase or force trades - they come to you
- Missing one trade means nothing - more are coming
- Trade with confidence, not desperation
- Scarcity thinking leads to bad decisions
- Fear-based trading leads to poor execution and missed opportunities
Abundance mindset is the foundation of consistent performance.
            """,
            "source": "siebold_177_secrets",
            "principle_number": 8,
            "category": "mindset",
        },
        {
            "id": "siebold_school",
            "title": "School Is Never Out (Siebold #10)",
            "content": """
School is never out for the great ones. In trading:
- Every trade, win or loss, teaches something
- Be a perpetual student of the market
- Today's lesson makes tomorrow easier
- Document what you learn in your trading journal
- The market evolves - your knowledge must too
- Compound your learning alongside your capital
Continuous learning is the only sustainable edge.
            """,
            "source": "siebold_177_secrets",
            "principle_number": 10,
            "category": "growth",
        },
        {
            "id": "siebold_bold",
            "title": "The Great Ones Are Bold (Siebold #11)",
            "content": """
The great ones are bold. In trading:
- When your system signals, execute without hesitation
- Boldness is not recklessness - it's confident action based on preparation
- Average performers hesitate; champions act
- Trust your analysis and pull the trigger
- Fortune favors the bold who have done their homework
- Boldness with discipline is the winning combination
Bold action on solid preparation separates winners from spectators.
            """,
            "source": "siebold_177_secrets",
            "principle_number": 11,
            "category": "resilience",
        },
        {
            "id": "siebold_mental_org",
            "title": "Masters of Mental Organization (Siebold #14)",
            "content": """
The great ones are masters of mental organization. In trading:
- Start each session with clear intentions
- Know exactly what setups you're looking for
- Identify 'no-trade' conditions before the market opens
- Set mental stops: at what point do you walk away?
- Mental clarity precedes trading clarity
- Structure your day for peak performance
Organized thinking produces organized results.
            """,
            "source": "siebold_177_secrets",
            "principle_number": 14,
            "category": "emotional_management",
        },
        {
            "id": "siebold_balance",
            "title": "Champions Seek Balance (Siebold #16)",
            "content": """
Champions seek balance. In trading:
- Know when to trade and when to step back
- Balance aggression with patience
- Sometimes the highest-EV action is NOT trading
- Protect your capital AND your psychology
- Balance winning streaks with grounded humility
- Balance losing streaks with resilient confidence
Balance is not moderation - it's optimal allocation of resources.
            """,
            "source": "siebold_177_secrets",
            "principle_number": 16,
            "category": "emotional_management",
        },
        {
            "id": "siebold_suffer",
            "title": "Not Afraid to Suffer (Siebold #18)",
            "content": """
The great ones aren't afraid to suffer. In trading:
- Losses hurt - that's normal and healthy
- Champions use pain as fuel, not poison
- Losses are TUITION for your trading education
- Embrace the suffering - it's building your edge
- Pain is temporary; the lessons are permanent
- What doesn't kill your account makes it stronger
Willingness to suffer separates professionals from amateurs.
            """,
            "source": "siebold_177_secrets",
            "principle_number": 18,
            "category": "resilience",
        },
        {
            "id": "siebold_failure_data",
            "title": "Failure Is Data (Siebold Principle)",
            "content": """
The world class reframe failure as data for iterative improvement. In trading:
- Losses are not defeat - they're information
- Every failed trade tells you something about the market or yourself
- Analyze failures systematically to extract patterns
- Failure is the cost of doing business
- The goal isn't to avoid failure but to learn from it quickly
- Elite achievers use failure as fuel for improvement
Failure is simply data for the next iteration.
            """,
            "source": "siebold_177_secrets",
            "principle_number": 0,
            "category": "resilience",
        },
    ]

    for principle in siebold_principles:
        documents.append(
            {
                "id": principle["id"],
                "content": f"{principle['title']}\n\n{principle['content'].strip()}",
                "metadata": {
                    "source": "mental_toughness_coach",
                    "framework": "siebold_177_secrets",
                    "author": "Steve Siebold",
                    "principle_number": principle["principle_number"],
                    "category": principle["category"],
                    "type": "trading_psychology",
                    "ticker": "PSYCHOLOGY",
                },
            }
        )

    # ===========================================================================
    # FIRE MOVEMENT PRINCIPLES
    # ===========================================================================
    fire_principles = [
        {
            "id": "fire_compound_growth",
            "title": "The Power of Compound Growth (FIRE Principle)",
            "content": """
FIRE PRINCIPLE: Compound growth is your superpower. In trading:
- Today's small P/L is noise - you're building a SYSTEM
- Einstein called compound interest the 8th wonder of the world
- Your edge compounds, your skills compound, your capital compounds
- At 62% win rate with proper position sizing, $1/day becomes $100/day
- Don't judge the harvest while planting seeds
- Each trade is a data point, not a destination
Trust the math: Win rate + edge + time = wealth.
            """,
            "category": "long_term_perspective",
        },
        {
            "id": "fire_delayed_gratification",
            "title": "Delayed Gratification (FIRE Principle)",
            "content": """
FIRE PRINCIPLE: Delayed gratification is the superpower of the wealthy. In trading:
- Average people need instant gratification
- The R&D phase is the ACCUMULATION period
- Every trade teaches the system something
- The payoff comes later, but it comes exponentially
- Focus on execution quality, not daily P/L
- Month 6 target is $100+/day - stay the course
Front-load the work so compound growth does the rest.
            """,
            "category": "long_term_perspective",
        },
        {
            "id": "fire_systems_beat_goals",
            "title": "Systems Beat Goals (FIRE Principle)",
            "content": """
FIRE PRINCIPLE: Goals are for amateurs. SYSTEMS are for professionals. In trading:
- You don't have a 'make money today' goal
- You have a SYSTEM that compounds intelligence daily
- The system is working even when individual trades lose
- Trust the process - the 4% rule works because systems work
- Ask: Is the SYSTEM improving? (Not: Did I profit today?)
- Log what the system learned from each trade
Refine the edge, don't chase the outcome.
            """,
            "category": "long_term_perspective",
        },
        {
            "id": "fire_25x_rule",
            "title": "The FIRE Number (25x Rule)",
            "content": """
FIRE PRINCIPLE: Financial independence = 25x annual expenses. In trading:
- You're not just trading - you're building a wealth engine
- At $100/day (North Star), that's $36,500/year passive income
- 25x = $912,500 equivalent wealth generated
- Each day the system improves, you're building toward that number
- Think in years, not days
- Small daily improvements = massive long-term results
Your future self will thank today's discipline.
            """,
            "category": "long_term_perspective",
        },
        {
            "id": "fire_coastfire",
            "title": "CoastFIRE and Front-Loading Work",
            "content": """
FIRE PRINCIPLE: CoastFIRE means front-loading the hard work. In trading:
- Days 1-90 are the front-loading phase
- The losses NOW are investments in the system
- By Month 6, the system trades FOR you
- This temporary discomfort buys permanent freedom
- Embrace the struggle - it's building your edge
- 90 days of discipline = years of passive income
Document everything for future compound returns.
            """,
            "category": "long_term_perspective",
        },
        {
            "id": "fire_abundance",
            "title": "Abundance Mindset (FIRE Principle)",
            "content": """
FIRE PRINCIPLE: Scarcity thinking leads to bad decisions. In trading:
- The market offers UNLIMITED opportunities every single day
- Missing one trade means nothing
- Revenge trading means everything (bad)
- Operate from abundance: There's always another setup tomorrow
- Let go of 'missed' opportunities - more are coming
- Quality > Quantity in trade selection
Patience is a wealth-building superpower.
            """,
            "category": "long_term_perspective",
        },
    ]

    for principle in fire_principles:
        documents.append(
            {
                "id": principle["id"],
                "content": f"{principle['title']}\n\n{principle['content'].strip()}",
                "metadata": {
                    "source": "mental_toughness_coach",
                    "framework": "fire_movement",
                    "author": "FIRE Movement",
                    "category": principle["category"],
                    "type": "trading_psychology",
                    "ticker": "PSYCHOLOGY",
                },
            }
        )

    # ===========================================================================
    # KAHNEMAN PRINCIPLES (Thinking, Fast and Slow)
    # ===========================================================================
    kahneman_principles = [
        {
            "id": "kahneman_system1_system2",
            "title": "System 1 vs System 2 (Kahneman)",
            "content": """
KAHNEMAN: Your brain has two systems of thinking:
- System 1: Fast, intuitive, emotional (causes trading errors)
- System 2: Slow, deliberate, logical (what we need for trading)

In trading:
- System 1 is great for catching a ball, terrible for trading
- STOP and engage System 2 before every trade decision
- Take 30 seconds, breathe, then ask: Does this trade meet ALL my criteria?
- Verbalize your reasoning out loud (activates System 2)
- Check: Am I trading the SETUP or trading my EMOTIONS?

The rational move often FEELS wrong because System 1 is noisy.
            """,
            "category": "cognitive_science",
        },
        {
            "id": "kahneman_loss_aversion",
            "title": "Loss Aversion (Kahneman)",
            "content": """
KAHNEMAN: Humans feel losses 2x more intensely than equivalent gains.

In trading:
- A $10 loss FEELS like a $20 gain - your brain is lying to you
- This asymmetry causes holding losers too long
- And cutting winners too early (disposition effect)
- The rational move often FEELS wrong
- Ask: Would I enter this position TODAY at this price?
- If NO: Exit. The sunk cost is irrelevant.
- A loss realized is better than a loss compounded

Trust your system, not your feelings.
            """,
            "category": "cognitive_science",
        },
        {
            "id": "kahneman_anchoring",
            "title": "Anchoring Bias (Kahneman)",
            "content": """
KAHNEMAN: You're ANCHORED to reference points (like your entry price).

In trading:
- The market doesn't care what you paid
- Your entry price is IRRELEVANT to where the stock goes next
- Evaluate positions as if you just discovered them today
- Would you buy it NOW at the current price?
- If not, why are you holding?
- Forget your entry price - it's a sunk cost
- The market owes you nothing

Trade what IS, not what WAS.
            """,
            "category": "cognitive_science",
        },
        {
            "id": "kahneman_wysiati",
            "title": "WYSIATI - What You See Is All There Is (Kahneman)",
            "content": """
KAHNEMAN: Your brain builds confident stories from limited data.

'What You See Is All There Is' (WYSIATI) - In trading:
- You're seeing a FRACTION of relevant information
- The chart, the news, your analysis - it's incomplete
- Overconfidence comes from coherent stories, not complete information
- Ask: What am I NOT seeing that could matter?
- Reduce position size when uncertainty is high
- The less you know, the smaller you should bet

Stay humble. Your analysis is always incomplete.
            """,
            "category": "cognitive_science",
        },
        {
            "id": "kahneman_regression",
            "title": "Regression to the Mean (Kahneman)",
            "content": """
KAHNEMAN: Extreme results regress to the mean.

In trading:
- Hot streaks cool off - this isn't mystical, it's mathematics
- Cold streaks warm up
- Your recent performance (good OR bad) is partially luck
- Don't increase risk after wins - regression is coming
- Don't despair after losses - regression is coming
- Stay consistent - the system works over MANY trades

The mean is always coming. Trade accordingly.
            """,
            "category": "cognitive_science",
        },
        {
            "id": "kahneman_planning_fallacy",
            "title": "The Planning Fallacy (Kahneman)",
            "content": """
KAHNEMAN: We systematically underestimate time, costs, and risks.

In trading:
- 'This trade is different' is usually wrong
- Your best prediction is how SIMILAR trades went
- Use base rates, not hopes
- What's your historical win rate on setups like this?
- Size the position based on ACTUAL data, not hope
- Remember: You're not special. Base rates apply to you.

Use outside view (base rates) not inside view (this specific case).
            """,
            "category": "cognitive_science",
        },
        {
            "id": "kahneman_substitution",
            "title": "Substitution Heuristic (Kahneman)",
            "content": """
KAHNEMAN: When faced with a hard question, System 1 secretly substitutes an easier one.

In trading:
- 'Is this a good trade?' becomes 'Do I FEEL good about this trade?'
- Feelings are not analysis
- Force yourself to answer the ACTUAL question
- Write down your ACTUAL criteria for entry
- Check each criterion with Yes/No (no maybes)
- If any criterion is No, the answer is No

Does this meet my documented criteria? Yes or No. Nothing else matters.
            """,
            "category": "cognitive_science",
        },
    ]

    for principle in kahneman_principles:
        documents.append(
            {
                "id": principle["id"],
                "content": f"{principle['title']}\n\n{principle['content'].strip()}",
                "metadata": {
                    "source": "mental_toughness_coach",
                    "framework": "kahneman_thinking_fast_slow",
                    "author": "Daniel Kahneman",
                    "category": principle["category"],
                    "type": "trading_psychology",
                    "ticker": "PSYCHOLOGY",
                },
            }
        )

    return documents


def ingest_mental_toughness() -> dict[str, Any]:
    """
    Ingest all mental toughness content into RAG vector store.

    Returns:
        Dict with ingestion results
    """
    logger.info("=" * 80)
    logger.info("INGESTING MENTAL TOUGHNESS COACH CONTENT INTO RAG")
    logger.info("=" * 80)

    # Get all content
    documents = get_mental_toughness_content()
    logger.info(f"Prepared {len(documents)} psychology documents")

    # Get RAG database
    db = get_rag_db()

    # Prepare for ingestion
    doc_texts = []
    metadatas = []
    ids = []

    for doc in documents:
        doc_texts.append(doc["content"])
        metadatas.append(doc["metadata"])
        ids.append(f"psychology_{doc['id']}")

    # Ingest into RAG
    logger.info("Ingesting into ChromaDB...")
    result = db.add_documents(documents=doc_texts, metadatas=metadatas, ids=ids)

    if result.get("status") == "success":
        logger.info(f"✓ Successfully ingested {len(documents)} documents")
    else:
        logger.error(f"✗ Failed to ingest: {result.get('message', 'Unknown error')}")
        return {"status": "error", "message": result.get("message")}

    # Summary by framework
    siebold_count = sum(1 for d in documents if d["metadata"]["framework"] == "siebold_177_secrets")
    fire_count = sum(1 for d in documents if d["metadata"]["framework"] == "fire_movement")
    kahneman_count = sum(
        1 for d in documents if d["metadata"]["framework"] == "kahneman_thinking_fast_slow"
    )

    logger.info("\n" + "=" * 80)
    logger.info("INGESTION COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Siebold principles: {siebold_count}")
    logger.info(f"FIRE principles: {fire_count}")
    logger.info(f"Kahneman principles: {kahneman_count}")
    logger.info(f"Total documents: {len(documents)}")

    return {
        "status": "success",
        "total_documents": len(documents),
        "breakdown": {
            "siebold": siebold_count,
            "fire": fire_count,
            "kahneman": kahneman_count,
        },
    }


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    result = ingest_mental_toughness()

    if result["status"] == "success":
        logger.info("\n✅ Mental Toughness content successfully ingested into RAG!")
        logger.info("You can now query trading psychology using semantic search.")
    else:
        logger.error(f"\n❌ Ingestion failed: {result.get('message')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
