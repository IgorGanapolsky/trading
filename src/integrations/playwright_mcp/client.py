"""Playwright MCP Client - Core browser automation using accessibility snapshots.

This client interfaces with the Playwright MCP server to provide:
- LLM-friendly accessibility tree snapshots (no vision models needed)
- Full browser control: navigate, click, type, screenshot
- Headless operation for automated trading workflows

Reference: https://github.com/microsoft/playwright-mcp
"""

import asyncio
import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AccessibilitySnapshot:
    """Structured representation of a page's accessibility tree."""

    url: str
    title: str
    tree: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)

    def find_elements(self, role: str | None = None, name: str | None = None) -> list[dict]:
        """Find elements in the accessibility tree by role or name."""
        results = []
        self._search_tree(self.tree, role, name, results)
        return results

    def _search_tree(
        self,
        node: dict,
        role: str | None,
        name: str | None,
        results: list,
    ) -> None:
        """Recursively search the accessibility tree."""
        if node is None:
            return

        matches = True
        if role and node.get("role") != role:
            matches = False
        if name and name.lower() not in node.get("name", "").lower():
            matches = False

        if matches and (role or name):
            results.append(node)

        for child in node.get("children", []):
            self._search_tree(child, role, name, results)


@dataclass
class BrowserState:
    """Current state of the browser session."""

    current_url: str = ""
    page_title: str = ""
    is_ready: bool = False
    last_action: str = ""
    last_action_time: datetime | None = None


