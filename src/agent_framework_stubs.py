"""Stub module - provides empty implementations for deleted agent_framework."""


class AgentResult:
    """Stub for deleted AgentResult."""
    def __init__(self, *args, **kwargs):
        self.success = True
        self.data = {}


class RunContext:
    """Stub for deleted RunContext."""
    def __init__(self, *args, **kwargs):
        pass


class ContextEngine:
    """Stub for deleted ContextEngine."""
    def __init__(self, *args, **kwargs):
        pass

    def get_context(self, *args, **kwargs) -> dict:
        return {}

    def prune_memories(self, *args, **kwargs) -> list:
        """Stub for memory pruning - returns empty list."""
        return []

    def store_memory(self, *args, **kwargs) -> str:
        """Stub for memory storage - returns empty ID."""
        return ""

    def retrieve_memories(self, *args, **kwargs) -> list:
        """Stub for memory retrieval - returns empty list."""
        return []

    def send_context_message(self, *args, **kwargs) -> None:
        """Stub for context messaging."""
        pass

    def validate_context_flow(self, *args, **kwargs) -> tuple:
        """Stub for context validation - always valid."""
        return (True, [])

    def get_agent_context(self, *args, **kwargs) -> dict:
        """Stub for agent context - returns empty dict."""
        return {}


class MemoryTimescale:
    """Stub for deleted MemoryTimescale."""
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


def get_context_engine(*args, **kwargs):
    """Return stub context engine."""
    return ContextEngine()
