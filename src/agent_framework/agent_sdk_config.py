"""
Claude Agent SDK Configuration

Implements the new Agent SDK features announced December 2025:
1. 1M Context Windows - Enable 5x larger context for full codebase awareness
2. Sandboxing Configuration - Secure code execution
3. SDK V2 Integration - Modern agent interfaces

Reference: https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ContextWindowSize(Enum):
    """Available context window sizes"""

    STANDARD = 200_000  # Standard Claude context
    EXTENDED_1M = 1_000_000  # 1M context beta (requires Tier 4 or custom limits)


class EffortLevel(Enum):
    """
    Effort levels for Claude Opus 4.5 optimization.

    Based on Anthropic's effort parameter documentation:
    - LOW: Quick lookups, simple classification, high-volume tasks
    - MEDIUM: Standard analysis, balanced speed/quality (default)
    - HIGH: Complex reasoning, architectural decisions, critical trades

    Reference: https://platform.claude.com/docs/en/build-with-claude/effort
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class EffortConfig:
    """
    Configuration for effort-based model selection and token limits.

    Opus 4.5 uses 67% fewer tokens for the same work when effort is optimized.
    """

    level: EffortLevel = EffortLevel.MEDIUM

    # Token limits per effort level
    max_tokens: int = 2000

    # Temperature (lower for deterministic, higher for creative)
    temperature: float = 0.7

    # Model selection based on effort (can be overridden)
    # LOW -> Haiku, MEDIUM -> Sonnet, HIGH -> Opus
    use_model_escalation: bool = True

    @classmethod
    def for_level(cls, level: EffortLevel) -> EffortConfig:
        """Create effort config for a specific level."""
        configs = {
            EffortLevel.LOW: cls(
                level=EffortLevel.LOW,
                max_tokens=500,
                temperature=0.3,
            ),
            EffortLevel.MEDIUM: cls(
                level=EffortLevel.MEDIUM,
                max_tokens=2000,
                temperature=0.5,
            ),
            EffortLevel.HIGH: cls(
                level=EffortLevel.HIGH,
                max_tokens=4096,
                temperature=0.7,
            ),
        }
        return configs.get(level, configs[EffortLevel.MEDIUM])


class SandboxMode(Enum):
    """Sandbox execution modes"""

    DISABLED = "disabled"  # No sandboxing
    NATIVE = "native"  # Native sandbox runtime (lightweight)
    DOCKER = "docker"  # Docker container isolation
    GVISOR = "gvisor"  # Maximum security with gVisor


@dataclass
class SandboxSettings:
    """
    Sandbox configuration for secure agent execution.

    Based on Claude Agent SDK sandboxing documentation.
    """

    enabled: bool = True
    mode: SandboxMode = SandboxMode.NATIVE

    # Network isolation
    network_disabled: bool = True
    allowed_domains: list[str] = field(
        default_factory=lambda: [
            "api.alpaca.markets",  # Alpaca trading API
            "paper-api.alpaca.markets",  # Paper trading
            "data.alpaca.markets",  # Market data
            "api.openrouter.ai",  # Multi-LLM
            "api.anthropic.com",  # Claude API
        ]
    )

    # Filesystem isolation
    allowed_paths: list[str] = field(
        default_factory=lambda: [
            "/tmp",  # noqa: S108
            str(Path.home() / "trading" / "data"),
            str(Path.home() / "trading" / "reports"),
        ]
    )
    read_only_paths: list[str] = field(
        default_factory=lambda: [
            str(Path.home() / "trading" / "src"),
            str(Path.home() / "trading" / "config"),
        ]
    )

    # Command restrictions
    excluded_commands: list[str] = field(
        default_factory=lambda: [
            "rm -rf",
            "curl | bash",
            "wget | sh",
            "sudo",
            "chmod 777",
            "dd if=",
        ]
    )

    # Resource limits (Docker/gVisor)
    memory_limit: str = "2g"
    cpu_limit: float = 2.0
    pids_limit: int = 100

    def to_docker_flags(self) -> list[str]:
        """Generate Docker run flags for sandboxed execution"""
        flags = [
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=100m",  # noqa: S108
            "--memory",
            self.memory_limit,
            "--cpus",
            str(self.cpu_limit),
            "--pids-limit",
            str(self.pids_limit),
            "--user",
            "1000:1000",
        ]

        if self.network_disabled:
            flags.extend(["--network", "none"])

        return flags


