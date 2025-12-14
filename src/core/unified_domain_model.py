"""
Unified Domain Model (UDM) for Trading System
Inspired by Netflix's Upper Metamodel & UDA Architecture

"Model Once, Represent Everywhere"
- Single authoritative definition for all trading concepts
- Auto-generates schemas for different representations
- Ensures consistency across strategies, data sources, and storage
- Self-validating: Runtime validation inspired by W3C SHACL
- Self-describing: Full introspection and metadata
- Self-referencing: Models the model itself

References:
- Netflix UDA: engineering.fyi/article/model-once-represent-everywhere
- Upper Metamodel: infoq.com/news/2025/12/netflix-upper-uda-architecture
- W3C SHACL: w3.org/TR/shacl/ (validation patterns)
"""

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, fields
from datetime import datetime
from enum import Enum
from typing import Any, Optional, get_type_hints

# =============================================================================
# VALIDATION FRAMEWORK (SHACL-inspired)
# =============================================================================


class ValidationError(Exception):
    """Raised when domain object validation fails"""

    def __init__(self, entity: str, field: str, message: str):
        self.entity = entity
        self.field = field
        self.message = message
        super().__init__(f"{entity}.{field}: {message}")


class ValidationResult:
    """Result of validation with all errors collected"""

    def __init__(self):
        self.errors: list[ValidationError] = []

    def add_error(self, entity: str, field: str, message: str):
        self.errors.append(ValidationError(entity, field, message))

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def raise_if_invalid(self):
        if not self.is_valid:
            raise ValidationError(
                self.errors[0].entity,
                self.errors[0].field,
                "; ".join(e.message for e in self.errors),
            )


class Validator(ABC):
    """Base validator interface (SHACL constraint pattern)"""

    @abstractmethod
    def validate(self, value: Any, field_name: str, entity_name: str) -> Optional[str]:
        """Returns error message if invalid, None if valid"""
        pass


class RangeValidator(Validator):
    """Validates numeric ranges"""

    def __init__(self, min_val: float = None, max_val: float = None):
        self.min_val = min_val
        self.max_val = max_val

    def validate(self, value: Any, field_name: str, entity_name: str) -> Optional[str]:
        if value is None:
            return None
        if self.min_val is not None and value < self.min_val:
            return f"must be >= {self.min_val}, got {value}"
        if self.max_val is not None and value > self.max_val:
            return f"must be <= {self.max_val}, got {value}"
        return None


class PatternValidator(Validator):
    """Validates string patterns (regex)"""

    def __init__(self, pattern: str, description: str = "pattern"):
        self.pattern = re.compile(pattern)
        self.description = description

    def validate(self, value: Any, field_name: str, entity_name: str) -> Optional[str]:
        if value is None:
            return None
        if not self.pattern.match(str(value)):
            return f"must match {self.description}"
        return None


class NotEmptyValidator(Validator):
    """Validates non-empty strings"""

    def validate(self, value: Any, field_name: str, entity_name: str) -> Optional[str]:
        if value is None or (isinstance(value, str) and not value.strip()):
            return "cannot be empty"
        return None


class EnumValidator(Validator):
    """Validates enum membership"""

    def __init__(self, enum_class: type[Enum]):
        self.enum_class = enum_class

    def validate(self, value: Any, field_name: str, entity_name: str) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, self.enum_class):
            return None
        try:
            self.enum_class(value)
            return None
        except ValueError:
            valid_values = [e.value for e in self.enum_class]
            return f"must be one of {valid_values}"


# Validation rules registry (SHACL shapes catalog)
VALIDATION_RULES: dict[str, dict[str, list[Validator]]] = {
    "Symbol": {
        "ticker": [NotEmptyValidator(), PatternValidator(r"^[A-Z0-9/]{1,10}$", "ticker format")],
    },
    "Price": {
        "value": [RangeValidator(min_val=0)],
    },
    "Signal": {
        "confidence": [RangeValidator(min_val=0.0, max_val=1.0)],
        "source": [NotEmptyValidator()],
    },
    "Trade": {
        "id": [NotEmptyValidator()],
        "quantity": [RangeValidator(min_val=0)],
        "notional": [RangeValidator(min_val=0)],
    },
    "Position": {
        "quantity": [RangeValidator(min_val=0)],
        "market_value": [RangeValidator(min_val=0)],
    },
    "Portfolio": {
        "equity": [RangeValidator(min_val=0)],
        "cash": [RangeValidator(min_val=0)],
    },
}


