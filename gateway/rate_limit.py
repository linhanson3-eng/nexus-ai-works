"""Rate limiting for the Gateway API using slowapi."""

from __future__ import annotations

import os

from slowapi import Limiter
from slowapi.util import get_remote_address

_default_limit = os.environ.get("RATE_LIMIT", "100/minute")

limiter = Limiter(key_func=get_remote_address, default_limits=[_default_limit])
