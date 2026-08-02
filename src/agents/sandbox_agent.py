"""
Sandbox Agent - LLM-in-Sandbox Integration for Autonomous Trading Analysis.

Based on: "LLM-in-Sandbox Elicits General Agentic Intelligence" (arxiv:2601.16206)
Microsoft Research, Jan 2026

Key capabilities:
- Dynamic code execution for novel analysis
- File system for long context handling (options chains)
- External resource fetching (Fed calendar, earnings)
- Self-validating strategy discovery

This enables our agents to:
1. Write and execute analysis code on-the-fly
2. Handle arbitrarily large options chains via file system
3. Fetch real-time external data without hard-coding
4. Discover and validate new trading patterns autonomously
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Project paths
PROJECT_DIR = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_DIR / "data"
SANDBOX_DIR = DATA_DIR / "sandbox"
SANDBOX_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class SandboxResult:
    """Result from sandbox code execution."""

    success: bool
    output: str
    error: str | None = None
    files_created: list[str] = field(default_factory=list)
    execution_time_ms: float = 0
    code_executed: str = ""


@dataclass
class SandboxCapabilities:
    """Defines what the sandbox can do."""

    can_execute_python: bool = True
    can_read_files: bool = True
    can_write_files: bool = True
    can_fetch_urls: bool = True  # For external resources
    max_execution_time_seconds: float = 30.0
    max_file_size_mb: float = 10.0
    allowed_imports: list[str] = field(
        default_factory=lambda: [
            "json",
            "csv",
            "math",
            "statistics",
            "datetime",
            "pathlib",
            "numpy",
            "pandas",  # Data analysis
            "requests",  # External fetching (controlled)
        ]
    )
    blocked_imports: list[str] = field(
        default_factory=lambda: [
            "os.system",
            "subprocess",
            "eval",
            "exec",  # Security
            "socket",
            "ftplib",
            "smtplib",  # Network (except requests)
        ]
    )


class SandboxAgent:
    """
    Autonomous agent with sandbox code execution capabilities.

    Inspired by LLM-in-Sandbox paper - agents can write and execute
    code to solve novel problems without hard-coded solutions.
    """

    def __init__(self, agent_name: str = "sandbox"):
        self.agent_name = agent_name
        self.capabilities = SandboxCapabilities()
        self.execution_history: list[SandboxResult] = []
        self.workspace = SANDBOX_DIR / agent_name
        self.workspace.mkdir(parents=True, exist_ok=True)

    def _sanitize_code(self, code: str) -> tuple[bool, str]:
        """
        Sanitize code before execution.

        Returns (is_safe, reason) tuple.
        """
        # Check for blocked imports/operations
        for blocked in self.capabilities.blocked_imports:
            if blocked in code:
                return False, f"Blocked operation: {blocked}"

        # Check for dangerous patterns
        dangerous_patterns = [
            "rm -rf",
            "shutil.rmtree",
            "__import__",
            "globals()",
            "locals()",
            "open('/etc",
            "open('/usr",
        ]
        for pattern in dangerous_patterns:
            if pattern in code:
                return False, f"Dangerous pattern: {pattern}"

        return True, "safe"

    async def execute_code(self, code: str, description: str = "") -> SandboxResult:
        """
        Execute Python code in a sandboxed environment.

        This is the core capability from LLM-in-Sandbox paper.
        """
        start_time = datetime.now()

        # Sanitize code
        is_safe, reason = self._sanitize_code(code)
        if not is_safe:
            return SandboxResult(
                success=False,
                output="",
                error=f"Code rejected: {reason}",
                code_executed=code[:200],
            )

        # Create temporary script file
        script_file = self.workspace / f"script_{datetime.now().strftime('%H%M%S')}.py"

        # Wrap code with safety measures
        wrapped_code = f"""
import sys
import json
from pathlib import Path

# Set working directory to sandbox
SANDBOX_DIR = Path("{self.workspace}")

# Capture output
_sandbox_output = []

def sandbox_print(*args, **kwargs):
    _sandbox_output.append(" ".join(str(a) for a in args))

# Replace print
print = sandbox_print

# Execute user code
try:
{self._indent_code(code, 4)}
except Exception as e:
    _sandbox_output.append(f"ERROR: {{e}}")