# =============================================================================
# CORE DOMAIN ENUMS (Single Source of Truth)
# =============================================================================


class AssetClass(str, Enum):
    """All supported asset classes"""

    EQUITY = "equity"
    CRYPTO = "crypto"
    OPTION = "option"
    ETF = "etf"
    BOND = "bond"


class TradeAction(str, Enum):
    """Trade action types"""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class OrderStatus(str, Enum):
    """Order status states"""

    PENDING = "pending"
    SUBMITTED = "submitted"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class SignalStrength(str, Enum):
    """Signal confidence levels"""

    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class StrategyTier(str, Enum):
    """Trading strategy tiers"""

    TIER1_SAFE = "tier1_safe"  # Low risk, high probability
    TIER2_MOMENTUM = "tier2_momentum"  # Momentum plays
    TIER3_SWING = "tier3_swing"  # Swing trades
    TIER4_OPTIONS = "tier4_options"  # Options strategies
    TIER5_CRYPTO = "tier5_crypto"  # Crypto trading


class DataSource(str, Enum):
    """Data source identifiers"""

    ALPACA = "alpaca"
    POLYGON = "polygon"
    YFINANCE = "yfinance"
    NEWS_API = "news_api"
    REDDIT = "reddit"
    TWITTER = "twitter"
    GEMINI_RESEARCH = "gemini_research"


# =============================================================================
# CORE DOMAIN MODELS (Netflix Upper Pattern)
# =============================================================================


@dataclass
class Symbol:
    """Unified symbol representation"""

    ticker: str  # e.g., "BTCUSD", "AAPL"
    asset_class: AssetClass
    exchange: Optional[str] = None  # e.g., "NASDAQ", "CRYPTO"
    name: Optional[str] = None  # e.g., "Bitcoin", "Apple Inc."

    def to_alpaca(self) -> str:
        """Project to Alpaca format"""
        if self.asset_class == AssetClass.CRYPTO:
            return self.ticker.replace("/", "")
        return self.ticker

    def to_yfinance(self) -> str:
        """Project to yfinance format"""
        if self.asset_class == AssetClass.CRYPTO:
            return f"{self.ticker[:3]}-USD"
        return self.ticker


@dataclass
class Price:
    """Unified price representation"""

    value: float
    currency: str = "USD"
    timestamp: Optional[datetime] = None
    source: Optional[DataSource] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "currency": self.currency,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "source": self.source.value if self.source else None,
        }


@dataclass
class Signal:
    """Unified trading signal"""

    symbol: Symbol
    action: TradeAction
    strength: SignalStrength
    confidence: float  # 0.0 - 1.0
    source: str  # Strategy or model that generated it
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol.ticker,
            "asset_class": self.symbol.asset_class.value,
            "action": self.action.value,
            "strength": self.strength.value,
            "confidence": self.confidence,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    def is_actionable(self, min_confidence: float = 0.6) -> bool:
        """Check if signal meets minimum confidence threshold"""
        return self.action != TradeAction.HOLD and self.confidence >= min_confidence


