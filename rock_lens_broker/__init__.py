"""Rock Lens local broker with a deliberately narrow public API."""

from .contracts import Context, HealthState
from .version import VERSION

__all__ = ["VERSION", "Context", "HealthState"]
