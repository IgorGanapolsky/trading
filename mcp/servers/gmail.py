"""
Gmail MCP Server - Email monitoring and processing

Provides tools for:
- Monitoring emails
- Sending emails
- Processing attachments
- Email-based workflow triggers
"""

from __future__ import annotations

import base64
import logging
import os
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    GMAIL_API_AVAILABLE = True
except ImportError:
    GMAIL_API_AVAILABLE = False

from mcp.utils import run_sync

logger = logging.getLogger(__name__)

# Gmail API scopes
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]

_gmail_service = None


def _get_gmail_client():
    """Get Gmail API client with OAuth2 authentication."""
    global _gmail_service

    if not GMAIL_API_AVAILABLE:
        logger.warning("Gmail API libraries not installed - install google-api-python-client")
        return None

    if _gmail_service is not None:
        return _gmail_service

    # Check for credentials file path
    credentials_path = os.getenv("GMAIL_CREDENTIALS_PATH")
    token_path = os.getenv("GMAIL_TOKEN_PATH", "data/gmail_token.json")

    if not credentials_path:
        logger.warning("GMAIL_CREDENTIALS_PATH not set - Gmail MCP will be limited")
        return None

    try:
        creds = None

        # Load existing token
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)

        # Refresh or get new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(credentials_path):
                    logger.error(f"Gmail credentials file not found: {credentials_path}")
                    return None

                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)

            # Save credentials for next run
            os.makedirs(os.path.dirname(token_path), exist_ok=True)
            with open(token_path, "w") as token:
                token.write(creds.to_json())

        # Build Gmail service
        _gmail_service = build("gmail", "v1", credentials=creds)
        logger.info("Gmail API client initialized successfully")
        return _gmail_service

    except Exception as e:
        logger.error(f"Failed to initialize Gmail client: {e}")
        return None


async def monitor_emails_async(query: str = "is:unread", max_results: int = 10) -> dict[str, Any]:
    """
    Monitor emails matching query.

    Args:
        query: Gmail search query (e.g., "is:unread from:client@example.com")
        max_results: Maximum number of emails to return

    Returns:
        List of emails with metadata
    """
    logger.info(f"Monitoring emails: {query}")

    service = _get_gmail_client()
    if not service:
        return {
            "emails": [],
            "query": query,
            "count": 0,
            "timestamp": datetime.now().isoformat(),
            "error": "Gmail API client not available - check credentials",
        }

    try:
        # Search for messages
        results = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=min(max_results, 100))
            .execute()
        )

        messages = results.get("messages", [])
        emails = []

        for msg in messages:
            try:
                # Get full message details
                message = (
                    service.users()
                    .messages()
                    .get(userId="me", id=msg["id"], format="full")
                    .execute()
                )

                payload = message.get("payload", {})
                headers = payload.get("headers", [])

                # Extract headers
                email_data = {
                    "id": msg["id"],
                    "thread_id": message.get("threadId"),
                    "snippet": message.get("snippet", ""),
                    "labels": message.get("labelIds", []),
                }

                for header in headers:
                    name = header.get("name", "").lower()
                    value = header.get("value", "")
                    if name == "from":
                        email_data["from"] = value
                    elif name == "to":
                        email_data["to"] = value
                    elif name == "subject":
                        email_data["subject"] = value
                    elif name == "date":
                        email_data["date"] = value

                emails.append(email_data)

            except Exception as e:
                logger.warning(f"Failed to get message {msg.get('id')}: {e}")
                continue

        return {
            "emails": emails,
            "query": query,
            "count": len(emails),
            "timestamp": datetime.now().isoformat(),
            "success": True,
        }

    except HttpError as e:
        logger.error(f"Gmail API error: {e}")
        return {
            "emails": [],
            "query": query,
            "count": 0,
            "timestamp": datetime.now().isoformat(),
            "error": f"Gmail API error: {str(e)}",
        }
    except Exception as e:
        logger.error(f"Unexpected error monitoring emails: {e}")
        return {
            "emails": [],
            "query": query,
            "count": 0,
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
        }


def monitor_emails(query: str = "is:unread", max_results: int = 10) -> dict[str, Any]:
    """Sync wrapper for monitor_emails_async."""
    return run_sync(monitor_emails_async(query, max_results))


