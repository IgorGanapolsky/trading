#!/usr/bin/env python3
"""
Telegram Alerting System for Trading Bot

Free, reliable, instant notifications to CEO's phone.
Setup time: 10 minutes | Cost: $0 forever | Reliability: 99.9%+
"""

import os
from datetime import datetime
from typing import Any

import requests


class TelegramAlerter:
    """
    Dead-simple Telegram alerting for trading system failures.

    Setup:
        1. Create bot via @BotFather on Telegram
        2. Get bot token and your chat ID
        3. Set environment variables:
           TELEGRAM_BOT_TOKEN=your_bot_token
           TELEGRAM_CHAT_ID=your_chat_id

    Usage:
        alerter = TelegramAlerter()
        alerter.send_alert("Trading system failed!", level="CRITICAL")
    """

    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")

        if not self.bot_token:
            print("⚠️  TELEGRAM_BOT_TOKEN not configured - alerts disabled")
            self.enabled = False
        elif not self.chat_id:
            print("⚠️  TELEGRAM_CHAT_ID not configured - alerts disabled")
            self.enabled = False
        else:
            self.enabled = True
            self.api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

    def send_alert(self, message: str, level: str = "INFO", include_timestamp: bool = True) -> bool:
        """
        Send alert to CEO via Telegram.

        Args:
            message: Alert message content
            level: Alert severity (INFO, WARNING, ERROR, CRITICAL)
            include_timestamp: Add timestamp to message

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            print(f"Telegram alerts disabled - would have sent: [{level}] {message}")
            return False

        # Map severity to emoji
        emoji_map = {"INFO": "ℹ️", "WARNING": "⚠️", "ERROR": "❌", "CRITICAL": "🚨"}

        emoji = emoji_map.get(level.upper(), "📢")

        # Format message
        timestamp_str = ""
        if include_timestamp:
            timestamp_str = f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}"

        formatted_message = f"{emoji} *{level.upper()}*\n\n{message}{timestamp_str}"

        # Send to Telegram
        try:
            payload = {
                "chat_id": self.chat_id,
                "text": formatted_message,
                "parse_mode": "Markdown",
            }

            response = requests.post(self.api_url, json=payload, timeout=10)
            response.raise_for_status()

            result = response.json()
            if result.get("ok"):
                print(f"✅ Telegram alert sent: [{level}] {message[:50]}...")
                return True
            else:
                print(f"❌ Telegram API returned error: {result}")
                return False

        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to send Telegram alert: {e}")
            return False

    def send_trade_failure(self, error: str, context: dict[str, Any] | None = None) -> bool:
        """
        Send trading-specific failure alert.

        Args:
            error: Error message
            context: Additional context (portfolio value, positions, etc.)

        Returns:
            True if sent successfully
        """
        message = "*TRADING SYSTEM FAILURE*\n\n"
        message += f"Error: {error}\n"

        if context:
            message += "\n*Context:*\n"
            for key, value in context.items():
                message += f"• {key}: {value}\n"

        message += "\n*Action Required:*\n"
        message += "Check logs and system state immediately."

        return self.send_alert(message, level="CRITICAL")

    def send_market_data_failure(self, symbol: str, error: str, attempts: int) -> bool:
        """
        Send market data fetch failure alert.

        Args:
            symbol: Stock symbol that failed
            error: Error message
            attempts: Number of attempts made

        Returns:
            True if sent successfully
        """
        message = (
            f"*MARKET DATA FAILURE*\n\n"
            f"Symbol: {symbol}\n"
            f"Error: {error}\n"
            f"Attempts: {attempts}\n\n"
            f"Trading halted for this symbol."
        )

        return self.send_alert(message, level="CRITICAL")

    def send_no_trades_alert(self, reason: str, day: int, portfolio_value: float) -> bool:
        """
        Send alert when no trades executed.

        Args:
            reason: Why trades were skipped
            day: Current day of 90
            portfolio_value: Current portfolio value

        Returns:
            True if sent successfully
        """
        message = (
            f"*NO TRADES EXECUTED*\n\n"
            f"Day: {day}/90\n"
            f"Portfolio: ${portfolio_value:,.2f}\n"
            f"Reason: {reason}\n\n"
            f"System is operational but no opportunities found."
        )

        return self.send_alert(message, level="WARNING")

    def send_daily_report(self, report: str) -> bool:
        """
        Send daily trading report to CEO.

        Args:
            report: Daily report text (can use Markdown formatting)

        Returns:
            True if sent successfully
        """
        return self.send_alert(report, level="INFO")

    def send_health_alert(self, status: str, failed_checks: list, portfolio_value: float) -> bool:
        """
        Send health check failure alert.

        Args:
            status: Health status (CRITICAL/WARNING)
            failed_checks: List of failed check names
            portfolio_value: Current portfolio value

        Returns:
            True if sent successfully
        """
        message = f"*HEALTH CHECK {status}*\n\nFailed Checks:\n"

        for check in failed_checks:
            message += f"❌ {check}\n"

        message += f"\nPortfolio: ${portfolio_value:,.2f}\n"
        message += "\nReview logs immediately."

        return self.send_alert(message, level=status)

    def send_tlt_gate_status(
        self, gate_opened: bool, sma20: float, sma50: float, current_price: float
    ) -> bool:
        """
        Send TLT momentum gate status change alert.

        Args:
            gate_opened: True if gate just opened, False if closed
            sma20: Current 20-day SMA value
            sma50: Current 50-day SMA value
            current_price: Current TLT price

        Returns:
            True if sent successfully
        """
        emoji = "🟢" if gate_opened else "🔴"
        status = "OPENED" if gate_opened else "CLOSED"
        action = (
            "✅ System will now allocate $90/day to TLT"
            if gate_opened
            else "⏸️  System will skip TLT orders until gate opens"
        )

        message = (
            f"{emoji} *TLT Momentum Gate {status}*\n\n"
            f"Treasuries trading is now {'ENABLED' if gate_opened else 'PAUSED'}.\n\n"
            f"*Current Status:*\n"
            f"• Price: ${current_price:.2f}\n"
            f"• SMA20: ${sma20:.2f}\n"
            f"• SMA50: ${sma50:.2f}\n"
            f"• Gate: {status} (SMA20 {'>=' if gate_opened else '<'} SMA50)\n\n"
            f"*Impact:*\n{action}\n\n"
            f"*Next Check:* Daily at market open"
        )

        return self.send_alert(message, level="INFO" if gate_opened else "WARNING")

    def test_connection(self) -> bool:
        """
        Test Telegram connection with simple ping.

        Returns:
            True if connection works
        """
        if not self.enabled:
            print("❌ Telegram not configured - cannot test")
            return False

        message = (
            "✅ *Telegram Alerting Active*\n\n"
            "Your autonomous trading bot is now monitored.\n"
            "You will receive instant notifications for:\n"
            "• Trade execution failures\n"
            "• Market data issues\n"
            "• Portfolio health problems\n"
            "• System errors\n"
            "• TLT momentum gate changes\n\n"
            "No more silent failures!"
        )

        return self.send_alert(message, level="INFO")


# Example usage and testing
if __name__ == "__main__":
    # Initialize alerter
    alerter = TelegramAlerter()

    # Test connection
    print("Testing Telegram connection...")
    if alerter.test_connection():
        print("✅ Telegram alerts configured successfully!")
    else:
        print("❌ Failed to send test alert")
        print("\nSetup instructions:")
        print("1. Open Telegram and search for @BotFather")
        print("2. Send /newbot and follow instructions")
        print("3. Copy the bot token")
        print("4. Send a message to your bot")
        print("5. Visit: https://api.telegram.org/bot<TOKEN>/getUpdates")
        print("6. Find your chat ID in the JSON response")
        print("7. Add to .env:")
        print("   TELEGRAM_BOT_TOKEN=your_token")
        print("   TELEGRAM_CHAT_ID=your_chat_id")
