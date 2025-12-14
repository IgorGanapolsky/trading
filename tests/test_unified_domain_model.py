"""
Tests for Unified Domain Model (Netflix Upper Pattern)

Tests cover:
1. Domain object creation and projections
2. SHACL-style validation
3. Relationship graph queries
4. Schema generation (JSON, SQL, Avro, GraphQL)
"""

try:
    import pytest

    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False

    # Mock pytest.raises for running without pytest
    class MockPytest:
        @staticmethod
        def raises(exc_type):
            class RaisesContext:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type_actual, exc_val, exc_tb):
                    if exc_val is not None:
                        return True  # Suppress the exception
                    raise AssertionError(f"Expected {exc_type} to be raised")

            return RaisesContext()

    pytest = MockPytest()

import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.unified_domain_model import (
    # Enums
    AssetClass,
    DataSource,
    DomainGraph,
    DomainValidator,
    NotEmptyValidator,
    OrderStatus,
    PatternValidator,
    Portfolio,
    Position,
    Price,
    RangeValidator,
    # Relationships
    RelationType,
    # Schema generation
    SchemaGenerator,
    Signal,
    SignalStrength,
    StrategyTier,
    # Domain objects
    Symbol,
    Trade,
    TradeAction,
    # Validation
    ValidationError,
    # Factory
    factory,
)


class TestDomainObjects:
    """Test core domain object creation and projections"""

    def test_symbol_crypto_projection(self):
        symbol = Symbol(ticker="BTCUSD", asset_class=AssetClass.CRYPTO)
        assert symbol.to_alpaca() == "BTCUSD"
        assert symbol.to_yfinance() == "BTC-USD"

    def test_symbol_equity_projection(self):
        symbol = Symbol(ticker="AAPL", asset_class=AssetClass.EQUITY, exchange="NASDAQ")
        assert symbol.to_alpaca() == "AAPL"
        assert symbol.to_yfinance() == "AAPL"

    def test_price_to_dict(self):
        price = Price(value=100.50, currency="USD", source=DataSource.ALPACA)
        d = price.to_dict()
        assert d["value"] == 100.50
        assert d["currency"] == "USD"
        assert d["source"] == "alpaca"

    def test_signal_actionable(self):
        symbol = Symbol(ticker="BTCUSD", asset_class=AssetClass.CRYPTO)
        signal = Signal(
            symbol=symbol,
            action=TradeAction.BUY,
            strength=SignalStrength.STRONG_BUY,
            confidence=0.85,
            source="test",
        )
        assert signal.is_actionable() is True
        assert signal.is_actionable(min_confidence=0.9) is False

    def test_signal_hold_not_actionable(self):
        symbol = Symbol(ticker="BTCUSD", asset_class=AssetClass.CRYPTO)
        signal = Signal(
            symbol=symbol,
            action=TradeAction.HOLD,
            strength=SignalStrength.HOLD,
            confidence=0.95,
            source="test",
        )
        assert signal.is_actionable() is False

    def test_trade_to_alpaca_order(self):
        symbol = Symbol(ticker="BTCUSD", asset_class=AssetClass.CRYPTO)
        trade = Trade(
            id="test_001",
            symbol=symbol,
            action=TradeAction.BUY,
            quantity=0.001,
            price=Price(value=90000.0),
            notional=25.0,
            strategy=StrategyTier.TIER5_CRYPTO,
        )
        order = trade.to_alpaca_order()
        assert order["symbol"] == "BTCUSD"
        assert order["side"] == "buy"
        assert order["notional"] == "25.0"
        assert order["type"] == "market"

    def test_trade_to_performance_record(self):
        symbol = Symbol(ticker="AAPL", asset_class=AssetClass.EQUITY)
        trade = Trade(
            id="test_002",
            symbol=symbol,
            action=TradeAction.SELL,
            quantity=10,
            price=Price(value=150.0),
            notional=1500.0,
            strategy=StrategyTier.TIER1_SAFE,
        )
        record = trade.to_performance_record()
        assert record["symbol"] == "AAPL"
        assert record["action"] == "SELL"
        assert record["strategy"] == "tier1_safe"

    def test_portfolio_total_pnl(self):
        positions = [
            Position(
                symbol=Symbol(ticker="AAPL", asset_class=AssetClass.EQUITY),
                quantity=10,
                avg_entry_price=Price(value=150.0),
                current_price=Price(value=160.0),
                market_value=1600.0,
                unrealized_pnl=100.0,
                unrealized_pnl_pct=6.67,
            ),
            Position(
                symbol=Symbol(ticker="GOOGL", asset_class=AssetClass.EQUITY),
                quantity=5,
                avg_entry_price=Price(value=140.0),
                current_price=Price(value=135.0),
                market_value=675.0,
                unrealized_pnl=-25.0,
                unrealized_pnl_pct=-3.57,
            ),
        ]
        portfolio = Portfolio(
            equity=100000.0, cash=97725.0, buying_power=195450.0, positions=positions
        )
        assert portfolio.total_pnl == 75.0  # 100 - 25
        assert portfolio.position_count == 2


