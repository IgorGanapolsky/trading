"""
Slack MCP Server - Slack notifications and messaging

Provides tools for:
- Sending messages to channels
- Sending direct messages
- Posting formatted messages
- Reading channel messages
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError

    SLACK_API_AVAILABLE = True
except ImportError:
    SLACK_API_AVAILABLE = False

from mcp.utils import run_sync

logger = logging.getLogger(__name__)

_slack_client = None


def _get_slack_client():
    """Get Slack Web API client."""
    global _slack_client

    if not SLACK_API_AVAILABLE:
        logger.warning("Slack SDK not installed - install slack-sdk")
        return None

    if _slack_client is not None:
        return _slack_client

    slack_token = os.getenv("SLACK_BOT_TOKEN")
    if not slack_token:
        logger.warning("SLACK_BOT_TOKEN not set - Slack MCP will be limited")
        return None

    try:
        _slack_client = WebClient(token=slack_token)
        # Test connection
        _slack_client.auth_test()
        logger.info("Slack API client initialized successfully")
        return _slack_client
    except Exception as e:
        logger.error(f"Failed to initialize Slack client: {e}")
        return None


async def send_message_async(
    channel: str, message: str, thread_ts: str | None = None
) -> dict[str, Any]:
    """
    Send message to Slack channel.

    Args:
        channel: Channel ID or name (e.g., "#trading-alerts")
        message: Message text
        thread_ts: Optional thread timestamp to reply to

    Returns:
        Send result
    """
    logger.info(f"Sending Slack message to {channel}")

    client = _get_slack_client()
    if not client:
        return {
            "success": False,
            "channel": channel,
            "message": message,
            "error": "Slack API client not available - check SLACK_BOT_TOKEN",
        }

    try:
        kwargs = {"channel": channel, "text": message}
        if thread_ts:
            kwargs["thread_ts"] = thread_ts

        response = client.chat_postMessage(**kwargs)

        return {
            "success": True,
            "channel": channel,
            "message": message,
            "ts": response["ts"],
            "timestamp": datetime.now().isoformat(),
            "message_id": response.get("message", {}).get("ts"),
        }

    except SlackApiError as e:
        logger.error(f"Slack API error: {e.response['error']}")
        return {
            "success": False,
            "channel": channel,
            "message": message,
            "error": f"Slack API error: {e.response['error']}",
        }
    except Exception as e:
        logger.error(f"Unexpected error sending Slack message: {e}")
        return {
            "success": False,
            "channel": channel,
            "message": message,
            "error": str(e),
        }


def send_message(channel: str, message: str, thread_ts: str | None = None) -> dict[str, Any]:
    """Sync wrapper for send_message_async."""
    return run_sync(send_message_async(channel, message, thread_ts))


async def send_formatted_message_async(
    channel: str, blocks: list[dict[str, Any]], text: str | None = None
) -> dict[str, Any]:
    """
    Send formatted message with Slack blocks.

    Args:
        channel: Channel ID or name
        blocks: Slack block kit blocks
        text: Fallback text

    Returns:
        Send result
    """
    logger.info(f"Sending formatted Slack message to {channel}")

    client = _get_slack_client()
    if not client:
        return {
            "success": False,
            "channel": channel,
            "blocks": blocks,
            "error": "Slack API client not available - check SLACK_BOT_TOKEN",
        }

    try:
        kwargs = {"channel": channel, "blocks": blocks}
        if text:
            kwargs["text"] = text

        response = client.chat_postMessage(**kwargs)

        return {
            "success": True,
            "channel": channel,
            "blocks": blocks,
            "ts": response["ts"],
            "timestamp": datetime.now().isoformat(),
            "message_id": response.get("message", {}).get("ts"),
        }

    except SlackApiError as e:
        logger.error(f"Slack API error: {e.response['error']}")
        return {
            "success": False,
            "channel": channel,
            "blocks": blocks,
            "error": f"Slack API error: {e.response['error']}",
        }
    except Exception as e:
        logger.error(f"Unexpected error sending formatted Slack message: {e}")
        return {"success": False, "channel": channel, "blocks": blocks, "error": str(e)}


def send_formatted_message(
    channel: str, blocks: list[dict[str, Any]], text: str | None = None
) -> dict[str, Any]:
    """Sync wrapper for send_formatted_message_async."""
    return run_sync(send_formatted_message_async(channel, blocks, text))


async def send_dm_async(user_id: str, message: str) -> dict[str, Any]:
    """
    Send direct message to user.

    Args:
        user_id: Slack user ID
        message: Message text

    Returns:
        Send result
    """
    logger.info(f"Sending DM to user {user_id}")

    client = _get_slack_client()
    if not client:
        return {
            "success": False,
            "user_id": user_id,
            "message": message,
            "error": "Slack API client not available - check SLACK_BOT_TOKEN",
        }

    try:
        # Open DM channel with user
        conversation = client.conversations_open(users=[user_id])
        channel_id = conversation["channel"]["id"]

        # Send message to DM channel
        response = client.chat_postMessage(channel=channel_id, text=message)

        return {
            "success": True,
            "user_id": user_id,
            "message": message,
            "ts": response["ts"],
            "channel_id": channel_id,
            "timestamp": datetime.now().isoformat(),
            "message_id": response.get("message", {}).get("ts"),
        }

    except SlackApiError as e:
        logger.error(f"Slack API error: {e.response['error']}")
        return {
            "success": False,
            "user_id": user_id,
            "message": message,
            "error": f"Slack API error: {e.response['error']}",
        }
    except Exception as e:
        logger.error(f"Unexpected error sending DM: {e}")
        return {
            "success": False,
            "user_id": user_id,
            "message": message,
            "error": str(e),
        }


def send_dm(user_id: str, message: str) -> dict[str, Any]:
    """Sync wrapper for send_dm_async."""
    return run_sync(send_dm_async(user_id, message))


def create_trade_alert_block(trade_data: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Create Slack block kit blocks for trade alert.

    Args:
        trade_data: Trade information

    Returns:
        List of Slack blocks
    """
    symbol = trade_data.get("symbol", "UNKNOWN")
    side = trade_data.get("side", "BUY").upper()
    quantity = trade_data.get("quantity", 0)
    price = trade_data.get("price", 0)

    return [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"Trade Executed: {symbol}"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Side:* {side}"},
                {"type": "mrkdwn", "text": f"*Quantity:* {quantity}"},
                {"type": "mrkdwn", "text": f"*Price:* ${price:.2f}"},
                {"type": "mrkdwn", "text": f"*Value:* ${quantity * price:.2f}"},
            ],
        },
    ]
