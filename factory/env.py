"""Safe environment variable parsing with type validation and defaults.

All env-var reads in the codebase should go through these helpers
to prevent crashes from misconfigured values (e.g. TIMEOUT=abc).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def env_int(name: str, default: int, *, min: int | None = None, max: int | None = None) -> int:
    """Read an integer env var, falling back to *default* on parse failure.

    Logs a warning if the value is present but unparseable or out of range.
    """
    raw = os.environ.get(name, "")
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning("%s=%r is not a valid integer — using default %d", name, raw, default)
        return default
    if min is not None and value < min:
        logger.warning("%s=%d below minimum %d — using %d", name, value, min, min)
        return min
    if max is not None and value > max:
        logger.warning("%s=%d above maximum %d — using %d", name, value, max, max)
        return max
    return value


def env_bool(name: str, default: bool = False) -> bool:
    """Read a boolean env var.

    True:  "1", "true",  "yes", "on"
    False: "0", "false", "no",  "off"
    Unset or "" returns *default*.
    """
    raw = os.environ.get(name, "").lower()
    if not raw:
        return default
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    logger.warning("%s=%r is not a valid boolean — using default %s", name, raw, default)
    return default


def env_path(name: str, default: str | Path) -> Path:
    """Read a filesystem path env var, expanding ~ and resolving."""
    raw = os.environ.get(name, "")
    if raw:
        return Path(raw).expanduser().resolve()
    return Path(str(default)).expanduser().resolve()


def env_str(name: str, default: str = "", *, choices: tuple[str, ...] | None = None) -> str:
    """Read a string env var with optional allowed-values check."""
    raw = os.environ.get(name, "")
    if not raw:
        return default
    if choices and raw not in choices:
        logger.warning("%s=%r not in %s — using default %r", name, raw, choices, default)
        return default
    return raw
