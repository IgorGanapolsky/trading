---
layout: post
title: "LL-028: Netflix Upper Metamodel - Unified Domain Model"
date: 2025-12-30
---

# LL-028: Netflix Upper Metamodel - Unified Domain Model

**ID**: LL-028

**Date**: 2025-12-13 (Updated)
**Severity**: HIGH
**Category**: Architecture
**Impact**: System-wide consistency, reduced bugs, easier integration

## Executive Summary

Implemented Netflix's full "Upper Metamodel" pattern for our trading system. Now includes:
- **SHACL-style validation** - Runtime constraint checking
- **Relationship modeling** - Entity graph with explicit relationships
- **Full schema generation** - JSON Schema, Avro, SQL DDL, GraphQL from single source

## The Problem (Spider-Man Problem)

Before: Each component had its own definition of core concepts:
- `crypto_strategy.py` had one Trade format
- `autonomous_trader.py` had another
- `system_state.json` had a third
- `trades_*.json` had yet another

This caused:
- Inconsistent data across systems
- Bugs from format mismatches
- Difficult integrations
- Code duplication

## The Solution (Model Once, Represent Everywhere)

Created `src/core/unified_domain_model.py` with:

### 1. Core Domain Objects
- `Symbol` - Unified symbol representation (projects to Alpaca, yfinance formats)
- `Signal` - Trading signals with confidence and strength
- `Trade` - Core trade object with projections to all formats
- `Position` - Portfolio positions
- `Portfolio` - Account state

### 2. SHACL-Style Validation (NEW)
```python
# Validate domain objects at runtime
result = DomainValidator.validate(trade)
if not result.is_valid:
    for error in result.errors:
        print(f"{error.field}: {error.message}")

# Or raise immediately
DomainValidator.validate_or_raise(trade)
```

Validators include:
- `RangeValidator` - Min/max numeric bounds
- `PatternValidator` - Regex patterns
- `NotEmptyValidator` - Required fields
- `EnumValidator` - Valid enum values

### 3. Relationship Graph (NEW)
```python
# Query entity relationships
DomainGraph.get_relationships_for("Trade")
# Returns: Signal→generates→Trade, Trade→affects→Position

# Generate Mermaid diagram
print(DomainGraph.to_mermaid())
# graph LR
#     Signal -->|generates| Trade
#     Trade -->|affects| Position
#     Position -->|belongs_to| Portfolio
```

### 4. Schema Generation (ENHANCED)
```python
# Generate all representations from single source
schemas = SchemaGenerator.generate_all(Trade)

schemas["json_schema"]  # JSON Schema for API validation
schemas["avro"]         # Avro for Kafka/streaming
schemas["sql_ddl"]      # SQL for PostgreSQL
schemas["graphql"]      # GraphQL type definitions
```

### 5. Projections (Original)
```python
trade = Trade(...)
trade.to_alpaca_order()       # Broker format
trade.to_dict()               # JSON storage
trade.to_performance_record() # Analytics
```

## Benefits

1. **Consistency** - Single definition for all concepts
2. **Validation** - Catch invalid data before it causes bugs
3. **Discoverability** - Entity graph shows how concepts relate
4. **Interoperability** - Auto-generate schemas for any system
5. **Self-documenting** - Mermaid diagrams from code

## Netflix Upper Principles Applied

| Netflix Principle | Our Implementation |
|------------------|-------------------|
| Self-validating | `DomainValidator` + SHACL-style rules |
| Self-describing | `DomainGraph` + relationship metadata |
| Model once | Single dataclass definitions |
| Represent everywhere | `SchemaGenerator.generate_all()` |
| Federation support | Relationship cardinality tracking |

## Sources

- [Netflix UDA - Engineering.fyi](https://engineering.fyi/article/model-once-represent-everywhere)
- [InfoQ: Netflix Upper Metamodel](https://www.infoq.com/news/2025/12/netflix-upper-uda-architecture)
- [W3C SHACL](https://www.w3.org/TR/shacl/) (validation patterns)

## Files

- Implementation: `src/core/unified_domain_model.py` (915 lines)
- Tests: `tests/test_unified_domain_model.py` (32 tests)
- Skill: `.claude/skills/unified_domain_model/SKILL.md`

## Tags

#architecture #netflix #domain-model #consistency #upper-metamodel #validation #shacl

