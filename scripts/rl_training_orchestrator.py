#!/usr/bin/env python3
"""
Unified RL Training Orchestrator

Supports training across multiple platforms:
1. Local Machine (fast, free, GPU support)
2. LangSmith (monitoring, experiment tracking)
3. GitHub Actions (automated, scheduled)
4. Vertex AI (cloud GPU training with experiment tracking)

Usage:
  # Local training
  python scripts/rl_training_orchestrator.py --platform local

  # LangSmith training
  python scripts/rl_training_orchestrator.py --platform langsmith

  # Vertex AI training (PPO on cloud GPU)
  python scripts/rl_training_orchestrator.py --platform vertex_ai --agents ppo

  # GitHub Actions (via workflow)
  # Just enable model-training.yml workflow
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.dashboard_metrics import load_json_file

DATA_DIR = Path("data")


class RLTrainingOrchestrator:
    """Unified orchestrator for RL training across platforms."""

    def __init__(self, platform: str = "local"):
        self.platform = platform
        self.results = {
            "platform": platform,
            "timestamp": datetime.now().isoformat(),
            "agents": {},
            "errors": [],
        }

    def train_q_learning(self) -> dict[str, Any]:
        """Train Q-learning agent."""
        try:
            from src.agents.reinforcement_learning_optimized import (
                OptimizedRLPolicyLearner,
            )

            rl_state_file = DATA_DIR / "rl_policy_state.json"
            if not rl_state_file.exists():
                return {
                    "success": True,
                    "message": "No RL state file found - agent will initialize on first trade (Skipped)",
                    "agent": "q_learning",
                }

            agent = OptimizedRLPolicyLearner()

            if agent.enable_replay and len(agent.replay_buffer) >= agent.replay_batch_size:
                training_iterations = min(20, len(agent.replay_buffer) // agent.replay_batch_size)
                total_updates = 0

                for _ in range(training_iterations):
                    agent._train_from_replay()
                    total_updates += 1

                agent._save_state()

                return {
                    "success": True,
                    "agent": "q_learning",
                    "training_iterations": total_updates,
                    "replay_buffer_size": len(agent.replay_buffer),
                    "message": f"Trained Q-learning agent: {total_updates} iterations",
                }
            else:
                return {
                    "success": True,
                    "agent": "q_learning",
                    "training_iterations": 0,
                    "replay_buffer_size": len(agent.replay_buffer),
                    "message": f"Replay buffer has {len(agent.replay_buffer)} samples (need {agent.replay_batch_size})",
                }
        except Exception as e:
            error_msg = f"Q-learning training failed: {e}"
            self.results["errors"].append(error_msg)
            return {
                "success": False,
                "agent": "q_learning",
                "error": str(e),
                "message": error_msg,
            }

    def train_dqn(self, device: str = "cpu", episodes: int = 10) -> dict[str, Any]:
        """Train DQN agent."""
        try:
            from src.ml.dqn_agent import DQNAgent

            all_trades = []
            trade_files = list(DATA_DIR.glob("trades_*.json"))
            for trade_file in trade_files:
                trades = load_json_file(trade_file)
                if isinstance(trades, list):
                    all_trades.extend(trades)

            if len(all_trades) < 32:
                return {
                    "success": True,
                    "agent": "dqn",
                    "message": f"Insufficient trade data: {len(all_trades)} trades (need 32+) (Skipped)",
                }

            model_path = DATA_DIR / "models" / "dqn_agent.pt"
            if model_path.exists():
                agent = DQNAgent.load(str(model_path))
            else:
                return {
                    "success": True,
                    "agent": "dqn",
                    "message": "DQN agent not initialized - need to configure input/output dimensions (Skipped)",
                }

            total_loss = 0.0
            training_steps = 0

            for _episode in range(episodes):
                loss = agent.train_step()
                if loss is not None:
                    total_loss += loss
                    training_steps += 1

            if training_steps > 0:
                agent.save(str(model_path))
                avg_loss = total_loss / training_steps

                return {
                    "success": True,
                    "agent": "dqn",
                    "episodes": episodes,
                    "training_steps": training_steps,
                    "avg_loss": avg_loss,
                    "message": f"Trained DQN agent: {training_steps} steps, avg loss: {avg_loss:.4f}",
                }
            else:
                return {
                    "success": False,
                    "agent": "dqn",
                    "message": "No training occurred - insufficient samples in replay buffer",
                }
        except Exception as e:
            error_msg = f"DQN training failed: {e}"
            self.results["errors"].append(error_msg)
            return {
                "success": False,
                "agent": "dqn",
                "error": str(e),
                "message": error_msg,
            }

    def train_with_langsmith(self, agent_type: str) -> dict[str, Any]:
        """Train agent with LangSmith monitoring."""
        try:
            # Check if LangSmith is configured
            langsmith_api_key = os.getenv("LANGCHAIN_API_KEY")
            if not langsmith_api_key:
                return {
                    "success": False,
                    "agent": agent_type,
                    "message": "LangSmith not configured - set LANGCHAIN_API_KEY environment variable",
                }

            # Set up LangSmith tracing
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            os.environ["LANGCHAIN_PROJECT"] = "trading-rl-training"

            from langsmith import Client

            Client(api_key=langsmith_api_key)

            # Train the agent (LangSmith will auto-trace via wrapper)
            try:
                if agent_type == "q_learning":
                    result = self.train_q_learning()
                elif agent_type == "dqn":
                    result = self.train_dqn()
                else:
                    result = {
                        "success": False,
                        "message": f"Unknown agent type: {agent_type}",
                    }

                # LangSmith automatically traces via wrapper - no manual run creation needed
                return result
            except Exception:
                raise
        except Exception as e:
            error_msg = f"LangSmith training failed: {e}"
            self.results["errors"].append(error_msg)
            return {
                "success": False,
                "agent": agent_type,
                "error": str(e),
                "message": error_msg,
            }

    def train_with_vertex_ai(
        self,
        symbol: str = "SPY",
        algorithm: str = "PPO",
        hyperparameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Train RL agent on Vertex AI with LangSmith experiment tracking.

        Args:
            symbol: Trading symbol to train on
            algorithm: RL algorithm (PPO, DQN, A2C)
            hyperparameters: Optional hyperparameters override

        Returns:
            Training job information
        """
        try:
            from src.ml.langsmith_rl_tracker import RLExperimentTracker
            from src.ml.rl_service_client import RLServiceClient

            # Initialize clients
            rl_client = RLServiceClient(provider="vertex_ai", enable_langsmith=True)
            experiment_tracker = RLExperimentTracker(project_name="trading-rl-training")

            # Create experiment in LangSmith
            experiment_name = (
                f"{algorithm.lower()}_{symbol.lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            experiment_id = experiment_tracker.create_experiment(
                name=experiment_name,
                algorithm=algorithm,
                description=f"Vertex AI {algorithm} training for {symbol}",
                hyperparameters=hyperparameters or {},
            )

            # Prepare environment specification
            env_spec = {
                "name": f"trading_env_{symbol.lower()}",
                "symbol": symbol,
                "state_dim": 10,
                "action_space": "discrete",
                "actions": ["HOLD", "BUY", "SELL"],
            }

            # Submit training job to Vertex AI
            job_info = rl_client.start_training(
                env_spec=env_spec,
                algorithm=algorithm,
                hyperparameters=hyperparameters,
            )

            # Log training start to LangSmith
            if experiment_id:
                experiment_tracker.log_training_start(
                    experiment_id=experiment_id,
                    config={
                        "platform": "vertex_ai",
                        "symbol": symbol,
                        "algorithm": algorithm,
                        "job_id": job_info.get("job_id"),
                        "hyperparameters": hyperparameters or {},
                    },
                )

            return {
                "success": True,
                "agent": algorithm.lower(),
                "platform": "vertex_ai",
                "job_id": job_info.get("job_id"),
                "experiment_id": experiment_id,
                "experiment_name": experiment_name,
                "status": job_info.get("status", "submitted"),
                "console_url": job_info.get("console_url"),
                "message": f"Vertex AI {algorithm} training job submitted for {symbol}",
            }

        except ImportError as e:
            error_msg = f"Vertex AI dependencies not installed: {e}"
            self.results["errors"].append(error_msg)
            return {
                "success": False,
                "agent": algorithm.lower(),
                "platform": "vertex_ai",
                "error": str(e),
                "message": error_msg,
            }
        except Exception as e:
            error_msg = f"Vertex AI training failed: {e}"
            self.results["errors"].append(error_msg)
            return {
                "success": False,
                "agent": algorithm.lower(),
                "platform": "vertex_ai",
                "error": str(e),
                "message": error_msg,
            }

    def check_vertex_ai_job(self, job_id: str) -> dict[str, Any]:
        """Check status of a Vertex AI training job."""
        try:
            from src.ml.rl_service_client import RLServiceClient

            rl_client = RLServiceClient(provider="vertex_ai")
            status = rl_client.get_job_status(job_id)
            return status
        except Exception as e:
            return {"job_id": job_id, "status": "error", "error": str(e)}

    def train_all(
        self,
        agents: list[str],
        device: str = "cpu",
        use_langsmith: bool = False,
        symbol: str = "SPY",
    ) -> dict[str, Any]:
        """Train all specified agents."""
        for agent in agents:
            if agent == "q_learning":
                if use_langsmith:
                    self.results["agents"]["q_learning"] = self.train_with_langsmith("q_learning")
                else:
                    self.results["agents"]["q_learning"] = self.train_q_learning()

            elif agent == "dqn":
                if use_langsmith:
                    self.results["agents"]["dqn"] = self.train_with_langsmith("dqn")
                else:
                    self.results["agents"]["dqn"] = self.train_dqn(device=device)

            elif agent == "ppo":
                # PPO training via Vertex AI with LangSmith tracking
                if self.platform == "vertex_ai":
                    self.results["agents"]["ppo"] = self.train_with_vertex_ai(
                        symbol=symbol,
                        algorithm="PPO",
                    )
                else:
                    self.results["agents"]["ppo"] = {
                        "success": False,
                        "agent": "ppo",
                        "message": "PPO training requires Vertex AI - use --platform vertex_ai",
                    }

            elif agent == "a2c":
                # A2C training via Vertex AI
                if self.platform == "vertex_ai":
                    self.results["agents"]["a2c"] = self.train_with_vertex_ai(
                        symbol=symbol,
                        algorithm="A2C",
                    )
                else:
                    self.results["agents"]["a2c"] = {
                        "success": False,
                        "agent": "a2c",
                        "message": "A2C training requires Vertex AI - use --platform vertex_ai",
                    }

        # Calculate summary
        successful = sum(1 for r in self.results["agents"].values() if r.get("success", False))
        total = len(self.results["agents"])

        self.results["summary"] = {
            "successful": successful,
            "total": total,
            "success_rate": successful / total if total > 0 else 0.0,
            "platform": self.platform,
        }

        return self.results

    def save_results(self) -> Path:
        """Save training results to file."""
        results_file = DATA_DIR / "rl_training_log.json"

        if results_file.exists():
            with open(results_file) as f:
                log = json.load(f)
        else:
            log = []

        log.append(self.results)

        # Keep only last 200 entries
        if len(log) > 200:
            log = log[-200:]

        with open(results_file, "w") as f:
            json.dump(log, f, indent=2)

        return results_file


