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


class MemoryTimescale:
    """Stub for deleted MemoryTimescale."""
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


def get_context_engine(*args, **kwargs):
    """Return stub context engine."""
    return ContextEngine()
