from __future__ import annotations

"""Channel plugin interface — multi-platform messaging adapters."""

from factory.channel.adapter import (
    ChannelAdapter,
    DummyChannel,
    broadcast,
    get_adapter,
    list_adapters,
    on_inbound,
    register,
    send_to_channel,
    unregister,
)
from factory.channel.types import ChannelMessage, ChannelStatus
from factory.channel.weixin import WeixinChannel, WeixinConfig

__all__ = [
    "ChannelAdapter",
    "DummyChannel",
    "register",
    "unregister",
    "get_adapter",
    "list_adapters",
    "on_inbound",
    "send_to_channel",
    "broadcast",
    "ChannelMessage",
    "ChannelStatus",
    "WeixinChannel",
    "WeixinConfig",
]
