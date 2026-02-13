"""
Tests for OpenRouter Price Monitor.

Verifies:
- Price drop detection logic
- Baseline save/load
- Alert threshold behavior
- Graceful failure on API errors
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from scripts.openrouter_price_monitor import (
    PRICE_DROP_THRESHOLD,
    TRACKED_MODELS,
    detect_price_drops,
    fetch_openrouter_prices,
)


class TestDetectPriceDrops:
    """Test price drop detection logic."""

    def test_no_drops_when_prices_same(self):
        """No drops when current equals baseline."""
        baseline = {
            "deepseek/deepseek-r1": {
                "input_cost_per_1m": 0.70,
                "output_cost_per_1m": 2.50,
            }
        }
        current = {
            "deepseek/deepseek-r1": {
                "name": "DeepSeek-R1",
                "input_cost_per_1m": 0.70,
                "output_cost_per_1m": 2.50,
            }
        }
        drops = detect_price_drops(current, baseline)
        assert len(drops) == 0

    def test_detects_input_cost_drop(self):
        """Detects significant input cost drop."""
        baseline = {
            "deepseek/deepseek-r1": {
                "input_cost_per_1m": 0.70,
                "output_cost_per_1m": 2.50,
            }
        }
        current = {
            "deepseek/deepseek-r1": {
                "name": "DeepSeek-R1",
                "input_cost_per_1m": 0.10,  # 85% drop
                "output_cost_per_1m": 2.50,
            }
        }
        drops = detect_price_drops(current, baseline)
        assert len(drops) == 1
        assert drops[0]["model_id"] == "deepseek/deepseek-r1"
        assert drops[0]["input_drop_pct"] > 80

    def test_detects_output_cost_drop(self):
        """Detects significant output cost drop."""
        baseline = {
            "deepseek/deepseek-r1": {
                "input_cost_per_1m": 0.70,
                "output_cost_per_1m": 2.50,
            }
        }
        current = {
            "deepseek/deepseek-r1": {
                "name": "DeepSeek-R1",
                "input_cost_per_1m": 0.70,
                "output_cost_per_1m": 0.30,  # 88% drop
            }
        }
        drops = detect_price_drops(current, baseline)
        assert len(drops) == 1
        assert drops[0]["output_drop_pct"] > 80

    def test_ignores_small_drops(self):
        """Ignores drops below threshold."""
        baseline = {
            "deepseek/deepseek-r1": {
                "input_cost_per_1m": 0.70,
                "output_cost_per_1m": 2.50,
            }
        }
        current = {
            "deepseek/deepseek-r1": {
                "name": "DeepSeek-R1",
                "input_cost_per_1m": 0.60,  # 14% drop — below 30% threshold
                "output_cost_per_1m": 2.30,  # 8% drop
            }
        }
        drops = detect_price_drops(current, baseline)
        assert len(drops) == 0

    def test_ignores_price_increases(self):
        """Price increases are not flagged."""
        baseline = {
            "deepseek/deepseek-r1": {
                "input_cost_per_1m": 0.70,
                "output_cost_per_1m": 2.50,
            }
        }
        current = {
            "deepseek/deepseek-r1": {
                "name": "DeepSeek-R1",
                "input_cost_per_1m": 1.00,  # Increase
                "output_cost_per_1m": 3.00,
            }
        }
        drops = detect_price_drops(current, baseline)
        assert len(drops) == 0

    def test_skips_models_not_in_baseline(self):
        """New models not in baseline are skipped."""
        baseline = {}
        current = {
            "deepseek/deepseek-r1": {
                "name": "DeepSeek-R1",
                "input_cost_per_1m": 0.10,
                "output_cost_per_1m": 0.30,
            }
        }
        drops = detect_price_drops(current, baseline)
        assert len(drops) == 0

    def test_multiple_drops_detected(self):
        """Multiple model drops detected simultaneously."""
        baseline = {
            "deepseek/deepseek-r1": {
                "input_cost_per_1m": 0.70,
                "output_cost_per_1m": 2.50,
            },
            "deepseek/deepseek-chat": {
                "input_cost_per_1m": 0.30,
                "output_cost_per_1m": 1.20,
            },
        }
        current = {
            "deepseek/deepseek-r1": {
                "name": "R1",
                "input_cost_per_1m": 0.09,  # 87% drop
                "output_cost_per_1m": 0.31,
            },
            "deepseek/deepseek-chat": {
                "name": "V3",
                "input_cost_per_1m": 0.04,  # 87% drop
                "output_cost_per_1m": 0.15,
            },
        }
        drops = detect_price_drops(current, baseline)
        assert len(drops) == 2

    def test_zero_baseline_no_division_error(self):
        """Zero baseline price doesn't cause division by zero."""
        baseline = {
            "deepseek/deepseek-r1": {
                "input_cost_per_1m": 0,
                "output_cost_per_1m": 0,
            }
        }
        current = {
            "deepseek/deepseek-r1": {
                "name": "R1",
                "input_cost_per_1m": 0.70,
                "output_cost_per_1m": 2.50,
            }
        }
        drops = detect_price_drops(current, baseline)
        assert len(drops) == 0  # No error, no drop flagged


class TestThreshold:
    """Test that the alert threshold is configured correctly."""

    def test_threshold_is_30_percent(self):
        """Alert threshold is 30% drop."""
        assert PRICE_DROP_THRESHOLD == 0.30

    def test_tracked_models_include_reasoning(self):
        """Reasoning models are tracked."""
        assert "deepseek/deepseek-r1" in TRACKED_MODELS
        assert "deepseek/deepseek-chat" in TRACKED_MODELS


class TestFetchPrices:
    """Test OpenRouter API fetch."""

    def test_fetch_handles_api_error(self):
        """API errors raise exceptions (caller handles)."""
        with patch("scripts.openrouter_price_monitor.urllib.request.urlopen") as mock_url:
            mock_url.side_effect = Exception("Connection timeout")
            with pytest.raises(Exception, match="Connection timeout"):
                fetch_openrouter_prices()

    def test_fetch_parses_response(self):
        """Parses OpenRouter API response correctly."""
        mock_data = {
            "data": [
                {
                    "id": "deepseek/deepseek-r1",
                    "pricing": {
                        "prompt": "0.0000007",  # $0.70 per 1M
                        "completion": "0.0000025",  # $2.50 per 1M
                    },
                },
                {
                    "id": "some/other-model",
                    "pricing": {"prompt": "0.001", "completion": "0.002"},
                },
            ]
        }
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(mock_data).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("scripts.openrouter_price_monitor.urllib.request.urlopen") as mock_url:
            mock_url.return_value = mock_response
            prices = fetch_openrouter_prices()

        assert "deepseek/deepseek-r1" in prices
        assert "some/other-model" not in prices  # Not tracked
        assert prices["deepseek/deepseek-r1"]["input_cost_per_1m"] == 0.7
        assert prices["deepseek/deepseek-r1"]["output_cost_per_1m"] == 2.5
