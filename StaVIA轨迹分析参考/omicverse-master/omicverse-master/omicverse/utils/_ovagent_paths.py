"""Central resolver for ov.Agent storage root.

Honors ``OVAGENT_HOME`` env var; falls back to ``~/.ovagent``. Lets users
redirect all session / trace / context / notebook output to a scratch
filesystem on hosts where /home is small or quota-constrained.
"""

from __future__ import annotations

import os
from pathlib import Path


def ovagent_home() -> Path:
    """Return the root directory for ov.Agent persistent state.

    Resolution order:
    1. ``$OVAGENT_HOME`` (if set and non-empty)
    2. ``~/.ovagent``

    The directory is **not** created here — callers append a subdir
    (``runs``, ``sessions``, ``harness``, etc.) and `.mkdir(parents=True, exist_ok=True)`.
    """
    env = os.environ.get("OVAGENT_HOME", "").strip()
    if env:
        return Path(env).expanduser()
    return Path.home() / ".ovagent"
