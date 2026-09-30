# Ah! I STILL have `@patch("src.brokers.multi_broker.TradingClient")`!
# Because my previous file write had exactly that!
# That's why it failed with `AttributeError`!
# Because in `src.brokers.multi_broker.py`, `TradingClient` is imported locally INSIDE `def alpaca(self):`!
# It is NOT an attribute of `src.brokers.multi_broker` module!
# And I ALSO have `@patch("src.safety.mandatory_trade_gate.validate_ticker")`!
# Which caused `AttributeError: module 'src.safety' has no attribute 'mandatory_trade_gate'` during collection IF it failed to import!
# Wait! In `ca9ce56`, I did `pytest.importorskip("src.safety.mandatory_trade_gate")`.
# BUT `@patch` is evaluated during module LOAD!
# Since `pytest.importorskip` skips the test execution, it DOES NOT prevent the module from being LOADED and decorators from being evaluated!
# And when the decorator `@patch("src.safety.mandatory_trade_gate.validate_ticker")` is evaluated, it resolves `src.safety.mandatory_trade_gate.validate_ticker`!
# If `src.safety.mandatory_trade_gate` is NOT imported (because we skipped it, or it failed to import), `patch` fails!
# That is exactly what is happening!
