import json
import logging
import os
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RLMTask:
    """Task definition for RLM (Algorithm 1) execution."""

    id: str
    task_type: str  # e.g., "log_analysis", "trade_aggregation"
    query: str
    data_paths: list[str]


class RLMOrchestrator:
    """
    RLM (Recursive Language Model) Orchestrator.

    Implements the 'Algorithm 1' pattern:
    1. Plan (Decision: Code-First vs Reasoning-First)
    2. Zero Sub-call Execution (Pure Python logic over recursive LLM calls)
    3. Large-Scale Analysis (100x faster than traditional agentic loops)
    """

    def __init__(self, root_dir: str = "."):
        self.root = Path(root_dir)
        self.analysis_output_dir = self.root / "data/analysis"
        os.makedirs(self.analysis_output_dir, exist_ok=True)

    def execute_algorithm_1(self, task: RLMTask) -> dict[str, Any]:
        """
        Executes a task using the RLM Algorithm 1 pattern.
        """
        logger.info(f"🚀 Starting RLM Task {task.id}: {task.query}")

        # In a real RLM CLI (like the screenshot), the model would generate this code.
        # We are implementing the 'Native' RLM logic here.

        if task.task_type == "trade_aggregation":
            return self._run_zero_subcall_trade_aggregation(task.data_paths, task.id)

        return {"status": "error", "message": "Unknown task type"}

    def _run_zero_subcall_trade_aggregation(
        self, file_paths: list[str], task_id: str
    ) -> dict[str, Any]:
        """
        RLM Strategy: Pure Python aggregation (Zero Sub-calls).
        100x faster and cheaper than agentic data reading.
        """
        logger.info(f"🧠 RLM Plan: Aggregate {len(file_paths)} trade files via pure Python.")

        all_trades = []
        winning_tickers = []
        total_pnl = 0.0

        for path_str in file_paths:
            path = self.root / path_str
            if not path.exists():
                continue

            try:
                with open(path) as f:
                    trades = json.load(f)
                    if isinstance(trades, list):
                        all_trades.extend(trades)
                        for t in trades:
                            pnl = t.get("pnl", 0.0)
                            total_pnl += pnl
                            if pnl > 0:
                                winning_tickers.append(t.get("symbol"))
            except Exception as e:
                logger.error(f"Error reading {path}: {e}")

        # RLM-style summary (Zero sub-calls)
        ticker_counts = Counter(winning_tickers)
        top_winners = ticker_counts.most_common(5)

        result = {
            "total_trades": len(all_trades),
            "net_pnl": round(total_pnl, 2),
            "top_winning_tickers": top_winners,
            "methodology": "RLM Algorithm 1 (Zero Sub-calls)",
        }

        output_file = self.analysis_output_dir / f"rlm_summary_{task_id}.json"
        with open(output_file, "w") as f:
            json.dump(result, f, indent=2)

        logger.info(f"✅ RLM Analysis Complete. Summary at {output_file}")
        return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    orchestrator = RLMOrchestrator()

    # Example Task: Analyze paired closed trades (canonical ledger only)
    recent_trade_files = [
        "data/trades.json",
    ]

    task = RLMTask(
        id="weekly_performance_report",
        task_type="trade_aggregation",
        query="Analyze top winning tickers from the last 5 trading days.",
        data_paths=recent_trade_files,
    )

    summary = orchestrator.execute_algorithm_1(task)
    print(json.dumps(summary, indent=2))
