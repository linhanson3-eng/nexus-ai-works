"""Channel adapter interface and global registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

from factory.channel.types import ChannelMessage


class ChannelAdapter(ABC):
    """Abstract base for channel adapters.

    Each channel (WeChat, Feishu, Discord, etc.) implements this interface.
    The factory gateway routes messages through registered adapters.
    """

    def __init__(self, name: str, config: dict[str, Any] | None = None) -> None:
        self.name = name
        self.config = config or {}
        self._running = False

    # -- Lifecycle --

    async def start(self) -> None:
        """Start the channel adapter. Called once on registration."""
        self._running = True

    async def stop(self) -> None:
        """Stop the channel adapter. Clean up connections."""
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    # -- Message I/O --

    @abstractmethod
    async def send(self, message: ChannelMessage) -> bool:
        """Send a message via this channel. Return True on success."""
        ...

    async def on_receive(self, message: ChannelMessage) -> None:
        """Called by the adapter when an inbound message arrives.

        Default implementation calls registered handlers. Subclasses
        should call this after constructing the ChannelMessage.
        """
        for handler in _inbound_handlers:
            try:
                await handler(message)
            except Exception:
                pass

    # -- Health --

    async def health(self) -> dict[str, Any]:
        """Return health status dict."""
        return {
            "name": self.name,
            "running": self._running,
            "type": self.__class__.__name__,
        }


# -- Global Channel Registry --

_registry: dict[str, ChannelAdapter] = {}
_inbound_handlers: list[Callable[[ChannelMessage], Awaitable[None]]] = []


def register(name: str, adapter: ChannelAdapter) -> None:
    """Register a channel adapter."""
    _registry[name] = adapter


def unregister(name: str) -> None:
    """Unregister a channel adapter."""
    _registry.pop(name, None)


def get_adapter(name: str) -> ChannelAdapter | None:
    """Get a registered channel adapter."""
    return _registry.get(name)


def list_adapters() -> list[str]:
    """List all registered channel adapter names."""
    return list(_registry.keys())


def on_inbound(handler: Callable[[ChannelMessage], Awaitable[None]]) -> Callable[[ChannelMessage], Awaitable[None]]:
    """Register a global inbound message handler."""
    _inbound_handlers.append(handler)
    return handler


async def send_to_channel(channel_name: str, message: ChannelMessage) -> bool:
    """Convenience: send a message to a specific channel."""
    adapter = _registry.get(channel_name)
    if adapter is None:
        return False
    return await adapter.send(message)


async def broadcast(message: ChannelMessage) -> dict[str, bool]:
    """Send a message to all registered channels."""
    results: dict[str, bool] = {}
    for name, adapter in _registry.items():
        try:
            results[name] = await adapter.send(message)
        except Exception:
            results[name] = False
    return results


class DummyChannel(ChannelAdapter):
    """A no-op channel adapter for testing and development."""

    async def send(self, message: ChannelMessage) -> bool:
        # In test/CLI mode, just print the message
        print(
            f"[{self.name}] TO {message.workshop_name or '?'}/{message.agent_name or '?'}: "
            f"{message.content[:120]}"
        )
        return True
