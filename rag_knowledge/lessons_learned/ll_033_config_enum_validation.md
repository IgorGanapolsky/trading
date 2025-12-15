# Lesson Learned: Config Enum Validation

**ID**: LL_033
**Date**: 2025-12-14
**Severity**: HIGH
**Category**: Configuration
**Tags**: enum, validation, config, pre-commit, schema

## Incident Summary

The `config/strategy_registry.json` contained an invalid enum value `"commodity"` for the `asset_class` field. The valid values defined in `src/strategies/registry.py` are: `equity`, `options`, `crypto`, `mixed`. This caused the strategy registry to fail loading with a warning that was silently ignored.

## Root Cause

1. JSON config files are not validated against Python enum definitions
2. Manual edits to config files bypass type checking
3. No pre-commit hook to validate enum values in configs
4. Warning was logged but didn't fail the build

## Impact

- Strategy registry logged warning on every import
- Precious metals strategy was not properly registered
- Silent failure mode - system appeared to work but was degraded

## Prevention Measures

### 1. Schema Validation Test (Automated)
```python
# tests/test_config_schema_validation.py
def test_strategy_registry_asset_classes():
    """Validate all asset_class values match AssetClass enum."""
    from src.strategies.registry import AssetClass
    valid_values = {e.value for e in AssetClass}

    with open("config/strategy_registry.json") as f:
        data = json.load(f)

    for name, strategy in data.get("strategies", {}).items():
        asset_class = strategy.get("asset_class")
        assert asset_class in valid_values, \
            f"Strategy '{name}' has invalid asset_class: {asset_class}"
```

### 2. Pre-commit Hook
Add to `.pre-commit-config.yaml`:
```yaml
- id: validate-config-enums
  name: Validate Config Enum Values
  entry: python3 scripts/validate_config_enums.py
  language: system
  files: '\.json$'
  pass_filenames: false
```

### 3. RAG Query Pattern
When editing config files, always query RAG:
- "What are valid values for [field_name] in [config_file]?"
- "Show me the enum definition for AssetClass"

## Detection Method

This bug was found during a codebase audit when import tests revealed the warning:
```
WARNING - Failed to load strategy registry: 'commodity' is not a valid AssetClass
```

## Fix Applied

Changed `config/strategy_registry.json` line 220:
```diff
- "asset_class": "commodity",
+ "asset_class": "equity",
```

Note: GLD/SLV are equity ETFs that track commodities, not actual commodity futures.

## Related Lessons

- LL_009: CI syntax validation
- LL_024: Trading script syntax validation

## Verification Query

To check for similar issues in the future:
```bash
grep -r "enum" src/ --include="*.py" | grep "class.*Enum"
```
Then verify all config files use only valid enum values.
