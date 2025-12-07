"""
Human-in-the-Loop Approval Agent

Implements approval workflows for high-value trades and critical decisions.
Based on AgentKit pattern with human approval gates.
"""

import asyncio
import json
import logging
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from src.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ApprovalStatus(Enum):
    """Approval status enumeration."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"
    EXPIRED = "expired"


@dataclass
class ApprovalRequest:
    """Represents a human approval request."""

    id: str
    type: str  # "trade", "risk_override", "circuit_breaker", etc.
    context: dict[str, Any]
    priority: str  # "low", "medium", "high", "critical"
    timeout_seconds: int = 900  # Default 15 minutes
    created_at: str = ""
    status: str = ApprovalStatus.PENDING.value
    decision: dict[str, Any] | None = None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


class ApprovalAgent(BaseAgent):
    """
    Human-in-the-loop approval agent.

    Manages approval workflows for:
    - High-value trades (> threshold)
    - Risk limit overrides
    - Circuit breaker decisions
    - Strategy changes
    """

    def __init__(self):
        super().__init__(name="ApprovalAgent", role="Human Approval Coordinator")
        self.pending_approvals: dict[str, ApprovalRequest] = {}
        self.approval_history: list[ApprovalRequest] = []
        self.approval_dir = Path("data/approvals")
        self.approval_dir.mkdir(parents=True, exist_ok=True)

        # Configuration
        self.high_value_threshold = float(os.getenv("APPROVAL_HIGH_VALUE_THRESHOLD", "1000.0"))
        self.notification_channels = os.getenv("APPROVAL_NOTIFICATION_CHANNELS", "email").split(",")

    def analyze(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Process an approval request.

        Args:
            data: Approval request data

        Returns:
            Approval result
        """
        request_type = data.get("type", "trade")

        if request_type == "request_approval":
            return self._request_approval(data)
        elif request_type == "check_approval":
            return self._check_approval_status(data)
        elif request_type == "submit_decision":
            return self._submit_decision(data)
        else:
            return {"success": False, "error": f"Unknown approval type: {request_type}"}

    def _request_approval(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Request human approval for a decision.

        Args:
            data: Contains decision context, type, priority

        Returns:
            Approval request ID and status
        """
        approval_type = data.get("approval_type", "trade")
        context = data.get("context", {})
        priority = data.get("priority", "medium")
        timeout = data.get("timeout_seconds", 900)

        # Determine if approval is needed
        if approval_type == "trade":
            trade_value = context.get("trade_value", 0)
            if trade_value < self.high_value_threshold:
                return {
                    "success": True,
                    "approval_required": False,
                    "reason": f"Trade value ${trade_value} below threshold ${self.high_value_threshold}",
                }

        # Create approval request
        approval_id = str(uuid.uuid4())
        request = ApprovalRequest(
            id=approval_id,
            type=approval_type,
            context=context,
            priority=priority,
            timeout_seconds=timeout,
        )

        self.pending_approvals[approval_id] = request

        # Send notifications
        asyncio.create_task(self._send_notifications(request))

        # Save to disk
        self._save_approval_request(request)

        logger.info(f"Approval requested: {approval_id} ({approval_type}, {priority})")

        return {
            "success": True,
            "approval_required": True,
            "approval_id": approval_id,
            "status": ApprovalStatus.PENDING.value,
            "timeout_at": (datetime.now() + timedelta(seconds=timeout)).isoformat(),
            "notification_channels": self.notification_channels,
        }

    def _check_approval_status(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Check status of an approval request.

        Args:
            data: Contains approval_id

        Returns:
            Current approval status
        """
        approval_id = data.get("approval_id")
        if not approval_id:
            return {"success": False, "error": "approval_id required"}

        if approval_id in self.pending_approvals:
            request = self.pending_approvals[approval_id]

            # Check timeout
            created_at = datetime.fromisoformat(request.created_at)
            timeout_at = created_at + timedelta(seconds=request.timeout_seconds)

            if datetime.now() > timeout_at:
                request.status = ApprovalStatus.TIMEOUT.value
                self._finalize_approval(request)
                return {
                    "success": True,
                    "status": ApprovalStatus.TIMEOUT.value,
                    "reason": "Approval request timed out",
                }

            return {
                "success": True,
                "status": request.status,
                "created_at": request.created_at,
                "timeout_at": timeout_at.isoformat(),
                "context": request.context,
            }
        else:
            # Check history
            for req in self.approval_history:
                if req.id == approval_id:
                    return {
                        "success": True,
                        "status": req.status,
                        "decision": req.decision,
                        "created_at": req.created_at,
                    }

            return {
                "success": False,
                "error": f"Approval request {approval_id} not found",
            }

    def _submit_decision(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Submit human decision for an approval request.

        Args:
            data: Contains approval_id, decision (approved/rejected), reason

        Returns:
            Decision result
        """
        approval_id = data.get("approval_id")
        decision = data.get("decision", "rejected")  # "approved" or "rejected"
        reason = data.get("reason", "")
        decision_by = data.get("decision_by", "human")

        if not approval_id:
            return {"success": False, "error": "approval_id required"}

        if approval_id not in self.pending_approvals:
            return {
                "success": False,
                "error": f"Approval request {approval_id} not found or already processed",
            }

        request = self.pending_approvals[approval_id]

        # Update request
        request.status = (
            ApprovalStatus.APPROVED.value
            if decision == "approved"
            else ApprovalStatus.REJECTED.value
        )
        request.decision = {
            "decision": decision,
            "reason": reason,
            "decision_by": decision_by,
            "decided_at": datetime.now().isoformat(),
        }

        # Finalize
        self._finalize_approval(request)

        logger.info(f"Approval {approval_id} {decision}: {reason}")

        return {
            "success": True,
            "approval_id": approval_id,
            "status": request.status,
            "decision": request.decision,
        }

    def _finalize_approval(self, request: ApprovalRequest):
        """Move approval from pending to history."""
        if request.id in self.pending_approvals:
            del self.pending_approvals[request.id]

        self.approval_history.append(request)

        # Save to disk
        self._save_approval_request(request)

    async def _send_notifications(self, request: ApprovalRequest):
        """Send notifications to configured channels."""
        logger.info(f"Sending approval notifications for {request.id}")

        # This would integrate with notification MCPs (Slack, Email, etc.)
        # For now, log the notification

        notification_message = (
            f"🔔 Approval Required: {request.type}\n"
            f"Priority: {request.priority}\n"
            f"ID: {request.id}\n"
            f"Context: {json.dumps(request.context, indent=2)}"
        )

        for channel in self.notification_channels:
            logger.info(f"Notification to {channel}: {notification_message[:100]}...")
            # TODO: Integrate with actual notification MCPs

    def _save_approval_request(self, request: ApprovalRequest):
        """Save approval request to disk."""
        file_path = self.approval_dir / f"{request.id}.json"
        with open(file_path, "w") as f:
            json.dump(asdict(request), f, indent=2)

    async def wait_for_approval(self, approval_id: str, check_interval: int = 5) -> dict[str, Any]:
        """
        Wait for approval decision (async).

        Args:
            approval_id: Approval request ID
            check_interval: Seconds between status checks

        Returns:
            Final approval decision
        """
        while True:
            status_result = self._check_approval_status({"approval_id": approval_id})

            if status_result.get("status") != ApprovalStatus.PENDING.value:
                return status_result

            await asyncio.sleep(check_interval)
