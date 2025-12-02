"""
Example: Workflow Automation with Human-in-the-Loop

Demonstrates AgentKit-style workflow automation:
1. Email monitoring workflow
2. Report generation with approval
3. Multi-step trading workflow
"""

import asyncio

from src.orchestration.workflow_orchestrator import WorkflowOrchestrator


async def example_email_workflow():
    """Example: Email monitoring and processing workflow."""
    orchestrator = WorkflowOrchestrator()

    workflow = {
        "name": "Client Report Processing",
        "description": "Monitor email, process CSV, update dashboard",
        "steps": [
            {
                "name": "monitor_email",
                "type": "mcp_call",
                "data": {
                    "server": "gmail",
                    "tool": "monitor_emails",
                    "payload": {
                        "query": "is:unread from:client@example.com has:attachment",
                        "max_results": 5,
                    },
                },
            },
            {
                "name": "process_attachment",
                "type": "mcp_call",
                "data": {
                    "server": "gmail",
                    "tool": "process_attachment",
                    "payload": {
                        "message_id": "{previous_step.message_id}",
                        "attachment_id": "{previous_step.attachment_id}",
                        "save_path": "data/reports/client_report.csv",
                    },
                },
                "requires_approval": True,
                "approval": {
                    "type": "manual",
                    "priority": "medium",
                    "timeout_seconds": 900,
                },
            },
            {
                "name": "update_dashboard",
                "type": "workflow",
                "data": {
                    "type": "file_processing",
                    "file_path": "data/reports/client_report.csv",
                    "file_type": "csv",
                },
            },
            {
                "name": "send_confirmation",
                "type": "notification",
                "data": {
                    "message": "Client report processed and dashboard updated",
                    "channels": ["email", "slack"],
                    "priority": "low",
                },
            },
        ],
    }

    result = await orchestrator.execute_workflow(workflow)
    print(f"Workflow completed: {result['status']}")
    return result


async def example_report_workflow():
    """Example: Automated report generation with approval."""
    orchestrator = WorkflowOrchestrator()

    workflow = {
        "name": "Daily Trading Report",
        "description": "Generate and distribute daily trading report",
        "steps": [
            {
                "name": "gather_data",
                "type": "mcp_call",
                "data": {
                    "server": "alpaca-trading",
                    "tool": "get_account",
                    "payload": {},
                },
            },
            {
                "name": "generate_report",
                "type": "workflow",
                "data": {
                    "type": "report_generation",
                    "report_type": "daily",
                    "recipients": ["trader@example.com"],
                },
            },
            {
                "name": "approve_report",
                "type": "approval",
                "data": {
                    "approval_type": "report_review",
                    "priority": "high",
                    "timeout_seconds": 1800,
                },
                "requires_approval": True,
                "approval": {"type": "manual", "priority": "high"},
            },
            {
                "name": "send_report",
                "type": "mcp_call",
                "data": {
                    "server": "gmail",
                    "tool": "send_email",
                    "payload": {
                        "to": ["trader@example.com"],
                        "subject": "Daily Trading Report",
                        "body": "Please find attached the daily trading report.",
                        "attachments": ["{previous_step.report_path}"],
                    },
                },
            },
        ],
    }

    result = await orchestrator.execute_workflow(workflow)
    print(f"Report workflow completed: {result['status']}")
    return result


async def example_trading_workflow():
    """Example: Multi-step trading workflow with approval gates."""
    orchestrator = WorkflowOrchestrator()

    workflow = {
        "name": "High-Value Trade Execution",
        "description": "Execute high-value trade with approval gates",
        "steps": [
            {
                "name": "analyze_market",
                "type": "mcp_call",
                "data": {
                    "server": "openrouter",
                    "tool": "detailed_sentiment",
                    "payload": {"market_data": {"symbol": "SPY"}, "news": []},
                },
            },
            {
                "name": "request_approval",
                "type": "approval",
                "data": {
                    "approval_type": "trade",
                    "context": {
                        "symbol": "SPY",
                        "trade_value": 5000.0,
                        "action": "BUY",
                    },
                    "priority": "high",
                },
                "requires_approval": True,
                "approval": {
                    "type": "manual",
                    "priority": "high",
                    "timeout_seconds": 600,
                },
            },
            {
                "name": "execute_trade",
                "type": "mcp_call",
                "data": {
                    "server": "alpaca-trading",
                    "tool": "submit_order",
                    "payload": {
                        "symbol": "SPY",
                        "qty": 10,
                        "side": "buy",
                        "type": "market",
                    },
                },
            },
            {
                "name": "notify_execution",
                "type": "notification",
                "data": {
                    "message": "Trade executed: SPY BUY 10 shares",
                    "channels": ["slack", "email"],
                    "priority": "medium",
                    "type": "trade",
                    "context": {"symbol": "SPY", "side": "BUY", "quantity": 10},
                },
            },
        ],
    }

    result = await orchestrator.execute_workflow(workflow)
    print(f"Trading workflow completed: {result['status']}")
    return result


if __name__ == "__main__":
    print("Workflow Automation Examples")
    print("=" * 50)

    # Run examples
    asyncio.run(example_email_workflow())
    print()
    asyncio.run(example_report_workflow())
    print()
    asyncio.run(example_trading_workflow())
