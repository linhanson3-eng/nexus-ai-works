"""Channel message types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ChannelMessage:
    """A message received from or being sent to a channel."""

    sender: str
    content: str
    channel_name: str
    timestamp: str = ""
    metadata: dict[str, str] = field(default_factory=dict, hash=False, compare=False)
    # Routing hints
    workshop_name: str = ""
    agent_name: str = ""


@dataclass(frozen=True)
class ChannelStatus:
    """Health status of a channel adapter."""

    name: str
    connected: bool
    last_event_at: str = ""
    error: str = ""