class TestValidation:
    """Test SHACL-style validation"""

    def test_range_validator_valid(self):
        v = RangeValidator(min_val=0, max_val=1)
        assert v.validate(0.5, "test", "Test") is None
        assert v.validate(0, "test", "Test") is None
        assert v.validate(1, "test", "Test") is None

    def test_range_validator_invalid(self):
        v = RangeValidator(min_val=0, max_val=1)
        assert v.validate(-0.1, "test", "Test") is not None
        assert v.validate(1.5, "test", "Test") is not None

    def test_pattern_validator_valid(self):
        v = PatternValidator(r"^[A-Z]{2,4}$", "ticker")
        assert v.validate("AAPL", "test", "Test") is None
        assert v.validate("BTC", "test", "Test") is None

    def test_pattern_validator_invalid(self):
        v = PatternValidator(r"^[A-Z]{2,4}$", "ticker")
        assert v.validate("aapl", "test", "Test") is not None
        assert v.validate("TOOLONG", "test", "Test") is not None

    def test_not_empty_validator(self):
        v = NotEmptyValidator()
        assert v.validate("hello", "test", "Test") is None
        assert v.validate("", "test", "Test") is not None
        assert v.validate(None, "test", "Test") is not None

    def test_domain_validator_valid_trade(self):
        symbol = Symbol(ticker="BTCUSD", asset_class=AssetClass.CRYPTO)
        trade = Trade(
            id="test_001",
            symbol=symbol,
            action=TradeAction.BUY,
            quantity=1.0,
            price=Price(value=90000.0),
            notional=100.0,
            strategy=StrategyTier.TIER5_CRYPTO,
        )
        assert DomainValidator.is_valid(trade) is True

    def test_domain_validator_invalid_trade(self):
        symbol = Symbol(ticker="BTCUSD", asset_class=AssetClass.CRYPTO)
        trade = Trade(
            id="",  # Empty
            symbol=symbol,
            action=TradeAction.BUY,
            quantity=-1,  # Negative
            price=Price(value=90000.0),
            notional=-100.0,  # Negative
            strategy=StrategyTier.TIER5_CRYPTO,
        )
        result = DomainValidator.validate(trade)
        assert result.is_valid is False
        assert len(result.errors) == 3

    def test_domain_validator_raise(self):
        symbol = Symbol(ticker="BTCUSD", asset_class=AssetClass.CRYPTO)
        trade = Trade(
            id="",
            symbol=symbol,
            action=TradeAction.BUY,
            quantity=1,
            price=Price(value=90000.0),
            notional=100.0,
            strategy=StrategyTier.TIER5_CRYPTO,
        )
        with pytest.raises(ValidationError):
            DomainValidator.validate_or_raise(trade)


class TestRelationshipGraph:
    """Test entity relationship modeling"""

    def test_get_trade_relationships(self):
        rels = DomainGraph.get_relationships_for("Trade")
        assert len(rels) == 3  # generates, references, affects

    def test_get_outgoing_relationships(self):
        rels = DomainGraph.get_outgoing("Signal")
        assert len(rels) == 1
        assert rels[0].relation == RelationType.GENERATES
        assert rels[0].target_type == "Trade"

    def test_get_incoming_relationships(self):
        rels = DomainGraph.get_incoming("Portfolio")
        assert len(rels) == 1
        assert rels[0].source_type == "Position"

    def test_mermaid_diagram(self):
        diagram = DomainGraph.to_mermaid()
        assert "graph LR" in diagram
        assert "Signal -->|generates| Trade" in diagram

    def test_to_dict(self):
        d = DomainGraph.to_dict()
        assert "entities" in d
        assert "relationships" in d
        assert "Trade" in d["entities"]


