"""
Tests for Google Gemini AI Agent Integration

These tests verify that the Gemini agents integrate properly with our 
trading system while maintaining our disciplined approach to risk management.
"""

import unittest
import os
from unittest.mock import patch

from src.ai.gemini_agent import (
    AgentConfig,
    GeminiTradingAgent,
    RegimeDetectionAgent,
    RiskManagementAgent,
    get_gemini_agent_status
)
from config.gemini_agent_config import validate_config


class TestAgentConfig(unittest.TestCase):
    """Test Agent Configuration"""
    
    def test_default_config(self):
        """Test default agent configuration"""
        config = AgentConfig()
        
        # Should have default model
        self.assertEqual(config.model_name, "gemini-1.5-pro")
        
        # Temperature should be low for consistency
        self.assertEqual(config.temperature, 0.1)
        
        # Should have safety settings
        self.assertIsNotNone(config.safety_settings)
    
    @patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"})
    def test_api_key_config(self):
        """Test API key configuration"""
        config = AgentConfig()
        self.assertEqual(config.api_key, "test-key")


class TestGeminiTradingAgent(unittest.TestCase):
    """Test Base Trading Agent"""
    
    def setUp(self):
        # Create a config without API key to avoid actual API calls
        self.config = AgentConfig()
        self.config.api_key = ""
        self.agent = GeminiTradingAgent(self.config)
    
    def test_initialization_without_api_key(self):
        """Test agent initialization without API key"""
        self.assertIsNone(self.agent.model)
    
    def test_prepare_market_context(self):
        """Test market context preparation"""
        market_data = {
            "price": 767.78,
            "iv_rank": 13.2,
            "vix": 15.30,
            "spy_above_200dma": True
        }
        
        context = self.agent._prepare_market_context(market_data)
        
        self.assertIn("Current price: $767.78", context)
        self.assertIn("Implied Volatility Rank: 13.20%", context)
        self.assertIn("VIX: 15.30", context)
        self.assertIn("SPY above 200 DMA: True", context)
    
    def test_prepare_system_instruction(self):
        """Test system instruction preparation"""
        instruction = self.agent._prepare_system_instruction()
        
        self.assertIn("NEVER recommend entering trades when IV rank is below 30%", instruction)
        self.assertIn("NEVER recommend trades when VIX is above 30", instruction)
        self.assertIn("ALWAYS consider risk management first", instruction)
    
    @patch.object(GeminiTradingAgent, '_prepare_system_instruction')
    @patch.object(GeminiTradingAgent, '_prepare_market_context')
    def test_analyze_regime_without_model(self, mock_context, mock_instruction):
        """Test regime analysis without model"""
        mock_context.return_value = "test context"
        mock_instruction.return_value = "test instruction"
        
        result = self.agent.analyze_regime({"price": 100})
        
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Gemini model not available")


class TestRegimeDetectionAgent(unittest.TestCase):
    """Test Regime Detection Agent"""
    
    def setUp(self):
        config = AgentConfig()
        config.api_key = ""
        self.agent = RegimeDetectionAgent(config)
    
    def test_agent_name(self):
        """Test agent name"""
        self.assertEqual(self.agent.name, "RegimeDetectionAgent")
    
    @patch.object(GeminiTradingAgent, '_prepare_system_instruction')
    def test_detect_regime_shift_without_model(self, mock_instruction):
        """Test regime shift detection without model"""
        mock_instruction.return_value = "test instruction"
        
        historical_data = [
            {"date": "2023-01-01", "iv_rank": 20, "vix": 15, "price": 100},
            {"date": "2023-01-02", "iv_rank": 25, "vix": 16, "price": 101}
        ]
        
        result = self.agent.detect_regime_shift(historical_data)
        
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Gemini model not available")


class TestRiskManagementAgent(unittest.TestCase):
    """Test Risk Management Agent"""
    
    def setUp(self):
        config = AgentConfig()
        config.api_key = ""
        self.agent = RiskManagementAgent(config)
    
    def test_agent_name(self):
        """Test agent name"""
        self.assertEqual(self.agent.name, "RiskManagementAgent")
    
    @patch.object(GeminiTradingAgent, '_prepare_system_instruction')
    def test_assess_portfolio_risk_without_model(self, mock_instruction):
        """Test portfolio risk assessment without model"""
        mock_instruction.return_value = "test instruction"
        
        portfolio_data = {"positions": [], "equity": 10000}
        market_data = {"price": 100, "iv_rank": 20}
        
        result = self.agent.assess_portfolio_risk(portfolio_data, market_data)
        
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Gemini model not available")


class TestUtilityFunctions(unittest.TestCase):
    """Test Utility Functions"""
    
    @patch.dict(os.environ, {}, clear=True)
    def test_get_gemini_agent_status_no_key(self):
        """Test agent status without API key"""
        status = get_gemini_agent_status()
        
        self.assertFalse(status["gemini_integration_enabled"])
        self.assertFalse(status["api_key_available"])
        self.assertEqual(status["models_available"], [])
        self.assertIsInstance(status["timestamp"], str)
    
    @patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"})
    def test_get_gemini_agent_status_with_key(self):
        """Test agent status with API key"""
        status = get_gemini_agent_status()
        
        self.assertTrue(status["gemini_integration_enabled"])
        self.assertTrue(status["api_key_available"])
        self.assertIsInstance(status["timestamp"], str)
    
    def test_validate_config(self):
        """Test config validation"""
        result = validate_config()
        
        self.assertIsInstance(result, dict)
        self.assertIn("all_valid", result)
        self.assertIn("api_key_set", result)
        self.assertIn("model_name_valid", result)


class TestIntegrationWithExistingSystem(unittest.TestCase):
    """Test integration with existing trading system principles"""
    
    def test_respects_kill_switch_principle(self):
        """Test that agents respect the kill switch principle"""
        config = AgentConfig()
        config.api_key = ""
        agent = GeminiTradingAgent(config)
        
        # Even if an AI agent was functional, it should respect our discipline
        instruction = agent._prepare_system_instruction()
        
        # Should include our key discipline requirements
        self.assertIn("NEVER recommend entering trades when IV rank is below 30%", instruction)
        self.assertIn("The current system is in paper-only validation mode", instruction)
        self.assertIn("before considering live trading", instruction)
    
    def test_paper_only_enforcement(self):
        """Test paper-only mode enforcement in instructions"""
        config = AgentConfig()
        config.api_key = ""
        agent = GeminiTradingAgent(config)
        
        instruction = agent._prepare_system_instruction()
        
        # Should emphasize paper-only validation
        self.assertIn("paper-only validation mode", instruction)
        self.assertIn("30 trades with positive expectancy", instruction)
        self.assertIn("before considering live trading", instruction)


if __name__ == "__main__":
    print("Running Gemini Agent Integration Tests...")
    print()
    
    # Run tests
    unittest.main(verbosity=2)