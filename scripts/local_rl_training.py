#!/usr/bin/env python3
"""
Local RL Training Script

Runs RL training more frequently on your local machine.
Now uses unified orchestrator supporting Local, LangSmith, and GitHub Actions.

Why local?
- Faster than GitHub Actions (no CI overhead)
- Cheaper (no compute costs)
- Can use GPU if available
- More frequent training = better RL performance

Usage:
  # Run once (immediate training)
  python scripts/local_rl_training.py

  # Run continuously (every 2 hours)
  python scripts/local_rl_training.py --continuous --interval 7200

  # Use GPU if available
  python scripts/local_rl_training.py --device cuda

  # Train specific RL agents
  python scripts/local_rl_training.py --agents dqn,ppo

  # Enable LangSmith monitoring
  python scripts/local_rl_training.py --use-langsmith
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.rl_training_orchestrator import RLTrainingOrchestrator

DATA_DIR = Path("data")


def load_json_file(filepath: Path) -> Any:
    """Load JSON file and return contents."""
    with open(filepath) as f:
        return json.load(f)


def train_q_learning_agent() -> dict[str, Any]:
    """Train Q-learning agent from experience replay buffer."""
    try:
        from src.agents.reinforcement_learning_optimized import OptimizedRLPolicyLearner

        # Load RL state
        rl_state_file = DATA_DIR / "rl_policy_state.json"
        if not rl_state_file.exists():
            return {
                "success": False,
                "message": "No RL state file found - agent will initialize on first trade",
                "agent": "q_learning",
            }

        # Initialize agent (will load state)
        agent = OptimizedRLPolicyLearner()

        # Train from replay buffer if it has enough samples
        if agent.enable_replay and len(agent.replay_buffer) >= agent.replay_batch_size:
            # Run multiple training iterations
            training_iterations = min(10, len(agent.replay_buffer) // agent.replay_batch_size)
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
        return {
            "success": False,
            "agent": "q_learning",
            "error": str(e),
            "message": f"Q-learning training failed: {e}",
        }


def train_all_agents_legacy(agents: list[str], device: str = "cpu") -> dict[str, Any]:
    """Train Q-learning agent from experience replay buffer."""
    try:
        from src.agents.reinforcement_learning_optimized import OptimizedRLPolicyLearner

        # Load RL state
        rl_state_file = DATA_DIR / "rl_policy_state.json"
        if not rl_state_file.exists():
            return {
                "success": False,
                "message": "No RL state file found - agent will initialize on first trade",
                "agent": "q_learning",
            }

        # Initialize agent (will load state)
        agent = OptimizedRLPolicyLearner()

        # Train from replay buffer if it has enough samples
        if agent.enable_replay and len(agent.replay_buffer) >= agent.replay_batch_size:
            # Run multiple training iterations
            training_iterations = min(10, len(agent.replay_buffer) // agent.replay_batch_size)
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
        return {
            "success": False,
            "agent": "q_learning",
            "error": str(e),
            "message": f"Q-learning training failed: {e}",
        }


def train_dqn_agent(device: str = "cpu", episodes: int = 10) -> dict[str, Any]:
    """Train DQN agent."""
    try:
        from src.ml.dqn_agent import DQNAgent

        # Check if we have enough trade data
        all_trades = []
        trade_files = list(DATA_DIR.glob("trades_*.json"))
        for trade_file in trade_files:
            trades = load_json_file(trade_file)
            if isinstance(trades, list):
                all_trades.extend(trades)

        if len(all_trades) < 32:  # Need at least batch_size samples
            return {
                "success": False,
                "agent": "dqn",
                "message": f"Insufficient trade data: {len(all_trades)} trades (need 32+)",
            }

        # Load or create DQN agent
        model_path = DATA_DIR / "models" / "dqn_agent.pt"
        if model_path.exists():
            # Load existing agent
            agent = DQNAgent.load(str(model_path))
        else:
            # Create new agent (would need to configure input/output dims)
            return {
                "success": False,
                "agent": "dqn",
                "message": "DQN agent not initialized - need to configure input/output dimensions",
            }

        # Train for specified episodes
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
        return {
            "success": False,
            "agent": "dqn",
            "error": str(e),
            "message": f"DQN training failed: {e}",
        }


def train_ppo_agent(device: str = "cpu", episodes: int = 5) -> dict[str, Any]:
    """Train PPO agent."""
    try:
        # Check if we have enough trade data
        all_trades = []
        trade_files = list(DATA_DIR.glob("trades_*.json"))
        for trade_file in trade_files:
            trades = load_json_file(trade_file)
            if isinstance(trades, list):
                all_trades.extend(trades)

        if len(all_trades) < 64:  # Need at least batch_size samples
            return {
                "success": False,
                "agent": "ppo",
                "message": f"Insufficient trade data: {len(all_trades)} trades (need 64+)",
            }

        # Load or create PPO model
        DATA_DIR / "models" / "ppo_agent.pt"

        # For now, return not implemented (would need full environment setup)
        return {
            "success": False,
            "agent": "ppo",
            "message": "PPO training requires full environment setup - use model-training.yml workflow",
        }
    except Exception as e:
        return {
            "success": False,
            "agent": "ppo",
            "error": str(e),
            "message": f"PPO training failed: {e}",
        }


def train_all_agents(agents: list[str], device: str = "cpu") -> dict[str, Any]:
    """Train all specified RL agents."""
    results = {"timestamp": datetime.now().isoformat(), "device": device, "agents": {}}

    if "q_learning" in agents or "all" in agents:
        results["agents"]["q_learning"] = train_q_learning_agent()

    if "dqn" in agents or "all" in agents:
        results["agents"]["dqn"] = train_dqn_agent(device=device)

    if "ppo" in agents or "all" in agents:
        results["agents"]["ppo"] = train_ppo_agent(device=device)

    # Summary
    successful = sum(1 for r in results["agents"].values() if r.get("success", False))
    total = len(results["agents"])

    results["summary"] = {
        "successful": successful,
        "total": total,
        "success_rate": successful / total if total > 0 else 0.0,
    }

    return results


def main():
    parser = argparse.ArgumentParser(description="Local RL Training Script")
    parser.add_argument(
        "--agents",
        type=str,
        default="q_learning",
        help="Comma-separated list of agents to train: q_learning,dqn,ppo,all (default: q_learning)",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cpu",
        choices=["cpu", "cuda"],
        help="Device to use for training (default: cpu)",
    )
    parser.add_argument("--continuous", action="store_true", help="Run continuously in a loop")
    parser.add_argument(
        "--interval",
        type=int,
        default=7200,
        help="Interval in seconds for continuous mode (default: 7200 = 2 hours)",
    )
    parser.add_argument(
        "--episodes",
        type=int,
        default=10,
        help="Number of training episodes for deep RL agents (default: 10)",
    )
    parser.add_argument(
        "--use-langsmith",
        action="store_true",
        help="Enable LangSmith monitoring (requires LANGCHAIN_API_KEY)",
    )

    args = parser.parse_args()

    agents = [a.strip() for a in args.agents.split(",")]
    if "all" in agents:
        agents = ["q_learning", "dqn"]

    print("=" * 70)
    print("LOCAL RL TRAINING")
    print("=" * 70)
    print(f"Agents: {', '.join(agents)}")
    print(f"Device: {args.device}")
    print(f"Mode: {'Continuous' if args.continuous else 'Single Run'}")
    print(f"LangSmith: {'Enabled' if args.use_langsmith else 'Disabled'}")
    if args.continuous:
        print(f"Interval: {args.interval} seconds ({args.interval / 3600:.1f} hours)")
    print("=" * 70)
    print()

    if args.continuous:
        print(f"🔄 Running continuously (every {args.interval / 3600:.1f} hours)")
        print("   Press Ctrl+C to stop")
        print()

        iteration = 0
        try:
            while True:
                iteration += 1
                print(f"\n{'=' * 70}")
                print(
                    f"Training Iteration #{iteration} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                print(f"{'=' * 70}\n")

                orchestrator = RLTrainingOrchestrator(platform="local")
                results = orchestrator.train_all(
                    agents, device=args.device, use_langsmith=args.use_langsmith
                )
                orchestrator.save_results()

                # Print results
                for agent_name, result in results["agents"].items():
                    status = "✅" if result.get("success", False) else "❌"
                    print(f"{status} {agent_name}: {result.get('message', 'Unknown')}")

                print(
                    f"\n📊 Summary: {results['summary']['successful']}/{results['summary']['total']} agents trained successfully"
                )

                # Results already saved by orchestrator

                print(f"\n⏰ Next training in {args.interval / 3600:.1f} hours...")
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n\n🛑 Training stopped by user")
    else:
        # Single run
        orchestrator = RLTrainingOrchestrator(platform="local")
        results = orchestrator.train_all(
            agents, device=args.device, use_langsmith=args.use_langsmith
        )
        orchestrator.save_results()

        # Print results
        print("\n📊 Training Results:")
        print("-" * 70)
        for agent_name, result in results["agents"].items():
            status = "✅" if result.get("success", False) else "❌"
            print(f"{status} {agent_name}:")
            for key, value in result.items():
                if key not in ["success", "agent"]:
                    print(f"   {key}: {value}")
            print()

        print(
            f"Summary: {results['summary']['successful']}/{results['summary']['total']} agents trained successfully"
        )

        # Results already saved by orchestrator
        results_file = DATA_DIR / "rl_training_log.json"
        print(f"\n✅ Results saved to {results_file}")


if __name__ == "__main__":
    main()