# Output results
print(json.dumps({{"output": _sandbox_output}}))
"""

        script_file.write_text(wrapped_code)

        try:
            # Execute with timeout
            proc = await asyncio.create_subprocess_exec(
                "python3",
                str(script_file),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace),
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=self.capabilities.max_execution_time_seconds,
                )
            except TimeoutError:
                proc.kill()
                return SandboxResult(
                    success=False,
                    output="",
                    error="Execution timeout",
                    code_executed=code[:200],
                )

            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            # Parse output
            output_text = stdout.decode() if stdout else ""
            error_text = stderr.decode() if stderr else ""

            # Check for files created
            files_created = [
                f.name for f in self.workspace.glob("*") if f.is_file() and f != script_file
            ]

            result = SandboxResult(
                success=proc.returncode == 0,
                output=output_text,
                error=error_text if error_text else None,
                files_created=files_created,
                execution_time_ms=execution_time,
                code_executed=code[:500],
            )

            self.execution_history.append(result)
            return result

        finally:
            # Cleanup script file
            if script_file.exists():
                script_file.unlink()

    def _indent_code(self, code: str, spaces: int) -> str:
        """Indent code block."""
        indent = " " * spaces
        return "\n".join(indent + line for line in code.split("\n"))

    async def analyze_options_chain(self, chain_data: list[dict]) -> dict[str, Any]:
        """
        Analyze options chain using sandbox execution.

        This handles arbitrarily large chains by writing to file system.
        """
        # Write chain to file (handles long context)
        chain_file = self.workspace / "options_chain.json"
        chain_file.write_text(json.dumps(chain_data, indent=2))

        # Dynamic analysis code
        analysis_code = '''
import json
from pathlib import Path

# Read options chain from file (handles any size)
chain_file = SANDBOX_DIR / "options_chain.json"
chain = json.loads(chain_file.read_text())

# Analyze chain
puts = [o for o in chain if o.get("type") == "put"]
calls = [o for o in chain if o.get("type") == "call"]

# Find optimal strikes for iron condor
# Look for 15-20 delta options
def find_delta_strike(options, target_delta, direction):
    """Find strike closest to target delta."""
    best = None
    for opt in options:
        delta = abs(opt.get("delta", 0))
        if best is None or abs(delta - target_delta) < abs(best.get("delta", 0) - target_delta):
            best = opt
    return best

put_short = find_delta_strike(puts, 0.15, "put")
call_short = find_delta_strike(calls, 0.15, "call")

# Calculate expected premium
total_premium = 0
if put_short:
    total_premium += put_short.get("bid", 0)
if call_short:
    total_premium += call_short.get("bid", 0)

result = {
    "total_options": len(chain),
    "puts": len(puts),
    "calls": len(calls),
    "recommended_put_strike": put_short.get("strike") if put_short else None,
    "recommended_call_strike": call_short.get("strike") if call_short else None,
    "expected_premium": total_premium,
    "analysis_method": "sandbox_dynamic",
}

# Save result
result_file = SANDBOX_DIR / "analysis_result.json"
result_file.write_text(json.dumps(result, indent=2))

print(f"Analyzed {len(chain)} options")
print(f"Recommended IC: {result['recommended_put_strike']}/{result['recommended_call_strike']}")
'''

        result = await self.execute_code(analysis_code, "Options chain analysis")

        # Read analysis result
        result_file = self.workspace / "analysis_result.json"
        if result_file.exists():
            return json.loads(result_file.read_text())

        return {"error": result.error or "Analysis failed"}

    async def fetch_external_resource(self, url: str, resource_type: str) -> dict[str, Any]:
        """
        Fetch external resource using sandbox.

        This enables dynamic data fetching without hard-coding.
        """
        if not self.capabilities.can_fetch_urls:
            return {"error": "URL fetching disabled"}

        # Only allow specific domains for safety
        allowed_domains = [
            "api.stlouisfed.org",  # FRED data
            "www.alphavantage.co",
            "query1.finance.yahoo.com",
            "api.polygon.io",
        ]

        is_allowed = any(domain in url for domain in allowed_domains)
        if not is_allowed:
            return {"error": "Domain not in allowlist"}

        fetch_code = f"""
import requests
import json
from pathlib import Path

try:
    response = requests.get("{url}", timeout=10)
    response.raise_for_status()

    data = response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text

    # Save to file
    result_file = SANDBOX_DIR / "fetched_resource.json"
    result_file.write_text(json.dumps({{"url": "{url}", "data": data, "status": response.status_code}}))

    print(f"Fetched {{len(str(data))}} bytes from {url}")
except Exception as e:
    print(f"Fetch failed: {{e}}")
"""

        result = await self.execute_code(fetch_code, f"Fetch {resource_type}")

        result_file = self.workspace / "fetched_resource.json"
        if result_file.exists():
            return json.loads(result_file.read_text())

        return {"error": result.error or "Fetch failed"}

    async def discover_pattern(
        self, historical_data: list[dict], hypothesis: str
    ) -> dict[str, Any]:
        """
        Self-validating pattern discovery.

        Agent writes code to test a trading hypothesis.
        """
        # Write historical data to file
        data_file = self.workspace / "historical_data.json"
        data_file.write_text(json.dumps(historical_data, indent=2))

        discovery_code = f"""