class TestSchemaGenerator:
    """Test schema generation (Model Once, Represent Everywhere)"""

    def test_json_schema_generation(self):
        schema = SchemaGenerator.to_json_schema(Trade)
        assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"
        assert schema["type"] == "object"
        assert schema["title"] == "Trade"
        assert "properties" in schema

    def test_avro_schema_generation(self):
        schema = SchemaGenerator.to_avro_schema(Trade)
        assert schema["type"] == "record"
        assert schema["name"] == "Trade"
        assert schema["namespace"] == "com.trading.domain"
        assert "fields" in schema

    def test_sql_ddl_generation(self):
        ddl = SchemaGenerator.to_sql_ddl(Trade)
        assert "CREATE TABLE trade" in ddl
        assert "id VARCHAR(64) PRIMARY KEY" in ddl

    def test_graphql_type_generation(self):
        gql = SchemaGenerator.to_graphql_type(Trade)
        assert "type Trade {" in gql
        assert "id:" in gql

    def test_generate_all(self):
        schemas = SchemaGenerator.generate_all(Trade)
        assert "json_schema" in schemas
        assert "avro" in schemas
        assert "sql_ddl" in schemas
        assert "graphql" in schemas


class TestDomainFactory:
    """Test factory methods"""

    def test_create_crypto_symbol(self):
        symbol = factory.create_crypto_symbol("ETHUSD")
        assert symbol.ticker == "ETHUSD"
        assert symbol.asset_class == AssetClass.CRYPTO
        assert symbol.exchange == "CRYPTO"

    def test_create_equity_symbol(self):
        symbol = factory.create_equity_symbol("MSFT", "NYSE")
        assert symbol.ticker == "MSFT"
        assert symbol.asset_class == AssetClass.EQUITY
        assert symbol.exchange == "NYSE"

    def test_create_signal_strong_buy(self):
        symbol = factory.create_crypto_symbol("BTCUSD")
        signal = factory.create_signal(symbol, TradeAction.BUY, 0.9, "test")
        assert signal.strength == SignalStrength.STRONG_BUY

    def test_create_signal_regular_sell(self):
        symbol = factory.create_crypto_symbol("BTCUSD")
        signal = factory.create_signal(symbol, TradeAction.SELL, 0.7, "test")
        assert signal.strength == SignalStrength.SELL

    def test_create_signal_hold(self):
        symbol = factory.create_crypto_symbol("BTCUSD")
        signal = factory.create_signal(symbol, TradeAction.BUY, 0.4, "test")
        assert signal.strength == SignalStrength.HOLD

    def test_create_trade_from_alpaca(self):
        alpaca_response = {
            "id": "abc123",
            "symbol": "BTCUSD",
            "side": "buy",
            "qty": "0.001",
            "filled_avg_price": "90000.00",
            "notional": "90.00",
            "status": "filled",
        }
        trade = factory.create_trade_from_alpaca(alpaca_response, StrategyTier.TIER5_CRYPTO)
        assert trade.id == "abc123"
        assert trade.symbol.asset_class == AssetClass.CRYPTO
        assert trade.status == OrderStatus.FILLED


if __name__ == "__main__":
    if HAS_PYTEST:
        pytest.main([__file__, "-v"])
    else:
        # Run tests manually
        print("Running tests without pytest...")
        print()

        # TestDomainObjects
        t = TestDomainObjects()
        t.test_symbol_crypto_projection()
        t.test_symbol_equity_projection()
        t.test_price_to_dict()
        t.test_signal_actionable()
        t.test_signal_hold_not_actionable()
        t.test_trade_to_alpaca_order()
        t.test_trade_to_performance_record()
        t.test_portfolio_total_pnl()
        print("✓ TestDomainObjects: 8 tests passed")

        # TestValidation
        v = TestValidation()
        v.test_range_validator_valid()
        v.test_range_validator_invalid()
        v.test_pattern_validator_valid()
        v.test_pattern_validator_invalid()
        v.test_not_empty_validator()
        v.test_domain_validator_valid_trade()
        v.test_domain_validator_invalid_trade()
        v.test_domain_validator_raise()
        print("✓ TestValidation: 8 tests passed")

        # TestRelationshipGraph
        r = TestRelationshipGraph()
        r.test_get_trade_relationships()
        r.test_get_outgoing_relationships()
        r.test_get_incoming_relationships()
        r.test_mermaid_diagram()
        r.test_to_dict()
        print("✓ TestRelationshipGraph: 5 tests passed")

        # TestSchemaGenerator
        s = TestSchemaGenerator()
        s.test_json_schema_generation()
        s.test_avro_schema_generation()
        s.test_sql_ddl_generation()
        s.test_graphql_type_generation()
        s.test_generate_all()
        print("✓ TestSchemaGenerator: 5 tests passed")

        # TestDomainFactory
        f = TestDomainFactory()
        f.test_create_crypto_symbol()
        f.test_create_equity_symbol()
        f.test_create_signal_strong_buy()
        f.test_create_signal_regular_sell()
        f.test_create_signal_hold()
        f.test_create_trade_from_alpaca()
        print("✓ TestDomainFactory: 6 tests passed")

        print()
        print("=" * 50)
        print("ALL 32 TESTS PASSED!")
        print("=" * 50)