@dataclass
class AgentSDKConfig:
    """
    Configuration for Claude Agent SDK integration.

    Centralizes all Agent SDK settings including:
    - Context window configuration (standard vs 1M)
    - Beta feature flags
    - Sandboxing settings
    - Model selection
    - Effort-based optimization (Opus 4.5)
    """

    # Context window settings
    context_size: ContextWindowSize = ContextWindowSize.EXTENDED_1M
    enable_context_compaction: bool = True  # Auto-summarize when approaching limit

    # Beta features
    beta_features: list[str] = field(
        default_factory=lambda: [
            "context-1m-2025-08-07",  # 1M context window
        ]
    )

    # Model configuration
    default_model: str = "claude-sonnet-4-5-20250929"  # Claude Sonnet 4.5
    opus_model: str = "claude-opus-4-5-20251101"  # Claude Opus 4.5 for complex tasks
    haiku_model: str = "claude-3-5-haiku-20241022"  # Fast model for simple tasks

    # Sandboxing
    sandbox: SandboxSettings = field(default_factory=SandboxSettings)

    # Agent-specific context allocations (tokens)
    # These are significantly increased with 1M context
    agent_context_allocations: dict[str, int] = field(
        default_factory=lambda: {
            # Core trading agents - expanded with 1M context
            "research_agent": 200_000,  # Full market data + history
            "signal_agent": 150_000,  # Technical indicators + patterns
            "risk_agent": 100_000,  # Risk metrics + position data
            "execution_agent": 50_000,  # Order execution context
            "meta_agent": 400_000,  # Full coordination context
            # Specialized agents
            "momentum_agent": 100_000,
            "rl_agent": 150_000,  # RL state + history
            "gemini_agent": 100_000,
            "debate_agents": 200_000,  # Multiple perspectives
            # Default for unspecified agents
            "default": 50_000,
        }
    )

    # Agent-specific effort levels (Opus 4.5 optimization)
    # Maps agent_id to effort level for token/cost optimization
    agent_effort_levels: dict[str, EffortLevel] = field(
        default_factory=lambda: {
            # Core trading agents
            "research_agent": EffortLevel.HIGH,  # Deep analysis needed
            "signal_agent": EffortLevel.MEDIUM,  # Standard technical analysis
            "risk_agent": EffortLevel.MEDIUM,  # Risk calculations
            "execution_agent": EffortLevel.LOW,  # Simple order execution
            "meta_agent": EffortLevel.HIGH,  # Complex coordination
            # Specialized agents
            "momentum_agent": EffortLevel.MEDIUM,
            "rl_agent": EffortLevel.HIGH,  # RL requires deep reasoning
            "gemini_agent": EffortLevel.MEDIUM,
            "debate_agents": EffortLevel.HIGH,  # Multi-perspective analysis
            # Default for unspecified agents
            "default": EffortLevel.MEDIUM,
        }
    )

    # Confidence threshold for model escalation
    # If initial analysis confidence < threshold, escalate to higher-tier model
    confidence_escalation_threshold: float = 0.7

    # Enable confidence-based model escalation
    # If True, low-confidence Haiku responses escalate to Sonnet, etc.
    enable_confidence_escalation: bool = True

    # SDK settings
    max_retries: int = 3
    timeout_seconds: int = 300
    enable_streaming: bool = True

    @classmethod
    def from_env(cls) -> AgentSDKConfig:
        """Create config from environment variables"""
        config = cls()

        # Override context size if specified
        if os.getenv("CLAUDE_CONTEXT_1M", "true").lower() == "true":
            config.context_size = ContextWindowSize.EXTENDED_1M
        else:
            config.context_size = ContextWindowSize.STANDARD

        # Override model if specified
        if model := os.getenv("CLAUDE_MODEL"):
            config.default_model = model

        # Sandbox settings
        if os.getenv("CLAUDE_SANDBOX_DISABLED", "").lower() == "true":
            config.sandbox.enabled = False

        sandbox_mode = os.getenv("CLAUDE_SANDBOX_MODE", "native")
        config.sandbox.mode = SandboxMode(sandbox_mode)

        return config

    def get_api_params(self) -> dict[str, Any]:
        """Get parameters for Anthropic API calls"""
        params = {
            "model": self.default_model,
            "max_tokens": min(self.context_size.value // 4, 8192),  # Response limit
        }

        # Add beta headers for 1M context
        if self.context_size == ContextWindowSize.EXTENDED_1M:
            params["betas"] = self.beta_features

        return params

    def get_agent_context_limit(self, agent_id: str) -> int:
        """Get context token limit for a specific agent"""
        return self.agent_context_allocations.get(
            agent_id, self.agent_context_allocations["default"]
        )

    def get_agent_effort(self, agent_id: str) -> EffortLevel:
        """Get effort level for a specific agent."""
        return self.agent_effort_levels.get(agent_id, self.agent_effort_levels["default"])

    def get_agent_effort_config(self, agent_id: str) -> EffortConfig:
        """Get full effort configuration for a specific agent."""
        effort_level = self.get_agent_effort(agent_id)
        return EffortConfig.for_level(effort_level)

    def get_model_for_effort(self, effort_level: EffortLevel) -> str:
        """
        Get appropriate model based on effort level.

        Opus 4.5 optimization: Use cheaper models for simpler tasks.
        - LOW effort -> Haiku (fast, cheap)
        - MEDIUM effort -> Sonnet (balanced)
        - HIGH effort -> Opus (best quality)
        """
        model_map = {
            EffortLevel.LOW: self.haiku_model,
            EffortLevel.MEDIUM: self.default_model,  # Sonnet
            EffortLevel.HIGH: self.opus_model,
        }
        return model_map.get(effort_level, self.default_model)

    def get_model_for_agent(self, agent_id: str) -> str:
        """
        Get appropriate model for a specific agent based on its effort level.

        This implements Opus 4.5's effort-based optimization:
        - Execution agents use Haiku (simple tasks)
        - Signal/risk agents use Sonnet (standard analysis)
        - Research/RL agents use Opus (complex reasoning)
        """
        effort_level = self.get_agent_effort(agent_id)
        return self.get_model_for_effort(effort_level)

    def should_escalate_model(self, confidence: float, current_effort: EffortLevel) -> bool:
        """
        Determine if model should be escalated based on confidence.

        If confidence is below threshold and we're not already at HIGH effort,
        recommend escalating to a higher-tier model.

        Args:
            confidence: Confidence score from 0.0 to 1.0
            current_effort: Current effort level

        Returns:
            True if should escalate, False otherwise
        """
        if not self.enable_confidence_escalation:
            return False

        if current_effort == EffortLevel.HIGH:
            return False  # Already at highest level

        return confidence < self.confidence_escalation_threshold

    def get_escalated_model(self, current_effort: EffortLevel) -> tuple[str, EffortLevel]:
        """
        Get escalated model and effort level.

        Returns:
            Tuple of (model_name, new_effort_level)
        """
        escalation_map = {
            EffortLevel.LOW: (self.default_model, EffortLevel.MEDIUM),
            EffortLevel.MEDIUM: (self.opus_model, EffortLevel.HIGH),
            EffortLevel.HIGH: (self.opus_model, EffortLevel.HIGH),  # No escalation
        }
        return escalation_map.get(current_effort, (self.opus_model, EffortLevel.HIGH))


# Global configuration singleton
_sdk_config: AgentSDKConfig | None = None


def get_agent_sdk_config() -> AgentSDKConfig:
    """Get or create global Agent SDK configuration"""
    global _sdk_config
    if _sdk_config is None:
        _sdk_config = AgentSDKConfig.from_env()
        logger.info(
            f"Agent SDK initialized: context={_sdk_config.context_size.value:,} tokens, "
            f"sandbox={_sdk_config.sandbox.mode.value}, "
            f"betas={_sdk_config.beta_features}"
        )
    return _sdk_config


def configure_agent_sdk(config: AgentSDKConfig) -> None:
    """Set custom Agent SDK configuration"""
    global _sdk_config
    _sdk_config = config
    logger.info(f"Agent SDK reconfigured: {config.context_size.value:,} tokens")
