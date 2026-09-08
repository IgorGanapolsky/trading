"""
Google Gemini Agent Integration for Trading System

This module provides the foundational components for integrating 
Google Gemini AI agents into our trading system to enhance decision-making,
regime detection, and risk management while maintaining our disciplined approach.
"""

import os
import logging
from typing import Dict, Any, List
from dataclasses import dataclass
from datetime import datetime

import google.generativeai as genai
from google.generativeai.types import GenerationConfig, HarmCategory, HarmBlockThreshold


logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Configuration for Gemini trading agents"""
    api_key: str = os.getenv("GOOGLE_API_KEY", "")
    model_name: str = "gemini-1.5-pro"
    temperature: float = 0.1  # Low temperature for consistent, analytical responses
    max_tokens: int = 2048
    safety_settings: Dict[HarmCategory, HarmBlockThreshold] = None
    
    def __post_init__(self):
        if not self.api_key:
            logger.warning("GOOGLE_API_KEY not set. Gemini agents will not function.")
        
        # Conservative safety settings appropriate for financial applications
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        }


class GeminiTradingAgent:
    """
    Base class for Gemini-powered trading agents.
    
    Maintains our disciplined approach while enhancing capabilities with AI.
    All agent decisions go through our existing risk management and kill switches.
    """
    
    def __init__(self, config: AgentConfig = None):
        self.config = config or AgentConfig()
        
        if self.config.api_key:
            genai.configure(api_key=self.config.api_key)
            self.model = genai.GenerativeModel(
                model_name=self.config.model_name,
                generation_config=GenerationConfig(
                    temperature=self.config.temperature,
                    max_output_tokens=self.config.max_tokens
                ),
                safety_settings=self.config.safety_settings
            )
        else:
            self.model = None
            logger.error("Cannot initialize Gemini model: API key not provided")
    
    def _prepare_market_context(self, market_data: Dict[str, Any]) -> str:
        """Prepare market context for the agent"""
        context_parts = []
        
        # Add current market conditions
        context_parts.append(f"Current timestamp: {datetime.now().isoformat()}")
        
        if 'price' in market_data:
            context_parts.append(f"Current price: ${market_data['price']:.2f}")
        
        if 'iv_rank' in market_data:
            context_parts.append(f"Implied Volatility Rank: {market_data['iv_rank']:.2f}%")
            
        if 'vix' in market_data:
            context_parts.append(f"VIX: {market_data['vix']:.2f}")
            
        if 'spy_above_200dma' in market_data:
            context_parts.append(f"SPY above 200 DMA: {market_data['spy_above_200dma']}")
        
        if 'regime_conditions' in market_data:
            context_parts.append(f"Regime conditions: {market_data['regime_conditions']}")
        
        return "\n".join(context_parts)
    
    def _prepare_system_instruction(self) -> str:
        """Prepare system instruction with our trading principles"""
        return """
        You are an AI assistant for a disciplined trading system. Your role is to analyze market data 
        and provide recommendations within the following constraints:
        
        1. NEVER recommend entering trades when IV rank is below 30%
        2. NEVER recommend trades when VIX is above 30 (extremely high volatility)
        3. ALWAYS consider risk management first
        4. Provide quantitative analysis with specific metrics
        5. Acknowledge limitations and uncertainties
        6. Recommend conservative positions for validation phase
        
        The current system is in paper-only validation mode and must complete at least 30 trades 
        with positive expectancy before considering live trading. Your recommendations should 
        support this validation process while maintaining discipline.
        """
    
    def analyze_regime(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze market regime using Gemini AI
        
        Args:
            market_data: Dictionary containing market conditions
            
        Returns:
            Analysis results with recommendation
        """
        if not self.model:
            logger.error("Gemini model not initialized")
            return {"error": "Gemini model not available"}
        
        try:
            system_instruction = self._prepare_system_instruction()
            market_context = self._prepare_market_context(market_data)
            
            prompt = f"""
            {system_instruction}
            
            Analyze the following market conditions:
            {market_context}
            
            Provide a detailed analysis of:
            1. Current market regime suitability for our SPY put credit strategy
            2. Specific risks and opportunities
            3. Recommendation on whether to enter trades (YES/NO/CONDITIONAL)
            4. Supporting quantitative metrics
            
            Format your response as a structured analysis with clear reasoning.
            """
            
            response = self.model.generate_content(prompt)
            
            return {
                "analysis": response.text,
                "timestamp": datetime.now().isoformat(),
                "model_used": self.config.model_name
            }
            
        except Exception as e:
            logger.error(f"Error in regime analysis: {str(e)}")
            return {"error": str(e)}
    
    def validate_trade_idea(self, trade_idea: Dict[str, Any], market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a potential trade idea using Gemini AI
        
        Args:
            trade_idea: Dictionary containing trade details
            market_data: Current market conditions
            
        Returns:
            Validation results
        """
        if not self.model:
            logger.error("Gemini model not initialized")
            return {"error": "Gemini model not available"}
        
        try:
            system_instruction = self._prepare_system_instruction()
            market_context = self._prepare_market_context(market_data)
            
            prompt = f"""
            {system_instruction}
            
            Evaluate the following potential trade:
            {trade_idea}
            
            Market Conditions:
            {market_context}
            
            Perform a thorough validation including:
            1. Risk-reward assessment
            2. Alignment with current regime
            3. Position sizing appropriateness
            4. Potential issues or concerns
            
            Provide a clear YES/NO/MODIFY recommendation with detailed reasoning.
            """
            
            response = self.model.generate_content(prompt)
            
            return {
                "validation": response.text,
                "timestamp": datetime.now().isoformat(),
                "model_used": self.config.model_name
            }
            
        except Exception as e:
            logger.error(f"Error in trade validation: {str(e)}")
            return {"error": str(e)}


class RegimeDetectionAgent(GeminiTradingAgent):
    """
    Specialized agent for intelligent regime detection.
    Enhances our current regime gate with advanced pattern recognition.
    """
    
    def __init__(self, config: AgentConfig = None):
        super().__init__(config)
        self.name = "RegimeDetectionAgent"
    
    def detect_regime_shift(self, historical_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Detect potential regime shifts using historical data
        
        Args:
            historical_data: List of historical market data points
            
        Returns:
            Regime shift analysis
        """
        if not self.model:
            logger.error("Gemini model not initialized")
            return {"error": "Gemini model not available"}
        
        try:
            # Prepare historical context
            hist_str = "\n".join([
                f"{item.get('date', 'N/A')}: IV={item.get('iv_rank', 'N/A')}, "
                f"VIX={item.get('vix', 'N/A')}, Price={item.get('price', 'N/A')}"
                for item in historical_data[-10:]  # Last 10 data points
            ])
            
            system_instruction = self._prepare_system_instruction()
            
            prompt = f"""
            {system_instruction}
            
            Analyze the following historical market data for potential regime shifts:
            {hist_str}
            
            Identify:
            1. Any emerging trends or patterns
            2. Signs of regime transition
            3. Key inflection points
            4. Probability of regime change in next 5-10 days
            5. Recommended actions based on analysis
            
            Be conservative in your assessment and err on the side of caution.
            """
            
            response = self.model.generate_content(prompt)
            
            return {
                "regime_analysis": response.text,
                "timestamp": datetime.now().isoformat(),
                "model_used": self.config.model_name
            }
            
        except Exception as e:
            logger.error(f"Error in regime shift detection: {str(e)}")
            return {"error": str(e)}


class RiskManagementAgent(GeminiTradingAgent):
    """
    Specialized agent for AI-powered risk management.
    Enhances our current risk controls with intelligent monitoring.
    """
    
    def __init__(self, config: AgentConfig = None):
        super().__init__(config)
        self.name = "RiskManagementAgent"
    
    def assess_portfolio_risk(self, portfolio_data: Dict[str, Any], market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assess portfolio risk using AI analysis
        
        Args:
            portfolio_data: Current portfolio holdings and P&L
            market_data: Current market conditions
            
        Returns:
            Risk assessment
        """
        if not self.model:
            logger.error("Gemini model not initialized")
            return {"error": "Gemini model not available"}
        
        try:
            system_instruction = self._prepare_system_instruction()
            market_context = self._prepare_market_context(market_data)
            
            prompt = f"""
            {system_instruction}
            
            Assess the risk of the following portfolio:
            {portfolio_data}
            
            Current Market Conditions:
            {market_context}
            
            Evaluate:
            1. Current risk exposure
            2. Potential stress scenarios
            3. Correlation risks
            4. Concentration risks
            5. Recommendations for risk mitigation
            
            Remember that the system is in paper validation mode and risk management is paramount.
            """
            
            response = self.model.generate_content(prompt)
            
            return {
                "risk_assessment": response.text,
                "timestamp": datetime.now().isoformat(),
                "model_used": self.config.model_name
            }
            
        except Exception as e:
            logger.error(f"Error in portfolio risk assessment: {str(e)}")
            return {"error": str(e)}


def get_gemini_agent_status() -> Dict[str, Any]:
    """
    Get status of Gemini agent integration
    
    Returns:
        Status information
    """
    api_key_set = bool(os.getenv("GOOGLE_API_KEY"))
    
    return {
        "gemini_integration_enabled": api_key_set,
        "api_key_available": api_key_set,
        "models_available": ["gemini-1.5-pro", "gemini-1.5-flash"] if api_key_set else [],
        "timestamp": datetime.now().isoformat()
    }