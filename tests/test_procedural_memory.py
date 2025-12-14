"""Tests for Procedural Memory module."""

import tempfile
from pathlib import Path

import pytest
from src.memory.procedural_memory import (
    MarketRegime,
    ProceduralMemory,
    SkillAction,
    SkillConditions,
    SkillLibrary,
    SkillOutcome,
    SkillType,
    TradingSkill,
)


class TestSkillConditions:
    """Test skill condition matching."""

    def test_exact_match(self):
        """Test exact condition matching."""
        conditions = SkillConditions(
            rsi_range=(25, 35),
            trend="up",
            volume_condition="high",
        )

        context = {"rsi": 30, "trend": "up", "volume": "high"}
        matches, score = conditions.matches(context)

        assert matches is True
        assert score == 1.0  # All conditions match

    def test_partial_match(self):
        """Test partial condition matching."""
        conditions = SkillConditions(
            rsi_range=(25, 35),
            trend="up",
            volume_condition="high",
        )

        context = {"rsi": 30, "trend": "up", "volume": "low"}
        matches, score = conditions.matches(context)

        assert matches is True  # 2/3 match
        assert 0.6 < score < 0.7

    def test_no_match(self):
        """Test no match."""
        conditions = SkillConditions(
            rsi_range=(25, 35),
            trend="up",
        )

        context = {"rsi": 80, "trend": "down"}
        matches, score = conditions.matches(context)

        assert matches is False
        assert score == 0.0

    def test_regime_match(self):
        """Test market regime matching."""
        conditions = SkillConditions(
            regime=MarketRegime.TRENDING_UP,
        )

        context = {"regime": "trending_up"}
        matches, score = conditions.matches(context)

        assert matches is True

    def test_custom_conditions(self):
        """Test custom condition matching."""
        conditions = SkillConditions(
            custom={"sector": "tech", "market_cap": "large"},
        )

        context = {"sector": "tech", "market_cap": "large"}
        matches, score = conditions.matches(context)

        assert matches is True
        assert score == 1.0


class TestSkillOutcome:
    """Test skill outcome tracking."""

    def test_update_win(self):
        """Test updating with a winning trade."""
        outcome = SkillOutcome()

        outcome.update(profit_pct=5.0, duration_minutes=30)

        assert outcome.uses == 1
        assert outcome.wins == 1
        assert outcome.losses == 0
        assert outcome.total_profit_pct == 5.0
        assert outcome.avg_profit_pct == 5.0

    def test_update_loss(self):
        """Test updating with a losing trade."""
        outcome = SkillOutcome()

        outcome.update(profit_pct=-2.0, duration_minutes=15)

        assert outcome.uses == 1
        assert outcome.wins == 0
        assert outcome.losses == 1
        assert outcome.total_profit_pct == -2.0

    def test_multiple_updates(self):
        """Test multiple outcome updates."""
        outcome = SkillOutcome()

        outcome.update(profit_pct=3.0, duration_minutes=60)
        outcome.update(profit_pct=2.0, duration_minutes=45)
        outcome.update(profit_pct=-1.0, duration_minutes=30)

        assert outcome.uses == 3
        assert outcome.wins == 2
        assert outcome.losses == 1
        assert outcome.avg_profit_pct == pytest.approx(4.0 / 3, rel=0.01)

    def test_confidence_increases(self):
        """Test that confidence increases with successful uses."""
        outcome = SkillOutcome(confidence=0.5)

        for _ in range(10):
            outcome.update(profit_pct=2.0, duration_minutes=60)

        assert outcome.confidence > 0.5


