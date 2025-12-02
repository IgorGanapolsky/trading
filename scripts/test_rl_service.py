#!/usr/bin/env python3
"""
Test script for RL Service integration.
Verifies RL_AGENT_KEY is loaded and can connect to cloud RL provider.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment
load_dotenv()

from src.ml.rl_service_client import RLServiceClient


def main():
    """Test RL service connection and basic operations."""
    print("=" * 80)
    print("🧪 RL SERVICE CONNECTION TEST")
    print("=" * 80)
    print()

    # Check environment variable
    rl_key = os.getenv("RL_AGENT_KEY")
    if not rl_key:
        print("❌ RL_AGENT_KEY not found in environment")
        print("   Make sure it's in your .env file")
        return 1

    print(f"✅ RL_AGENT_KEY loaded (length: {len(rl_key)})")
    print()

    # Test connection
    try:
        print("🔧 Initializing RL service client…")
        client = RLServiceClient(provider="vertex_ai")
        print("✅ Connected to RL service (Vertex AI RL)")
        print()

        # Test training job submission
        print("🚀 Starting training job: dqn_trading_v1")
        env_spec = {
            "name": "trading_environment",
            "state_space": "continuous",
            "action_space": "discrete",
            "actions": ["BUY", "SELL", "HOLD"],
            "state_dim": 10,  # Market indicators
            "reward_function": "profit_based",
        }

        job_info = client.start_training(
            env_spec=env_spec, algorithm="DQN", job_name="dqn_trading_v1"
        )

        print("✅ Training job submitted successfully")
        print(f"   Job ID: {job_info['job_id']}")
        print(f"   Status: {job_info['status']}")
        print(f"   Algorithm: {job_info['algorithm']}")
        print()

        print("🏁 Test completed successfully!")
        print()
        print("Next steps:")
        print("  1. Install Vertex AI SDK: pip install google-cloud-aiplatform")
        print("  2. Configure Google Cloud project and enable Vertex AI RL API")
        print("  3. Use RLServiceClient in your training scripts")

        return 0

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