class PlaywrightMCPClient:
    """Client for interacting with Playwright MCP server.

    Provides browser automation through the Model Context Protocol,
    using accessibility snapshots for LLM-friendly page interaction.
    """

    def __init__(
        self,
        headless: bool = True,
        timeout: int = 30000,
        screenshots_dir: str | None = None,
    ):
        """Initialize the Playwright MCP client.

        Args:
            headless: Run browser in headless mode (default: True)
            timeout: Default timeout for operations in milliseconds
            screenshots_dir: Directory to save screenshots
        """
        self.headless = headless
        self.timeout = timeout
        self.screenshots_dir = Path(screenshots_dir or "data/audit_trail/screenshots")
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)

        self._browser_state = BrowserState()
        self._process: subprocess.Popen | None = None
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize the Playwright MCP server.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Check if Playwright is installed
            result = subprocess.run(
                ["npx", "@playwright/mcp@latest", "--help"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                logger.error("Playwright MCP not available: %s", result.stderr)
                return False

            self._initialized = True
            logger.info("Playwright MCP client initialized successfully")
            return True

        except subprocess.TimeoutExpired:
            logger.error("Playwright MCP initialization timed out")
            return False
        except FileNotFoundError:
            logger.error("npx not found - ensure Node.js is installed")
            return False
        except Exception as e:
            logger.error("Failed to initialize Playwright MCP: %s", e)
            return False

    async def navigate(self, url: str) -> AccessibilitySnapshot | None:
        """Navigate to a URL and get accessibility snapshot.

        Args:
            url: The URL to navigate to

        Returns:
            AccessibilitySnapshot of the page, or None on failure
        """
        try:
            result = await self._call_mcp_tool(
                "browser_navigate",
                {"url": url},
            )

            if result and result.get("success"):
                self._browser_state.current_url = url
                self._browser_state.is_ready = True
                self._browser_state.last_action = f"navigate:{url}"
                self._browser_state.last_action_time = datetime.now()

                # Get accessibility snapshot after navigation
                return await self.get_snapshot()

            return None

        except Exception as e:
            logger.error("Navigation failed: %s", e)
            return None

    async def get_snapshot(self) -> AccessibilitySnapshot | None:
        """Get the current page's accessibility snapshot.

        Returns:
            AccessibilitySnapshot of the current page
        """
        try:
            result = await self._call_mcp_tool("browser_snapshot", {})

            if result:
                return AccessibilitySnapshot(
                    url=self._browser_state.current_url,
                    title=result.get("title", ""),
                    tree=result.get("tree", {}),
                )
            return None

        except Exception as e:
            logger.error("Failed to get snapshot: %s", e)
            return None

    async def click(self, selector: str) -> bool:
        """Click an element by accessibility selector.

        Args:
            selector: Accessibility selector (e.g., "button:Submit")

        Returns:
            True if click successful
        """
        try:
            result = await self._call_mcp_tool(
                "browser_click",
                {"element": selector},
            )
            success = result.get("success", False) if result else False
            if success:
                self._browser_state.last_action = f"click:{selector}"
                self._browser_state.last_action_time = datetime.now()
            return success

        except Exception as e:
            logger.error("Click failed: %s", e)
            return False

    async def type_text(self, selector: str, text: str) -> bool:
        """Type text into an element.

        Args:
            selector: Accessibility selector for the input element
            text: Text to type

        Returns:
            True if typing successful
        """
        try:
            result = await self._call_mcp_tool(
                "browser_type",
                {"element": selector, "text": text},
            )
            success = result.get("success", False) if result else False
            if success:
                self._browser_state.last_action = f"type:{selector}"
                self._browser_state.last_action_time = datetime.now()
            return success

        except Exception as e:
            logger.error("Typing failed: %s", e)
            return False

    async def scroll(self, direction: str = "down", amount: int = 500) -> bool:
        """Scroll the page.

        Args:
            direction: "up" or "down"
            amount: Pixels to scroll

        Returns:
            True if scroll successful
        """
        try:
            # Calculate scroll coordinates
            delta_y = amount if direction == "down" else -amount

            result = await self._call_mcp_tool(
                "browser_scroll",
                {"deltaY": delta_y},
            )
            return result.get("success", False) if result else False

        except Exception as e:
            logger.error("Scroll failed: %s", e)
            return False

    async def screenshot(
        self,
        filename: str | None = None,
        full_page: bool = False,
    ) -> Path | None:
        """Take a screenshot of the current page.

        Args:
            filename: Custom filename (default: timestamp-based)
            full_page: Capture full scrollable page

        Returns:
            Path to saved screenshot, or None on failure
        """
        try:
            result = await self._call_mcp_tool(
                "browser_screenshot",
                {"fullPage": full_page},
            )

            if result and result.get("data"):
                # Generate filename if not provided
                if not filename:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"screenshot_{timestamp}.png"

                filepath = self.screenshots_dir / filename

                # Decode and save screenshot
                import base64

                image_data = base64.b64decode(result["data"])
                filepath.write_bytes(image_data)

                logger.info("Screenshot saved: %s", filepath)
                return filepath

            return None

        except Exception as e:
            logger.error("Screenshot failed: %s", e)
            return None

    async def wait_for_element(
        self,
        selector: str,
        timeout: int | None = None,
    ) -> bool:
        """Wait for an element to appear.

        Args:
            selector: Accessibility selector
            timeout: Timeout in milliseconds

        Returns:
            True if element found within timeout
        """
        timeout = timeout or self.timeout
        start_time = datetime.now()
        poll_interval = 500  # ms

        while True:
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            if elapsed > timeout:
                logger.warning("Timeout waiting for element: %s", selector)
                return False

            snapshot = await self.get_snapshot()
            if snapshot:
                # Parse selector (format: "role:name")
                parts = selector.split(":", 1)
                role = parts[0] if len(parts) > 0 else None
                name = parts[1] if len(parts) > 1 else None

                elements = snapshot.find_elements(role=role, name=name)
                if elements:
                    return True

            await asyncio.sleep(poll_interval / 1000)

    async def extract_text(self, selector: str | None = None) -> list[str]:
        """Extract text content from the page or specific elements.

        Args:
            selector: Optional accessibility selector to filter elements

        Returns:
            List of text strings found
        """
        try:
            snapshot = await self.get_snapshot()
            if not snapshot:
                return []

            # Parse selector if provided
            role = None
            name = None
            if selector:
                parts = selector.split(":", 1)
                role = parts[0] if len(parts) > 0 else None
                name = parts[1] if len(parts) > 1 else None

            if role or name:
                elements = snapshot.find_elements(role=role, name=name)
            else:
                elements = [snapshot.tree]

            texts = []
            for element in elements:
                self._extract_text_recursive(element, texts)

            return texts

        except Exception as e:
            logger.error("Text extraction failed: %s", e)
            return []

    def _extract_text_recursive(self, node: dict, texts: list) -> None:
        """Recursively extract text from accessibility tree nodes."""
        if node is None:
            return

        # Extract text from this node
        if node.get("name"):
            texts.append(node["name"])
        if node.get("value"):
            texts.append(node["value"])

        # Recurse into children
        for child in node.get("children", []):
            self._extract_text_recursive(child, texts)

    async def _call_mcp_tool(
        self,
        tool_name: str,
        params: dict[str, Any],
    ) -> dict | None:
        """Call a Playwright MCP tool.

        Args:
            tool_name: Name of the MCP tool
            params: Tool parameters

        Returns:
            Tool result or None on failure
        """
        try:
            # Build MCP command
            cmd = [
                "npx",
                "@playwright/mcp@latest",
                "--headless" if self.headless else "",
                "call",
                tool_name,
                json.dumps(params),
            ]
            # Remove empty args
            cmd = [c for c in cmd if c]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout / 1000,
            )

            if result.returncode == 0:
                return json.loads(result.stdout) if result.stdout else {"success": True}
            else:
                logger.error("MCP tool error: %s", result.stderr)
                return None

        except subprocess.TimeoutExpired:
            logger.error("MCP tool timed out: %s", tool_name)
            return None
        except json.JSONDecodeError as e:
            logger.error("Failed to parse MCP response: %s", e)
            return None
        except Exception as e:
            logger.error("MCP tool call failed: %s", e)
            return None

    async def close(self) -> None:
        """Close the browser and cleanup resources."""
        try:
            await self._call_mcp_tool("browser_close", {})
            self._browser_state = BrowserState()
            self._initialized = False
            logger.info("Browser closed successfully")
        except Exception as e:
            logger.error("Error closing browser: %s", e)

    @property
    def state(self) -> BrowserState:
        """Get current browser state."""
        return self._browser_state

    @property
    def is_initialized(self) -> bool:
        """Check if client is initialized."""
        return self._initialized


# Singleton instance for shared usage
_client_instance: PlaywrightMCPClient | None = None


def get_playwright_client(
    headless: bool = True,
    screenshots_dir: str | None = None,
) -> PlaywrightMCPClient:
    """Get or create the shared Playwright MCP client instance.

    Args:
        headless: Run browser in headless mode
        screenshots_dir: Directory to save screenshots

    Returns:
        Shared PlaywrightMCPClient instance
    """
    global _client_instance
    if _client_instance is None:
        _client_instance = PlaywrightMCPClient(
            headless=headless,
            screenshots_dir=screenshots_dir,
        )
    return _client_instance