async def send_email_async(
    to: str | list[str],
    subject: str,
    body: str,
    attachments: list[str] | None = None,
) -> dict[str, Any]:
    """
    Send email via Gmail.

    Args:
        to: Recipient email(s)
        subject: Email subject
        body: Email body
        attachments: Optional list of file paths to attach

    Returns:
        Send result
    """
    logger.info(f"Sending email to {to}: {subject}")

    service = _get_gmail_client()
    if not service:
        return {
            "success": False,
            "to": to if isinstance(to, list) else [to],
            "subject": subject,
            "error": "Gmail API client not available - check credentials",
        }

    try:
        recipients = to if isinstance(to, list) else [to]

        # Create message
        message = MIMEMultipart()
        message["to"] = ", ".join(recipients)
        message["subject"] = subject
        message.attach(MIMEText(body, "plain"))

        # Add attachments if provided
        if attachments:
            for file_path in attachments:
                if os.path.exists(file_path):
                    with open(file_path, "rb") as f:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(f.read())
                        encoders.encode_base64(part)
                        part.add_header(
                            "Content-Disposition",
                            f"attachment; filename= {os.path.basename(file_path)}",
                        )
                        message.attach(part)

        # Encode message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

        # Send message
        send_message = (
            service.users().messages().send(userId="me", body={"raw": raw_message}).execute()
        )

        return {
            "success": True,
            "to": recipients,
            "subject": subject,
            "message_id": send_message.get("id"),
            "thread_id": send_message.get("threadId"),
            "timestamp": datetime.now().isoformat(),
        }

    except HttpError as e:
        logger.error(f"Gmail API error sending email: {e}")
        return {
            "success": False,
            "to": to if isinstance(to, list) else [to],
            "subject": subject,
            "error": f"Gmail API error: {str(e)}",
        }
    except Exception as e:
        logger.error(f"Unexpected error sending email: {e}")
        return {
            "success": False,
            "to": to if isinstance(to, list) else [to],
            "subject": subject,
            "error": str(e),
        }


def send_email(
    to: str | list[str],
    subject: str,
    body: str,
    attachments: list[str] | None = None,
) -> dict[str, Any]:
    """Sync wrapper for send_email_async."""
    return run_sync(send_email_async(to, subject, body, attachments))


async def process_attachment_async(
    message_id: str, attachment_id: str, save_path: str | None = None
) -> dict[str, Any]:
    """
    Download and process email attachment.

    Args:
        message_id: Gmail message ID
        attachment_id: Attachment ID
        save_path: Optional path to save attachment

    Returns:
        Processing result
    """
    logger.info(f"Processing attachment {attachment_id} from message {message_id}")

    service = _get_gmail_client()
    if not service:
        return {
            "success": False,
            "message_id": message_id,
            "attachment_id": attachment_id,
            "error": "Gmail API client not available - check credentials",
        }

    try:
        # Get attachment
        attachment = (
            service.users()
            .messages()
            .attachments()
            .get(userId="me", messageId=message_id, id=attachment_id)
            .execute()
        )

        # Decode attachment data
        file_data = base64.urlsafe_b64decode(attachment["data"])

        # Save to file if path provided
        if save_path:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(file_data)

        return {
            "success": True,
            "message_id": message_id,
            "attachment_id": attachment_id,
            "saved_path": save_path,
            "size": attachment.get("size", len(file_data)),
            "timestamp": datetime.now().isoformat(),
        }

    except HttpError as e:
        logger.error(f"Gmail API error processing attachment: {e}")
        return {
            "success": False,
            "message_id": message_id,
            "attachment_id": attachment_id,
            "error": f"Gmail API error: {str(e)}",
        }
    except Exception as e:
        logger.error(f"Unexpected error processing attachment: {e}")
        return {
            "success": False,
            "message_id": message_id,
            "attachment_id": attachment_id,
            "error": str(e),
        }


def process_attachment(
    message_id: str, attachment_id: str, save_path: str | None = None
) -> dict[str, Any]:
    """Sync wrapper for process_attachment_async."""
    return run_sync(process_attachment_async(message_id, attachment_id, save_path))