@dataclass
class Trade:
    """Unified trade representation (the core domain object)"""

    id: str  # Unique trade ID
    symbol: Symbol
    action: TradeAction
    quantity: float
    price: Price
    notional: float  # Dollar amount
    strategy: StrategyTier
    timestamp: datetime = field(default_factory=datetime.utcnow)
    status: OrderStatus = OrderStatus.PENDING
    order_id: Optional[str] = None  # Broker order ID
    signal: Optional[Signal] = None  # Original signal
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary (for JSON storage)"""
        return {
            "id": self.id,
            "symbol": self.symbol.ticker,
            "asset_class": self.symbol.asset_class.value,
            "action": self.action.value,
            "quantity": self.quantity,
            "price": self.price.value,
            "notional": self.notional,
            "strategy": self.strategy.value,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
            "order_id": self.order_id,
            "metadata": self.metadata,
        }

    def to_alpaca_order(self) -> dict[str, Any]:
        """Project to Alpaca order format"""
        return {
            "symbol": self.symbol.to_alpaca(),
            "side": self.action.value.lower(),
            "type": "market",
            "notional": str(self.notional),
            "time_in_force": "day",
        }

    def to_performance_record(self) -> dict[str, Any]:
        """Project to performance log format"""
        return {
            "date": self.timestamp.strftime("%Y-%m-%d"),
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol.ticker,
            "action": self.action.value,
            "notional": self.notional,
            "price": self.price.value,
            "strategy": self.strategy.value,
            "status": self.status.value,
        }


@dataclass
class Position:
    """Unified position representation"""

    symbol: Symbol
    quantity: float
    avg_entry_price: Price
    current_price: Price
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol.ticker,
            "asset_class": self.symbol.asset_class.value,
            "quantity": self.quantity,
            "avg_entry_price": self.avg_entry_price.value,
            "current_price": self.current_price.value,
            "market_value": self.market_value,
            "unrealized_pnl": self.unrealized_pnl,
            "unrealized_pnl_pct": self.unrealized_pnl_pct,
        }


@dataclass
class Portfolio:
    """Unified portfolio state"""

    equity: float
    cash: float
    buying_power: float
    positions: list[Position] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def total_pnl(self) -> float:
        return sum(p.unrealized_pnl for p in self.positions)

    @property
    def position_count(self) -> int:
        return len(self.positions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "equity": self.equity,
            "cash": self.cash,
            "buying_power": self.buying_power,
            "total_pnl": self.total_pnl,
            "position_count": self.position_count,
            "positions": [p.to_dict() for p in self.positions],
            "timestamp": self.timestamp.isoformat(),
        }


# =============================================================================
# RELATIONSHIP MODELING (Entity Graph - Netflix Upper Pattern)
# =============================================================================


class RelationType(str, Enum):
    """Types of relationships between entities"""

    GENERATES = "generates"  # Signal generates Trade
    AFFECTS = "affects"  # Trade affects Position
    BELONGS_TO = "belongs_to"  # Position belongs to Portfolio
    REFERENCES = "references"  # Trade references Signal
    CONTAINS = "contains"  # Portfolio contains Position
    DERIVES_FROM = "derives_from"  # Price derives from DataSource


@dataclass
class Relationship:
    """Represents a relationship between two entity types"""

    source_type: str
    relation: RelationType
    target_type: str
    cardinality: str = "one_to_one"  # one_to_one, one_to_many, many_to_many
    description: str = ""


class DomainGraph:
    """
    Entity relationship graph (Netflix Upper's semantic layer).
    Models how domain concepts relate to each other.
    """

    # Define all relationships in the trading domain
    RELATIONSHIPS: list[Relationship] = [
        Relationship(
            "Signal",
            RelationType.GENERATES,
            "Trade",
            "one_to_one",
            "A signal generates a trade decision",
        ),
        Relationship(
            "Trade",
            RelationType.REFERENCES,
            "Signal",
            "one_to_one",
            "A trade references its originating signal",
        ),
        Relationship(
            "Trade",
            RelationType.AFFECTS,
            "Position",
            "many_to_one",
            "Multiple trades affect a single position",
        ),
        Relationship(
            "Position",
            RelationType.BELONGS_TO,
            "Portfolio",
            "many_to_one",
            "Multiple positions belong to one portfolio",
        ),
        Relationship(
            "Portfolio",
            RelationType.CONTAINS,
            "Position",
            "one_to_many",
            "A portfolio contains multiple positions",
        ),
        Relationship(
            "Price",
            RelationType.DERIVES_FROM,
            "DataSource",
            "many_to_one",
            "Prices derive from data sources",
        ),
        Relationship(
            "Symbol",
            RelationType.BELONGS_TO,
            "AssetClass",
            "many_to_one",
            "Symbols belong to asset classes",
        ),
    ]

    @classmethod
    def get_relationships_for(cls, entity_type: str) -> list[Relationship]:
        """Get all relationships where entity is source or target"""
        return [
            r
            for r in cls.RELATIONSHIPS
            if r.source_type == entity_type or r.target_type == entity_type
        ]

    @classmethod
    def get_outgoing(cls, entity_type: str) -> list[Relationship]:
        """Get relationships where entity is the source"""
        return [r for r in cls.RELATIONSHIPS if r.source_type == entity_type]

    @classmethod
    def get_incoming(cls, entity_type: str) -> list[Relationship]:
        """Get relationships where entity is the target"""
        return [r for r in cls.RELATIONSHIPS if r.target_type == entity_type]

    @classmethod
    def to_mermaid(cls) -> str:
        """Generate Mermaid diagram of the domain graph"""
        lines = ["graph LR"]
        for r in cls.RELATIONSHIPS:
            lines.append(f"    {r.source_type} -->|{r.relation.value}| {r.target_type}")
        return "\n".join(lines)

    @classmethod
    def to_dict(cls) -> dict[str, Any]:
        """Export domain graph as dictionary"""
        return {
            "entities": ["Symbol", "Price", "Signal", "Trade", "Position", "Portfolio"],
            "relationships": [
                {
                    "source": r.source_type,
                    "relation": r.relation.value,
                    "target": r.target_type,
                    "cardinality": r.cardinality,
                }
                for r in cls.RELATIONSHIPS
            ],
        }


# =============================================================================
# SCHEMA GENERATOR (Model Once, Represent Everywhere)
# =============================================================================

# Python type to JSON Schema type mapping
PYTHON_TO_JSON_SCHEMA: dict[str, str] = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
    "datetime": "string",
    "list": "array",
    "dict": "object",
    "List": "array",
    "Dict": "object",
    "Optional": None,  # Handled specially
}

# Python type to Avro type mapping
PYTHON_TO_AVRO: dict[str, str] = {
    "str": "string",
    "int": "long",
    "float": "double",
    "bool": "boolean",
    "datetime": {"type": "long", "logicalType": "timestamp-millis"},
}

# Python type to SQL type mapping
PYTHON_TO_SQL: dict[str, str] = {
    "str": "VARCHAR(255)",
    "int": "INTEGER",
    "float": "DECIMAL(18, 8)",
    "bool": "BOOLEAN",
    "datetime": "TIMESTAMP",
}


class SchemaGenerator:
    """
    Generates consistent schemas from domain models.
    Netflix's "Upper" pattern - single source generates all representations.

    Supports:
    - JSON Schema (for API validation)
    - Avro (for Kafka/streaming)
    - SQL DDL (for PostgreSQL)
    - GraphQL (for API layer)
    """

    @staticmethod
    def _get_python_type_name(type_hint) -> str:
        """Extract type name from type hint"""
        type_str = str(type_hint)
        # Handle Optional[X] -> X
        if "Optional" in type_str:
            inner = type_str.replace("typing.Optional[", "").replace("]", "")
            return inner.split(".")[-1]
        # Handle List[X], Dict[X, Y]
        if "[" in type_str:
            return type_str.split("[")[0].split(".")[-1]
        return type_str.split(".")[-1]

    @classmethod
    def to_json_schema(cls, model_class) -> dict[str, Any]:
        """Generate JSON Schema from dataclass"""
        properties = {}
        required = []

        try:
            hints = get_type_hints(model_class)
        except Exception:
            hints = {}

        for f in fields(model_class):
            field_type = hints.get(f.name, f.type)
            type_name = cls._get_python_type_name(field_type)

            # Map to JSON Schema type
            json_type = PYTHON_TO_JSON_SCHEMA.get(type_name, "object")

            # Check if field is required (no default)
            is_optional = "Optional" in str(field_type)

            if json_type == "string" and type_name == "datetime":
                properties[f.name] = {"type": "string", "format": "date-time"}
            elif json_type:
                properties[f.name] = {"type": json_type}
            else:
                properties[f.name] = {"type": "object"}

            if not is_optional and f.default is f.default_factory is type(None):
                required.append(f.name)

        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "title": model_class.__name__,
            "description": (model_class.__doc__ or "").strip(),
            "properties": properties,
            "required": required if required else None,
        }

    @classmethod
    def to_avro_schema(cls, model_class) -> dict[str, Any]:
        """Generate Avro schema for Kafka/streaming"""
        avro_fields = []

        try:
            hints = get_type_hints(model_class)
        except Exception:
            hints = {}

        for f in fields(model_class):
            field_type = hints.get(f.name, f.type)
            type_name = cls._get_python_type_name(field_type)

            # Map to Avro type
            avro_type = PYTHON_TO_AVRO.get(type_name, "string")
            is_optional = "Optional" in str(field_type)

            if is_optional:
                avro_type = ["null", avro_type]

            avro_fields.append(
                {
                    "name": f.name,
                    "type": avro_type,
                }
            )

        return {
            "type": "record",
            "name": model_class.__name__,
            "namespace": "com.trading.domain",
            "doc": (model_class.__doc__ or "").strip(),
            "fields": avro_fields,
        }

    @classmethod
    def to_sql_ddl(cls, model_class, dialect: str = "postgresql") -> str:
        """Generate SQL DDL for database tables"""
        table_name = model_class.__name__.lower()
        columns = []

        try:
            hints = get_type_hints(model_class)
        except Exception:
            hints = {}

        for f in fields(model_class):
            field_type = hints.get(f.name, f.type)
            type_name = cls._get_python_type_name(field_type)

            # Map to SQL type
            sql_type = PYTHON_TO_SQL.get(type_name, "TEXT")
            is_optional = "Optional" in str(field_type)

            nullable = "NULL" if is_optional else "NOT NULL"

            # Special handling for ID fields
            if f.name == "id":
                columns.append(f"    {f.name} VARCHAR(64) PRIMARY KEY")
            else:
                columns.append(f"    {f.name} {sql_type} {nullable}")

        ddl = f"CREATE TABLE {table_name} (\n"
        ddl += ",\n".join(columns)
        ddl += "\n);"

        return ddl

    @classmethod
    def to_graphql_type(cls, model_class) -> str:
        """Generate GraphQL type definition"""
        type_name = model_class.__name__

        gql_type_map = {
            "str": "String",
            "int": "Int",
            "float": "Float",
            "bool": "Boolean",
            "datetime": "DateTime",
        }

        gql_fields = []

        try:
            hints = get_type_hints(model_class)
        except Exception:
            hints = {}

        for f in fields(model_class):
            field_type = hints.get(f.name, f.type)
            type_name_str = cls._get_python_type_name(field_type)

            gql_type = gql_type_map.get(type_name_str, "String")
            is_optional = "Optional" in str(field_type)

            if not is_optional:
                gql_type += "!"

            gql_fields.append(f"  {f.name}: {gql_type}")

        return f"type {type_name} {{\n" + "\n".join(gql_fields) + "\n}"

    @classmethod
    def generate_all(cls, model_class) -> dict[str, Any]:
        """Generate all schema representations at once"""
        return {
            "json_schema": cls.to_json_schema(model_class),
            "avro": cls.to_avro_schema(model_class),
            "sql_ddl": cls.to_sql_ddl(model_class),
            "graphql": cls.to_graphql_type(model_class),
        }


# =============================================================================
# DOMAIN VALIDATOR (SHACL-style validation)
# =============================================================================


class DomainValidator:
    """
    Validates domain objects against SHACL-inspired rules.
    Netflix Upper uses SHACL for constraint validation.
    """

    @classmethod
    def validate(cls, obj: Any) -> ValidationResult:
        """Validate a domain object against its rules"""
        result = ValidationResult()
        entity_name = obj.__class__.__name__

        rules = VALIDATION_RULES.get(entity_name, {})

        for field_name, validators in rules.items():
            value = getattr(obj, field_name, None)
            for validator in validators:
                error = validator.validate(value, field_name, entity_name)
                if error:
                    result.add_error(entity_name, field_name, error)

        return result

    @classmethod
    def validate_or_raise(cls, obj: Any) -> None:
        """Validate and raise exception if invalid"""
        result = cls.validate(obj)
        result.raise_if_invalid()

    @classmethod
    def is_valid(cls, obj: Any) -> bool:
        """Quick check if object is valid"""
        return cls.validate(obj).is_valid


# =============================================================================
# DOMAIN FACTORY (Consistent Object Creation)
# =============================================================================


class DomainFactory:
    """
    Factory for creating domain objects with validation.
    Ensures all objects conform to unified model.
    """

    @staticmethod
    def create_crypto_symbol(ticker: str) -> Symbol:
        """Create a crypto symbol"""
        return Symbol(ticker=ticker, asset_class=AssetClass.CRYPTO, exchange="CRYPTO")

    @staticmethod
    def create_equity_symbol(ticker: str, exchange: str = "NASDAQ") -> Symbol:
        """Create an equity symbol"""
        return Symbol(ticker=ticker, asset_class=AssetClass.EQUITY, exchange=exchange)

    @staticmethod
    def create_trade_from_alpaca(alpaca_order: dict, strategy: StrategyTier) -> Trade:
        """Create Trade from Alpaca order response"""
        symbol_str = alpaca_order.get("symbol", "")
        is_crypto = "USD" in symbol_str and len(symbol_str) > 4

        symbol = Symbol(
            ticker=symbol_str, asset_class=AssetClass.CRYPTO if is_crypto else AssetClass.EQUITY
        )

        return Trade(
            id=alpaca_order.get("id", ""),
            symbol=symbol,
            action=TradeAction(alpaca_order.get("side", "buy").upper()),
            quantity=float(alpaca_order.get("qty", 0)),
            price=Price(value=float(alpaca_order.get("filled_avg_price", 0))),
            notional=float(alpaca_order.get("notional", 0)),
            strategy=strategy,
            status=OrderStatus.FILLED
            if alpaca_order.get("status") == "filled"
            else OrderStatus.PENDING,
            order_id=alpaca_order.get("id"),
        )

    @staticmethod
    def create_signal(
        symbol: Symbol, action: TradeAction, confidence: float, source: str
    ) -> Signal:
        """Create a trading signal"""
        if confidence >= 0.8:
            strength = (
                SignalStrength.STRONG_BUY
                if action == TradeAction.BUY
                else SignalStrength.STRONG_SELL
            )
        elif confidence >= 0.6:
            strength = SignalStrength.BUY if action == TradeAction.BUY else SignalStrength.SELL
        else:
            strength = SignalStrength.HOLD

        return Signal(
            symbol=symbol, action=action, strength=strength, confidence=confidence, source=source
        )


# Singleton factory instance
factory = DomainFactory()


if __name__ == "__main__":
    # Test the unified domain model
    print("=" * 60)
    print("UNIFIED DOMAIN MODEL TEST (Netflix Upper Pattern)")
    print("=" * 60)

    # 1. Create domain objects
    print("\n[1] DOMAIN OBJECTS")
    print("-" * 40)

    btc = factory.create_crypto_symbol("BTCUSD")
    print(f"Symbol: {btc.ticker}")
    print(f"  Alpaca format: {btc.to_alpaca()}")
    print(f"  yfinance format: {btc.to_yfinance()}")

    signal = factory.create_signal(
        symbol=btc, action=TradeAction.BUY, confidence=0.85, source="text_analyzer"
    )
    print(f"\nSignal: {signal.action.value}")
    print(f"  Strength: {signal.strength.value}")
    print(f"  Actionable: {signal.is_actionable()}")

    trade = Trade(
        id="trade_001",
        symbol=btc,
        action=TradeAction.BUY,
        quantity=0.00011,
        price=Price(value=90125.56),
        notional=10.0,
        strategy=StrategyTier.TIER5_CRYPTO,
        signal=signal,
    )
    print(f"\nTrade: {trade.id} - {trade.action.value} {trade.symbol.ticker}")

    # 2. Test SHACL-style validation
    print("\n[2] VALIDATION (SHACL-style)")
    print("-" * 40)

    # Valid object
    result = DomainValidator.validate(trade)
    print(f"Trade validation: {'PASS' if result.is_valid else 'FAIL'}")

    # Invalid object (negative notional)
    bad_trade = Trade(
        id="",  # Empty ID - should fail
        symbol=btc,
        action=TradeAction.BUY,
        quantity=-1,  # Negative - should fail
        price=Price(value=90125.56),
        notional=-10.0,  # Negative - should fail
        strategy=StrategyTier.TIER5_CRYPTO,
    )
    result = DomainValidator.validate(bad_trade)
    print(f"Bad trade validation: {'PASS' if result.is_valid else 'FAIL'}")
    for error in result.errors:
        print(f"  - {error.field}: {error.message}")

    # 3. Test relationship modeling
    print("\n[3] RELATIONSHIP GRAPH (Upper Pattern)")
    print("-" * 40)

    print("Trade relationships:")
    for rel in DomainGraph.get_relationships_for("Trade"):
        print(f"  {rel.source_type} --{rel.relation.value}--> {rel.target_type}")

    print("\nMermaid diagram:")
    print(DomainGraph.to_mermaid())

    # 4. Test schema generation
    print("\n[4] SCHEMA GENERATION (Model Once, Represent Everywhere)")
    print("-" * 40)

    print("\n--- JSON Schema ---")
    json_schema = SchemaGenerator.to_json_schema(Trade)
    print(json.dumps(json_schema, indent=2)[:500] + "...")

    print("\n--- SQL DDL ---")
    print(SchemaGenerator.to_sql_ddl(Trade))

    print("\n--- GraphQL Type ---")
    print(SchemaGenerator.to_graphql_type(Trade))

    print("\n--- Avro Schema ---")
    avro = SchemaGenerator.to_avro_schema(Trade)
    print(json.dumps(avro, indent=2)[:400] + "...")

    # 5. Projections
    print("\n[5] PROJECTIONS (Single Source, Multiple Formats)")
    print("-" * 40)
    print(f"Alpaca Order: {json.dumps(trade.to_alpaca_order(), indent=2)}")
    print(f"Performance Record: {json.dumps(trade.to_performance_record(), indent=2)}")

    print("\n" + "=" * 60)
    print("All tests completed successfully!")
    print("=" * 60)
