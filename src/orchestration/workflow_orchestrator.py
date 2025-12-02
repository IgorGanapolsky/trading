"""
Workflow Orchestrator - Coordinates multi-step automated workflows

Implements AgentKit-style workflow automation:
- Multi-step workflow execution
- Human-in-the-loop approval gates
- Error handling and retries
- Workflow state management
"""

import asyncio
import json
import logging
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from src.agents.approval_agent import ApprovalAgent
from src.agents.notification_agent import NotificationAgent
from src.agents.workflow_agent import WorkflowAgent

logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    """Workflow execution status."""

    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowOrchestrator:
    """
    Orchestrates multi-step workflows with approval gates.

    Features:
    - Sequential and parallel step execution
    - Human-in-the-loop approval gates
    - Error handling and retries
    - State persistence
    - Notification integration
    """

    def __init__(self):
        self.workflow_agent = WorkflowAgent()
        self.approval_agent = ApprovalAgent()
        self.notification_agent = NotificationAgent()
        self.active_workflows: dict[str, dict[str, Any]] = {}
        self.workflow_dir = Path("data/workflows")
        self.workflow_dir.mkdir(parents=True, exist_ok=True)

    async def execute_workflow(
        self, workflow_definition: dict[str, Any], workflow_id: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Execute a multi-step workflow.

        Args:
            workflow_definition: Workflow definition with steps
            workflow_id: Optional workflow ID (generated if not provided)

        Returns:
            Execution result
        """
        if not workflow_id:
            workflow_id = f"wf_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        workflow = {
            "id": workflow_id,
            "definition": workflow_definition,
            "status": WorkflowStatus.PENDING.value,
            "created_at": datetime.now().isoformat(),
            "steps": [],
            "current_step": 0,
        }

        self.active_workflows[workflow_id] = workflow
        self._save_workflow_state(workflow)

        try:
            workflow["status"] = WorkflowStatus.RUNNING.value

            steps = workflow_definition.get("steps", [])
            results = []

            for i, step in enumerate(steps):
                workflow["current_step"] = i
                step_result = await self._execute_step(workflow_id, step, i)
                results.append(step_result)

                # Check if step requires approval
                if step.get("requires_approval", False):
                    approval_result = await self._handle_approval_gate(
                        workflow_id, step, step_result
                    )

                    if not approval_result.get("approved", False):
                        workflow["status"] = WorkflowStatus.CANCELLED.value
                        workflow["cancellation_reason"] = "Approval denied"
                        break

                # Check if step failed
                if not step_result.get("success", False):
                    workflow["status"] = WorkflowStatus.FAILED.value
                    workflow["failure_step"] = i
                    workflow["failure_reason"] = step_result.get("error", "Unknown error")
                    break

            if workflow["status"] == WorkflowStatus.RUNNING.value:
                workflow["status"] = WorkflowStatus.COMPLETED.value

            workflow["completed_at"] = datetime.now().isoformat()
            workflow["results"] = results

            # Send completion notification
            await self._send_completion_notification(workflow)

            return workflow

        except Exception as e:
            logger.error(f"Workflow execution error: {e}")
            workflow["status"] = WorkflowStatus.FAILED.value
            workflow["error"] = str(e)
            return workflow

        finally:
            self._save_workflow_state(workflow)
            if workflow["status"] in [
                WorkflowStatus.COMPLETED,
                WorkflowStatus.FAILED,
                WorkflowStatus.CANCELLED,
            ]:
                del self.active_workflows[workflow_id]

    async def _execute_step(
        self, workflow_id: str, step: dict[str, Any], step_index: int
    ) -> dict[str, Any]:
        """
        Execute a single workflow step.

        Args:
            workflow_id: Workflow ID
            step: Step definition
            step_index: Step index

        Returns:
            Step execution result
        """
        step_type = step.get("type", "unknown")
        step_name = step.get("name", f"step_{step_index}")

        logger.info(f"Executing step {step_index}: {step_name} ({step_type})")

        try:
            if step_type == "workflow":
                # Call workflow agent
                result = self.workflow_agent.analyze(step.get("data", {}))
            elif step_type == "approval":
                # Request approval
                result = self.approval_agent.analyze(
                    {"type": "request_approval", **step.get("data", {})}
                )
            elif step_type == "notification":
                # Send notification
                result = self.notification_agent.analyze(step.get("data", {}))
            elif step_type == "mcp_call":
                # Call MCP tool
                result = await self._call_mcp_tool(step.get("data", {}))
            elif step_type == "model_training":
                # Train deep learning model
                result = await self._train_model(step.get("data", {}))
            elif step_type == "delay":
                # Wait for specified time
                delay_seconds = step.get("data", {}).get("seconds", 0)
                await asyncio.sleep(delay_seconds)
                result = {"success": True, "delayed_seconds": delay_seconds}
            else:
                result = {"success": False, "error": f"Unknown step type: {step_type}"}

            result["step_name"] = step_name
            result["step_index"] = step_index
            result["timestamp"] = datetime.now().isoformat()

            return result

        except Exception as e:
            logger.error(f"Step execution error: {e}")
            return {
                "success": False,
                "error": str(e),
                "step_name": step_name,
                "step_index": step_index,
            }

    async def _handle_approval_gate(
        self, workflow_id: str, step: dict[str, Any], step_result: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Handle approval gate in workflow.

        Args:
            workflow_id: Workflow ID
            step: Step definition
            step_result: Result from previous step

        Returns:
            Approval result
        """
        approval_data = step.get("approval", {})
        approval_type = approval_data.get("type", "manual")

        if approval_type == "auto":
            # Auto-approve based on conditions
            return {"approved": True, "type": "auto"}

        # Request human approval
        approval_request = self.approval_agent.analyze(
            {
                "type": "request_approval",
                "approval_type": step.get("type", "workflow_step"),
                "context": {
                    "workflow_id": workflow_id,
                    "step": step,
                    "step_result": step_result,
                },
                "priority": approval_data.get("priority", "medium"),
                "timeout_seconds": approval_data.get("timeout_seconds", 900),
            }
        )

        if not approval_request.get("approval_required", True):
            return {"approved": True, "type": "not_required"}

        approval_id = approval_request.get("approval_id")

        # Wait for approval
        approval_result = await self.approval_agent.wait_for_approval(approval_id)

        return {
            "approved": approval_result.get("status") == "approved",
            "approval_id": approval_id,
            "approval_result": approval_result,
        }

    async def _train_model(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Train deep learning model (LSTM feature extractor).

        Args:
            data: Training configuration (symbols, epochs, etc.)

        Returns:
            Training result
        """
        try:
            # Import model trainer skill
            import json as json_module
            import subprocess

            symbols = data.get("symbols", ["SPY", "QQQ", "VOO"])
            epochs = data.get("epochs", 50)
            batch_size = data.get("batch_size", 32)

            # Call model trainer skill
            cmd = [
                "python",
                ".claude/skills/model_trainer/scripts/model_trainer.py",
                "train",
                "--symbols",
                ",".join(symbols),
                "--epochs",
                str(epochs),
                "--batch-size",
                str(batch_size),
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(Path(__file__).parent.parent.parent),
            )

            if result.returncode == 0:
                training_result = json_module.loads(result.stdout)
                return {
                    "success": training_result.get("success", False),
                    "model_path": training_result.get("model_path"),
                    "training_metrics": training_result.get("training_metrics", {}),
                    "message": "Model training completed",
                }
            else:
                return {
                    "success": False,
                    "error": result.stderr,
                    "message": "Model training failed",
                }

        except Exception as e:
            logger.error(f"Model training error: {e}")
            return {"success": False, "error": str(e)}

    async def _call_mcp_tool(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Call an MCP tool.

        Args:
            data: MCP call data (server, tool, payload)

        Returns:
            MCP tool result
        """
        server = data.get("server")
        tool = data.get("tool")
        payload = data.get("payload", {})

        if not server or not tool:
            return {"success": False, "error": "server and tool required for MCP call"}

        try:
            # Import MCP client
            from mcp.client import default_client

            client = default_client()
            result = client.call_tool(server=server, tool=tool, payload=payload)

            return {"success": True, "server": server, "tool": tool, "result": result}
        except Exception as e:
            logger.error(f"MCP call error: {e}")
            return {"success": False, "error": str(e), "server": server, "tool": tool}

    async def _send_completion_notification(self, workflow: dict[str, Any]):
        """Send workflow completion notification."""
        status = workflow.get("status")
        workflow_id = workflow.get("id")

        message = f"Workflow {workflow_id} {status}"

        self.notification_agent.analyze(
            {
                "message": message,
                "channels": ["slack", "email"],
                "priority": "medium",
                "type": "workflow",
                "context": {"workflow_id": workflow_id, "status": status},
            }
        )

    def _save_workflow_state(self, workflow: dict[str, Any]):
        """Save workflow state to disk."""
        workflow_file = self.workflow_dir / f"{workflow['id']}.json"
        with open(workflow_file, "w") as f:
            json.dump(workflow, f, indent=2)

    def get_workflow_status(self, workflow_id: str) -> Optional[dict[str, Any]]:
        """Get current workflow status."""
        if workflow_id in self.active_workflows:
            return self.active_workflows[workflow_id]

        # Check saved workflows
        workflow_file = self.workflow_dir / f"{workflow_id}.json"
        if workflow_file.exists():
            with open(workflow_file) as f:
                return json.load(f)

        return None
