"""Trade Verifier - Screenshot-based trade verification for audit trails.

Uses Playwright MCP to verify trades by:
- Logging into broker portal (Alpaca)
- Capturing position screenshots
- Verifying order execution
- Creating audit trail documentation

This provides visual verification independent of API responses.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from src.integrations.playwright_mcp.client import (
    PlaywrightMCPClient,
    get_playwright_client,
)

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """Result of a trade verification."""

    verified: bool
    order_id: str
    symbol: str
    expected_qty: float
    actual_qty: float | None
    expected_side: str
    screenshot_path: Path | None
    verification_time: datetime
    details: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


@dataclass
class PositionSnapshot:
    """Snapshot of current positions from broker portal."""

    positions: list[dict]
    account_equity: float | None
    buying_power: float | None
    screenshot_path: Path | None
    capture_time: datetime
    source: str = "alpaca_web"


@dataclass
class AuditTrailEntry:
    """Entry in the trade audit trail."""

    timestamp: datetime
    action: str
    order_id: str | None
    symbol: str | None
    details: dict
    screenshot_path: Path | None
    api_response: dict | None = None
    web_verification: VerificationResult | None = None


class TradeVerifier:
    """Verifies trades through broker web portal using Playwright MCP.

    Provides independent verification of trade execution by:
    1. Navigating to broker portal
    2. Capturing position/order screenshots
    3. Comparing web data with API responses
    4. Creating audit trail documentation
    """

    # Alpaca dashboard URLs
    ALPACA_URLS = {
        "login": "https://app.alpaca.markets/login",
        "dashboard": "https://app.alpaca.markets/dashboard",
        "paper_dashboard": "https://app.alpaca.markets/paper/dashboard/overview",
        "positions": "https://app.alpaca.markets/paper/dashboard/positions",
        "orders": "https://app.alpaca.markets/paper/dashboard/orders",
        "account": "https://app.alpaca.markets/paper/dashboard/account",
    }

    def __init__(
        self,
        client: PlaywrightMCPClient | None = None,
        audit_dir: str | None = None,
        paper_trading: bool = True,
    ):
        """Initialize the trade verifier.

        Args:
            client: Playwright MCP client (creates new if None)
            audit_dir: Directory for audit trail files
            paper_trading: Whether to use paper trading URLs
        """
        self.client = client or get_playwright_client()
        self.audit_dir = Path(audit_dir or "data/audit_trail")
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self.paper_trading = paper_trading
        self._logged_in = False
        self._audit_entries: list[AuditTrailEntry] = []

    async def initialize(self) -> bool:
        """Initialize the verifier and client.

        Returns:
            True if initialization successful
        """
        if not self.client.is_initialized:
            success = await self.client.initialize()
            if not success:
                logger.error("Failed to initialize Playwright client")
                return False

        return True

    async def login_to_alpaca(
        self,
        email: str | None = None,
        api_key: str | None = None,
    ) -> bool:
        """Login to Alpaca dashboard.

        Note: This requires manual login flow or OAuth token.
        For automated trading, API verification is preferred.

        Args:
            email: Alpaca account email (prompts if None)
            api_key: API key for OAuth (if supported)

        Returns:
            True if login successful
        """
        try:
            # Navigate to login page
            snapshot = await self.client.navigate(self.ALPACA_URLS["login"])
            if not snapshot:
                logger.error("Failed to load Alpaca login page")
                return False

            # Note: Alpaca uses OAuth/SSO which is complex to automate
            # For now, we'll check if already logged in
            await asyncio.sleep(2)

            # Check if we're on dashboard (already logged in)
            current_snapshot = await self.client.get_snapshot()
            if current_snapshot and "dashboard" in self.client.state.current_url:
                self._logged_in = True
                logger.info("Already logged into Alpaca")
                return True

            # Manual login required - capture screenshot for user
            screenshot_path = await self.client.screenshot("alpaca_login_required.png")

            logger.warning(
                "Manual Alpaca login required. Screenshot saved: %s",
                screenshot_path,
            )
            return False

        except Exception as e:
            logger.error("Login error: %s", e)
            return False

    async def capture_positions_screenshot(
        self,
        filename: str | None = None,
    ) -> PositionSnapshot | None:
        """Capture screenshot of current positions.

        Args:
            filename: Custom filename for screenshot

        Returns:
            PositionSnapshot with captured data
        """
        try:
            # Navigate to positions page
            url = (
                self.ALPACA_URLS["positions"]
                if self.paper_trading
                else "https://app.alpaca.markets/dashboard/positions"
            )

            snapshot = await self.client.navigate(url)
            if not snapshot:
                logger.error("Failed to load positions page")
                return None

            # Wait for positions to load
            await asyncio.sleep(3)

            # Take screenshot
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = filename or f"positions_{timestamp}.png"
            screenshot_path = await self.client.screenshot(filename, full_page=True)

            # Extract position data from accessibility tree
            positions = self._extract_positions_from_snapshot(snapshot)

            # Create position snapshot
            return PositionSnapshot(
                positions=positions,
                account_equity=None,  # Would parse from snapshot
                buying_power=None,
                screenshot_path=screenshot_path,
                capture_time=datetime.now(),
            )

        except Exception as e:
            logger.error("Error capturing positions: %s", e)
            return None

    async def verify_order_execution(
        self,
        order_id: str,
        expected_symbol: str,
        expected_qty: float,
        expected_side: str,
        api_response: dict | None = None,
    ) -> VerificationResult:
        """Verify an order was executed correctly.

        Args:
            order_id: Order ID to verify
            expected_symbol: Expected symbol
            expected_qty: Expected quantity
            expected_side: Expected side (buy/sell)
            api_response: Original API response for comparison

        Returns:
            VerificationResult with verification status
        """
        errors: list[str] = []
        verified = False
        actual_qty = None
        screenshot_path = None

        try:
            # Navigate to orders page
            url = (
                self.ALPACA_URLS["orders"]
                if self.paper_trading
                else "https://app.alpaca.markets/dashboard/orders"
            )

            snapshot = await self.client.navigate(url)
            if not snapshot:
                errors.append("Failed to load orders page")
            else:
                # Wait for orders to load
                await asyncio.sleep(3)

                # Take screenshot of orders
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_path = await self.client.screenshot(
                    f"order_verify_{order_id}_{timestamp}.png"
                )

                # Search for the order in the accessibility tree
                order_data = self._find_order_in_snapshot(snapshot, order_id)

                if order_data:
                    actual_qty = order_data.get("qty")
                    actual_symbol = order_data.get("symbol", "").upper()
                    actual_side = order_data.get("side", "").lower()
                    order_status = order_data.get("status", "").lower()

                    # Verify order matches expectations
                    if actual_symbol == expected_symbol.upper():
                        if actual_side == expected_side.lower():
                            if order_status in ["filled", "completed"]:
                                if actual_qty is not None:
                                    if abs(float(actual_qty) - expected_qty) < 0.01:
                                        verified = True
                                    else:
                                        errors.append(
                                            f"Qty mismatch: expected {expected_qty}, got {actual_qty}"
                                        )
                            else:
                                errors.append(f"Order status: {order_status}")
                        else:
                            errors.append(
                                f"Side mismatch: expected {expected_side}, got {actual_side}"
                            )
                    else:
                        errors.append(
                            f"Symbol mismatch: expected {expected_symbol}, got {actual_symbol}"
                        )
                else:
                    errors.append(f"Order {order_id} not found in web portal")

        except Exception as e:
            errors.append(f"Verification error: {e}")
            logger.error("Order verification error: %s", e)

        result = VerificationResult(
            verified=verified,
            order_id=order_id,
            symbol=expected_symbol,
            expected_qty=expected_qty,
            actual_qty=actual_qty,
            expected_side=expected_side,
            screenshot_path=screenshot_path,
            verification_time=datetime.now(),
            details={
                "api_response": api_response,
                "paper_trading": self.paper_trading,
            },
            errors=errors,
        )

        # Add to audit trail
        self._add_audit_entry(
            action="order_verification",
            order_id=order_id,
            symbol=expected_symbol,
            details={"result": "verified" if verified else "failed", "errors": errors},
            screenshot_path=screenshot_path,
            api_response=api_response,
            web_verification=result,
        )

        return result

    async def capture_account_summary(
        self,
        filename: str | None = None,
    ) -> tuple[Path | None, dict]:
        """Capture account summary screenshot and data.

        Args:
            filename: Custom filename for screenshot

        Returns:
            Tuple of (screenshot_path, account_data)
        """
        try:
            # Navigate to account page
            url = (
                self.ALPACA_URLS["account"]
                if self.paper_trading
                else "https://app.alpaca.markets/dashboard/account"
            )

            snapshot = await self.client.navigate(url)
            if not snapshot:
                logger.error("Failed to load account page")
                return None, {}

            # Wait for page to load
            await asyncio.sleep(3)

            # Take screenshot
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = filename or f"account_summary_{timestamp}.png"
            screenshot_path = await self.client.screenshot(filename, full_page=True)

            # Extract account data
            account_data = self._extract_account_data(snapshot)

            return screenshot_path, account_data

        except Exception as e:
            logger.error("Error capturing account summary: %s", e)
            return None, {}

    async def create_daily_audit_report(self) -> Path | None:
        """Create a daily audit report with all screenshots and verifications.

        Returns:
            Path to the audit report file
        """
        try:
            # Capture current state
            positions = await self.capture_positions_screenshot()
            account_path, account_data = await self.capture_account_summary()

            # Create report
            timestamp = datetime.now().strftime("%Y%m%d")
            report_path = self.audit_dir / f"audit_report_{timestamp}.json"

            report = {
                "date": datetime.now().isoformat(),
                "paper_trading": self.paper_trading,
                "positions": {
                    "data": positions.positions if positions else [],
                    "screenshot": str(positions.screenshot_path) if positions else None,
                    "capture_time": (positions.capture_time.isoformat() if positions else None),
                },
                "account": {
                    "data": account_data,
                    "screenshot": str(account_path) if account_path else None,
                },
                "audit_entries": [
                    {
                        "timestamp": entry.timestamp.isoformat(),
                        "action": entry.action,
                        "order_id": entry.order_id,
                        "symbol": entry.symbol,
                        "details": entry.details,
                        "screenshot": (
                            str(entry.screenshot_path) if entry.screenshot_path else None
                        ),
                    }
                    for entry in self._audit_entries
                ],
            }

            report_path.write_text(json.dumps(report, indent=2))
            logger.info("Audit report created: %s", report_path)

            return report_path

        except Exception as e:
            logger.error("Error creating audit report: %s", e)
            return None

    def _extract_positions_from_snapshot(
        self,
        snapshot: Any,
    ) -> list[dict]:
        """Extract position data from accessibility snapshot."""
        positions = []

        if not snapshot:
            return positions

        # Look for table rows or list items containing position data
        try:
            # Find elements that might contain position info
            text_elements = snapshot.find_elements(role="cell")
            text_elements.extend(snapshot.find_elements(role="gridcell"))

            # Group by row and extract symbol, qty, value
            current_position: dict = {}

            for element in text_elements:
                name = element.get("name", "").strip()
                if not name:
                    continue

                # Look for ticker symbols (2-5 uppercase letters)
                if len(name) <= 5 and name.isupper() and name.isalpha():
                    if current_position:
                        positions.append(current_position)
                    current_position = {"symbol": name}

                # Look for quantities/values
                elif current_position:
                    if "$" in name:
                        current_position["market_value"] = name
                    elif name.replace(".", "").replace("-", "").isdigit():
                        if "qty" not in current_position:
                            current_position["qty"] = name
                        else:
                            current_position["avg_price"] = name

            if current_position:
                positions.append(current_position)

        except Exception as e:
            logger.debug("Error extracting positions: %s", e)

        return positions

    def _find_order_in_snapshot(
        self,
        snapshot: Any,
        order_id: str,
    ) -> dict | None:
        """Find a specific order in the accessibility snapshot."""
        if not snapshot:
            return None

        try:
            # Search for order ID in the page
            all_text = []
            snapshot.find_elements(role="text")

            def collect_text(node: dict) -> None:
                name = node.get("name", "")
                if name:
                    all_text.append((name, node))
                for child in node.get("children", []):
                    collect_text(child)

            collect_text(snapshot.tree)

            # Look for order ID
            for text, _node in all_text:
                if order_id in text or order_id[:8] in text:
                    # Found the order, try to extract surrounding data
                    return {"order_id": order_id, "found": True}

        except Exception as e:
            logger.debug("Error finding order: %s", e)

        return None

    def _extract_account_data(self, snapshot: Any) -> dict:
        """Extract account data from accessibility snapshot."""
        data = {}

        if not snapshot:
            return data

        try:
            # Look for common account fields
            text_content = []

            def collect_text(node: dict) -> None:
                name = node.get("name", "")
                if name:
                    text_content.append(name)
                for child in node.get("children", []):
                    collect_text(child)

            collect_text(snapshot.tree)

            # Parse for equity, buying power, etc.
            for i, text in enumerate(text_content):
                text_lower = text.lower()
                if "equity" in text_lower or "portfolio" in text_lower:
                    if i + 1 < len(text_content):
                        data["equity"] = text_content[i + 1]
                elif "buying power" in text_lower:
                    if i + 1 < len(text_content):
                        data["buying_power"] = text_content[i + 1]
                elif "cash" in text_lower:
                    if i + 1 < len(text_content):
                        data["cash"] = text_content[i + 1]

        except Exception as e:
            logger.debug("Error extracting account data: %s", e)

        return data

    def _add_audit_entry(
        self,
        action: str,
        order_id: str | None = None,
        symbol: str | None = None,
        details: dict | None = None,
        screenshot_path: Path | None = None,
        api_response: dict | None = None,
        web_verification: VerificationResult | None = None,
    ) -> None:
        """Add an entry to the audit trail."""
        entry = AuditTrailEntry(
            timestamp=datetime.now(),
            action=action,
            order_id=order_id,
            symbol=symbol,
            details=details or {},
            screenshot_path=screenshot_path,
            api_response=api_response,
            web_verification=web_verification,
        )
        self._audit_entries.append(entry)

    async def close(self) -> None:
        """Close the verifier and cleanup."""
        await self.client.close()
        self._logged_in = False


# Convenience function for quick verification
async def verify_trade(
    order_id: str,
    symbol: str,
    qty: float,
    side: str,
    api_response: dict | None = None,
) -> VerificationResult:
    """Convenience function to verify a single trade.

    Args:
        order_id: Order ID to verify
        symbol: Expected symbol
        qty: Expected quantity
        side: Expected side (buy/sell)
        api_response: Original API response

    Returns:
        VerificationResult
    """
    verifier = TradeVerifier()
    await verifier.initialize()
    result = await verifier.verify_order_execution(
        order_id=order_id,
        expected_symbol=symbol,
        expected_qty=qty,
        expected_side=side,
        api_response=api_response,
    )
    await verifier.close()
    return result
