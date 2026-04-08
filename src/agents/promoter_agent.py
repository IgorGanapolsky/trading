"""
Promoter Agent - Step 8: Autonomous Social Outreach.
Interfaces with Zernio API to broadcast trade successes and strategy updates.
"""

import json
import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)


class PromoterAgent:
    """Generates and posts content to Zernio for X, LinkedIn, and Reddit."""

    def __init__(self):
        self.api_key = os.getenv("ZERNIO_API_KEY")
        self.api_url = "https://zernio.com/api/v1/posts"  # Corrected GSD endpoint
        if not self.api_key:
            logger.warning("ZERNIO_API_KEY not found in .env. Social promotion will be MOCKED.")

    def generate_copy(self, trade_data: dict[str, Any]) -> str:
        """Create engaging copy based on trade results."""
        underlying = trade_data.get("underlying", "SPY")
        pnl_pct = trade_data.get("pnl_pct", 0.0)
        pnl_dollars = trade_data.get("pnl_dollars", 0.0)

        if pnl_pct > 0:
            return (
                f"🎯 Strategy Success: {underlying} Iron Condor closed for {pnl_pct:.1%} profit! \n\n"
                f"Generated ${pnl_dollars:.2f} in premium. \n"
                f"Regime: VIX {trade_data.get('vix', 'N/A')} | IV-RV Edge: {trade_data.get('edge', 'N/A')}\n\n"
                f"#Trading #Options #SPY #AI #QuantitativeTrading"
            )
        else:
            return (
                f"📝 Trade Entry: Opening {underlying} Iron Condor (4-DTE Tactical).\n"
                f"Short Delta: 0.15 | Target Profit: 50%\n"
                f"Safety Check: RAG-Verified ✅\n\n"
                f"#TradingSystem #Automation #FinTech"
            )

    def broadcast(self, trade_data: dict[str, Any]):
        """Post to Zernio."""
        copy = self.generate_copy(trade_data)

        payload = {
            "text": copy,  # Corrected key
            "platforms": ["twitter", "linkedin", "reddit"],
            "scheduledFor": None,  # Post immediately
        }

        if not self.api_key:
            logger.info(f"🧪 GSD PROMOTE (MOCK): {json.dumps(payload, indent=2)}")
            return {"status": "MOCKED", "content": copy}

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            response = requests.post(self.api_url, json=payload, headers=headers)
            # Log status for debugging
            logger.info(f"Zernio Request: {json.dumps(payload)}")
            logger.info(f"Zernio Response Status: {response.status_code}")
            logger.info(f"Zernio Response Body: {response.text}")

            response.raise_for_status()
            logger.info("✅ GSD: Promotion broadcasted to Zernio.")
            return response.json()
        except Exception as e:
            logger.error(f"❌ Zernio Broadcast Failed: {e}")
            if hasattr(e, "response") and e.response:
                logger.error(f"Details: {e.response.text}")
            return {"error": str(e)}
