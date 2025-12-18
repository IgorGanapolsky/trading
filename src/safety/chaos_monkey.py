"""Stub module - original safety deleted in cleanup."""


class ChaosMonkey:
    """Stub for deleted chaos monkey."""

    def __init__(self, *args, **kwargs):
        self.enabled = False

    def should_fail(self, *args, **kwargs) -> bool:
        return False


chaos_monkey = ChaosMonkey()