def main():
    parser = argparse.ArgumentParser(description="Unified RL Training Orchestrator")
    parser.add_argument(
        "--platform",
        type=str,
        default="local",
        choices=["local", "langsmith", "github", "vertex_ai"],
        help="Platform to train on (default: local)",
    )
    parser.add_argument(
        "--agents",
        type=str,
        default="q_learning",
        help="Comma-separated list of agents: q_learning,dqn,ppo,a2c,all (default: q_learning)",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cpu",
        choices=["cpu", "cuda"],
        help="Device for deep RL (default: cpu)",
    )
    parser.add_argument(
        "--use-langsmith",
        action="store_true",
        help="Enable LangSmith monitoring (requires LANGCHAIN_API_KEY)",
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default="SPY",
        help="Trading symbol for Vertex AI training (default: SPY)",
    )

    args = parser.parse_args()

    agents = [a.strip() for a in args.agents.split(",")]
    if "all" in agents:
        agents = ["q_learning", "dqn"]
        if args.platform == "vertex_ai":
            agents.extend(["ppo", "a2c"])

    print("=" * 70)
    print("RL TRAINING ORCHESTRATOR")
    print("=" * 70)
    print(f"Platform: {args.platform}")
    print(f"Agents: {', '.join(agents)}")
    print(f"Device: {args.device}")
    print(f"Symbol: {args.symbol}")
    print(f"LangSmith: {'Enabled' if args.use_langsmith else 'Disabled'}")
    print("=" * 70)
    print()

    orchestrator = RLTrainingOrchestrator(platform=args.platform)
    results = orchestrator.train_all(
        agents, device=args.device, use_langsmith=args.use_langsmith, symbol=args.symbol
    )

    # Print results
    print("\n📊 Training Results:")
    print("-" * 70)
    for agent_name, result in results["agents"].items():
        status = "✅" if result.get("success", False) else "❌"
        print(f"{status} {agent_name}: {result.get('message', 'Unknown')}")

    if results.get("errors"):
        print("\n⚠️ Errors:")
        for error in results["errors"]:
            print(f"  - {error}")

    print(
        f"\n📈 Summary: {results['summary']['successful']}/{results['summary']['total']} agents trained successfully"
    )

    # Save results
    results_file = orchestrator.save_results()
    print(f"\n✅ Results saved to {results_file}")

    return 0 if results["summary"]["success_rate"] > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