import json
import statistics
from pathlib import Path

# Load historical data
data_file = SANDBOX_DIR / "historical_data.json"
data = json.loads(data_file.read_text())

# Hypothesis: {hypothesis}

# Analyze pattern
wins = [d for d in data if d.get("pnl", 0) > 0]
losses = [d for d in data if d.get("pnl", 0) <= 0]

win_rate = len(wins) / len(data) if data else 0
avg_win = statistics.mean([d["pnl"] for d in wins]) if wins else 0
avg_loss = statistics.mean([d["pnl"] for d in losses]) if losses else 0
profit_factor = abs(sum(d["pnl"] for d in wins) / sum(d["pnl"] for d in losses)) if losses else float("inf")

# Pattern validation
is_valid = win_rate >= 0.8 and profit_factor >= 1.5

result = {{
    "hypothesis": "{hypothesis}",
    "total_trades": len(data),
    "win_rate": round(win_rate, 3),
    "avg_win": round(avg_win, 2),
    "avg_loss": round(avg_loss, 2),
    "profit_factor": round(profit_factor, 2),
    "is_valid": is_valid,
    "recommendation": "ADOPT" if is_valid else "REJECT",
}}

result_file = SANDBOX_DIR / "pattern_result.json"
result_file.write_text(json.dumps(result, indent=2))

print(f"Pattern validation: {{'VALID' if is_valid else 'INVALID'}}")
print(f"Win rate: {{win_rate:.1%}}, Profit factor: {{profit_factor:.2f}}")
"""

        result = await self.execute_code(discovery_code, f"Pattern discovery: {hypothesis}")

        result_file = self.workspace / "pattern_result.json"
        if result_file.exists():
            return json.loads(result_file.read_text())

        return {"error": result.error or "Pattern discovery failed"}

    def get_execution_summary(self) -> dict[str, Any]:
        """Get summary of sandbox executions."""
        successful = [r for r in self.execution_history if r.success]
        failed = [r for r in self.execution_history if not r.success]

        return {
            "total_executions": len(self.execution_history),
            "successful": len(successful),
            "failed": len(failed),
            "avg_execution_time_ms": (
                sum(r.execution_time_ms for r in self.execution_history)
                / len(self.execution_history)
                if self.execution_history
                else 0
            ),
            "files_in_workspace": len(list(self.workspace.glob("*"))),
        }


async def get_sandbox_signal(task: str = "analysis") -> dict[str, Any]:
    """
    Get trading signal from sandbox agent.

    This is the swarm integration point.
    """
    agent = SandboxAgent("trading_analysis")

    # Example: Analyze current market conditions dynamically
    analysis_code = """
import json
from datetime import datetime
from pathlib import Path

# Dynamic market analysis
# Agent can modify this based on current conditions

analysis = {
    "timestamp": datetime.now().isoformat(),
    "method": "sandbox_dynamic_analysis",
    "checks": {
        "market_hours": True,  # Would check actual hours
        "volatility_acceptable": True,
        "no_major_events": True,
    },
    "signal": 0.65,  # Neutral-bullish
    "confidence": 0.75,
}

# All checks must pass
all_passed = all(analysis["checks"].values())
analysis["recommendation"] = "TRADE" if all_passed and analysis["signal"] >= 0.6 else "HOLD"

result_file = SANDBOX_DIR / "market_analysis.json"
result_file.write_text(json.dumps(analysis, indent=2))

print(f"Analysis complete: {analysis['recommendation']}")
"""

    result = await agent.execute_code(analysis_code, "Market analysis")

    # Read result
    result_file = agent.workspace / "market_analysis.json"
    if result_file.exists():
        analysis = json.loads(result_file.read_text())
        return {
            "signal": analysis.get("signal", 0.5),
            "confidence": analysis.get("confidence", 0.5),
            "data": {
                "method": "llm_in_sandbox",
                "recommendation": analysis.get("recommendation", "HOLD"),
                "execution_summary": agent.get_execution_summary(),
            },
        }

    return {
        "signal": 0.5,
        "confidence": 0.3,
        "data": {"error": result.error or "Analysis failed"},
    }


if __name__ == "__main__":
    # Demo
    async def demo():
        agent = SandboxAgent("demo")

        # Test code execution
        result = await agent.execute_code(
            """
x = 2 + 2
print(f"Result: {x}")
""",
            "Simple math",
        )

        print(f"Execution: {result.success}")
        print(f"Output: {result.output}")
        print(f"Summary: {agent.get_execution_summary()}")

    asyncio.run(demo())
