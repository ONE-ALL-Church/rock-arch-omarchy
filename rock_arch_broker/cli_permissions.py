from __future__ import annotations

MUTATION_ACTIONS = (
    "addLinks", "addSections", "deleteLinks", "deleteSections", "runJobs", "buildMagnus",
)


class CliMutationError(Exception):
    def __init__(self, action: str) -> None:
        super().__init__("terminal_mutation_action_disabled")
        self.action = action


def require_mutation(allowed: frozenset[str] | None, action: str) -> None:
    """None denotes an interactive request; CLI grants are an explicit allowlist."""
    if allowed is not None and action not in allowed:
        raise CliMutationError(action)