class TestTradingSkill:
    """Test trading skill creation and matching."""

    def test_skill_creation(self):
        """Test creating a skill."""
        skill = TradingSkill(
            name="Test Skill",
            skill_type=SkillType.ENTRY,
            conditions=SkillConditions(rsi_range=(20, 40)),
            action=SkillAction(action_type="buy"),
        )

        assert skill.name == "Test Skill"
        assert skill.skill_type == SkillType.ENTRY
        assert skill.skill_id is not None

    def test_skill_serialization(self):
        """Test skill to_dict and from_dict."""
        skill = TradingSkill(
            name="Test Skill",
            skill_type=SkillType.ENTRY,
            conditions=SkillConditions(
                rsi_range=(20, 40),
                trend="up",
                regime=MarketRegime.TRENDING_UP,
            ),
            action=SkillAction(
                action_type="buy",
                stop_loss_pct=-2.0,
            ),
            outcome=SkillOutcome(uses=5, wins=3),
        )

        data = skill.to_dict()
        restored = TradingSkill.from_dict(data)

        assert restored.name == skill.name
        assert restored.skill_type == skill.skill_type
        assert restored.conditions.trend == skill.conditions.trend
        assert restored.action.stop_loss_pct == skill.action.stop_loss_pct
        assert restored.outcome.uses == skill.outcome.uses

    def test_embedding_text(self):
        """Test embedding text generation."""
        skill = TradingSkill(
            name="RSI Bounce",
            skill_type=SkillType.ENTRY,
            description="Buy on RSI oversold",
            conditions=SkillConditions(trend="up"),
            action=SkillAction(action_type="buy"),
        )

        text = skill.get_embedding_text()

        assert "RSI Bounce" in text
        assert "entry" in text
        assert "buy" in text


class TestSkillLibrary:
    """Test skill library functionality."""

    def test_add_and_get_skill(self):
        """Test adding and retrieving a skill."""
        with tempfile.TemporaryDirectory() as tmpdir:
            library = SkillLibrary(storage_path=Path(tmpdir))

            skill = TradingSkill(
                name="Test Skill",
                skill_type=SkillType.ENTRY,
            )

            skill_id = library.add_skill(skill)
            retrieved = library.get_skill(skill_id)

            assert retrieved is not None
            assert retrieved.name == "Test Skill"

    def test_retrieve_skills(self):
        """Test retrieving skills by context."""
        with tempfile.TemporaryDirectory() as tmpdir:
            library = SkillLibrary(storage_path=Path(tmpdir))

            # Add skills
            skill1 = TradingSkill(
                name="Uptrend Entry",
                skill_type=SkillType.ENTRY,
                conditions=SkillConditions(trend="up", rsi_range=(30, 50)),
                outcome=SkillOutcome(confidence=0.7),
            )
            skill2 = TradingSkill(
                name="Downtrend Entry",
                skill_type=SkillType.ENTRY,
                conditions=SkillConditions(trend="down", rsi_range=(60, 80)),
                outcome=SkillOutcome(confidence=0.6),
            )

            library.add_skill(skill1)
            library.add_skill(skill2)

            # Retrieve for uptrend context
            context = {"trend": "up", "rsi": 40}
            skills = library.retrieve_skills(context, skill_type=SkillType.ENTRY)

            assert len(skills) > 0
            assert skills[0][0].name == "Uptrend Entry"

    def test_extract_skill_from_trade(self):
        """Test extracting a skill from a trade record."""
        with tempfile.TemporaryDirectory() as tmpdir:
            library = SkillLibrary(storage_path=Path(tmpdir))

            trade_record = {
                "trade_id": "test123",
                "symbol": "BTCUSD",
                "action": "buy",
                "profit_pct": 3.5,
                "rsi": 28,
                "trend": "up",
                "volume": "high",
                "duration_minutes": 45,
            }

            skill = library.extract_skill_from_trade(trade_record)

            assert skill is not None
            assert skill.outcome.wins == 1
            assert skill.conditions.trend == "up"
            assert "BTCUSD" in skill.tags

    def test_skill_merging(self):
        """Test that similar skills are merged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            library = SkillLibrary(storage_path=Path(tmpdir))

            trade1 = {
                "trade_id": "t1",
                "symbol": "BTCUSD",
                "action": "buy",
                "profit_pct": 2.0,
                "rsi": 30,
                "trend": "up",
            }
            trade2 = {
                "trade_id": "t2",
                "symbol": "ETHUSD",
                "action": "buy",
                "profit_pct": 3.0,
                "rsi": 32,
                "trend": "up",
            }

            skill1 = library.extract_skill_from_trade(trade1)
            skill2 = library.extract_skill_from_trade(trade2)

            # Should be merged (same conditions)
            assert skill1.skill_id == skill2.skill_id
            assert skill1.outcome.uses == 2

    def test_get_best_skills(self):
        """Test getting best performing skills."""
        with tempfile.TemporaryDirectory() as tmpdir:
            library = SkillLibrary(storage_path=Path(tmpdir))

            # Add skills with different performance
            good_skill = TradingSkill(
                name="Good Skill",
                skill_type=SkillType.ENTRY,
                outcome=SkillOutcome(
                    uses=10,
                    wins=8,
                    expected_win_rate=0.8,
                    avg_profit_pct=3.0,
                    confidence=0.7,
                ),
            )
            bad_skill = TradingSkill(
                name="Bad Skill",
                skill_type=SkillType.ENTRY,
                outcome=SkillOutcome(
                    uses=10,
                    wins=3,
                    expected_win_rate=0.3,
                    avg_profit_pct=-1.0,
                    confidence=0.4,
                ),
            )

            library.add_skill(good_skill)
            library.add_skill(bad_skill)

            best = library.get_best_skills(min_uses=5)

            assert len(best) == 2
            assert best[0].name == "Good Skill"

    def test_deactivate_skill(self):
        """Test deactivating a skill."""
        with tempfile.TemporaryDirectory() as tmpdir:
            library = SkillLibrary(storage_path=Path(tmpdir))

            skill = TradingSkill(name="Test Skill")
            library.add_skill(skill)

            library.deactivate_skill(skill.skill_id, reason="poor performance")

            assert library.get_skill(skill.skill_id).active is False

    def test_skill_report(self):
        """Test generating skill report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            library = SkillLibrary(storage_path=Path(tmpdir))

            library.add_skill(
                TradingSkill(
                    name="Entry Skill",
                    skill_type=SkillType.ENTRY,
                    outcome=SkillOutcome(uses=5, wins=3),
                )
            )
            library.add_skill(
                TradingSkill(
                    name="Exit Skill",
                    skill_type=SkillType.EXIT,
                    outcome=SkillOutcome(uses=3, wins=2),
                )
            )

            report = library.get_skill_report()

            assert "ENTRY SKILLS" in report
            assert "EXIT SKILLS" in report
            assert "Entry Skill" in report


