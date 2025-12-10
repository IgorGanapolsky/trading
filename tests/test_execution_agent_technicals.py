import unittest
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
from src.agents.execution_agent import ExecutionAgent
from src.utils.market_data import DataSource, MarketDataResult


class TestExecutionAgentTechnicals(unittest.TestCase):
    def setUp(self):
        self.agent = ExecutionAgent()
        # Mock the LLM to avoid API calls
        self.agent.reason_with_llm = MagicMock(
            return_value={
                "reasoning": "TIMING: IMMEDIATE\nSLIPPAGE: 0.05%\nCONFIDENCE: 0.9\nRECOMMENDATION: EXECUTE"
            }
        )
        # Mock Alpaca API
        self.agent.alpaca_api = MagicMock()
        self.agent.alpaca_api.get_clock.return_value.is_open = True

    @patch("src.agents.execution_agent.MarketDataProvider")
    def test_analyze_with_technicals(self, MockMarketDataProvider):
        # Setup mock data provider
        mock_provider = MockMarketDataProvider.return_value
        self.agent.data_provider = mock_provider

        # Create sample historical data (60 days)
        dates = pd.date_range(end=pd.Timestamp.now(), periods=60)
        # Create a trend for MACD/RSI
        close_prices = np.linspace(100, 150, 60) + np.random.normal(0, 1, 60)
        data = pd.DataFrame(
            {
                "Close": close_prices,
                "Open": close_prices,
                "High": close_prices + 1,
                "Low": close_prices - 1,
                "Volume": 1000000,
            },
            index=dates,
        )

        mock_result = MarketDataResult(data=data, source=DataSource.CACHE)
        mock_provider.get_daily_bars.return_value = mock_result

        # Test input
        input_data = {
            "action": "BUY",
            "symbol": "AAPL",
            "position_size": 1000,
            "market_conditions": {"spread": "0.01", "volume": "High", "volatility": "Low"},
        }

        # Run analyze
        result = self.agent.analyze(input_data)

        # Verify data provider was called
        mock_provider.get_daily_bars.assert_called_with("AAPL", lookback_days=60)

        # Verify LLM was called with prompt containing technicals
        call_args = self.agent.reason_with_llm.call_args
        prompt = call_args[0][0]

        print("\nGenerated Prompt:")
        print(prompt)

        self.assertIn("TECHNICALS:", prompt)
        self.assertIn("MACD Hist", prompt)
        self.assertIn("RSI", prompt)
        self.assertIn("RSI > 70", prompt)  # Check for principles

        # Verify result structure
        self.assertEqual(result["action"], "EXECUTE")
        self.assertEqual(result["timing"], "IMMEDIATE")


if __name__ == "__main__":
    unittest.main()