class TestProceduralMemory:
    """Test high-level procedural memory interface."""

    def test_learn_from_trade(self):
        """Test learning from a trade."""
        with tempfile.TemporaryDirectory() as tmpdir:
            library = SkillLibrary(storage_path=Path(tmpdir))
            memory = ProceduralMemory(library=library)

            trade = {
                "trade_id": "test",
                "symbol": "BTCUSD",
                "action": "buy",
                "profit_pct": 2.5,
                "rsi": 35,
                "trend": "up",
            }

            skill = memory.learn_from_trade(trade)

            assert skill is not None

    def test_suggest_action(self):
        """Test action suggestion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            library = SkillLibrary(storage_path=Path(tmpdir))
            memory = ProceduralMemory(library=library)

            # Add a skill first
            skill = TradingSkill(
                name="Buy Low RSI",
                skill_type=SkillType.ENTRY,
                conditions=SkillConditions(rsi_range=(20, 40), trend="up"),
                action=SkillAction(action_type="buy", stop_loss_pct=-2.0),
                outcome=SkillOutcome(confidence=0.7),
            )
            library.add_skill(skill)

            # Get suggestion
            context = {"rsi": 30, "trend": "up"}
            suggestion = memory.suggest_action(context, skill_type=SkillType.ENTRY)

            assert suggestion is not None
            skill, action, confidence = suggestion
            assert action.action_type == "buy"

    def test_skill_use_tracking(self):
        """Test tracking skill use and outcomes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            library = SkillLibrary(storage_path=Path(tmpdir))
            memory = ProceduralMemory(library=library)

            skill = TradingSkill(
                name="Test Skill",
                outcome=SkillOutcome(uses=0),
            )
            library.add_skill(skill)

            # Record use
            memory.record_skill_use(skill.skill_id, "trade123")

            # Record outcome
            memory.record_trade_outcome("trade123", profit_pct=2.0, duration_minutes=60)

            # Check skill was updated
            updated = library.get_skill(skill.skill_id)
            assert updated.outcome.uses == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
