from __future__ import annotations
"""Tests for channel adapter interface and registry."""


import pytest

from factory.channel.adapter import (
    ChannelAdapter,
    DummyChannel,
    _inbound_handlers,
    _registry,
    broadcast,
    get_adapter,
    list_adapters,
    on_inbound,
    register,
    send_to_channel,
    unregister,
)
from factory.channel.types import ChannelMessage, ChannelStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def clear_registry() -> None:
    """Reset the global registry and inbound handlers before each test."""
    _registry.clear()
    _inbound_handlers.clear()
    yield
    _registry.clear()
    _inbound_handlers.clear()


@pytest.fixture
def dummy() -> DummyChannel:
    """Return a fresh DummyChannel adapter."""
    return DummyChannel(name="test-dummy")


@pytest.fixture
def sample_message() -> ChannelMessage:
    """Return a sample ChannelMessage for tests."""
    return ChannelMessage(
        sender="user-1",
        content="Hello, world!",
        channel_name="test-dummy",
        workshop_name="ws-1",
        agent_name="agent-1",
    )


# ---------------------------------------------------------------------------
# TestChannelMessage
# ---------------------------------------------------------------------------


class TestChannelMessage:
    """Tests for the ChannelMessage frozen dataclass."""

    def test_frozen_dataclass_prevents_mutation(self) -> None:
        msg = ChannelMessage(sender="u1", content="hi", channel_name="ch1")
        with pytest.raises(Exception):
            msg.sender = "changed"  # type: ignore[misc]

    def test_defaults_are_applied(self) -> None:
        msg = ChannelMessage(sender="u1", content="hi", channel_name="ch1")
        assert msg.timestamp == ""
        assert msg.metadata == {}
        assert msg.workshop_name == ""
        assert msg.agent_name == ""

    def test_all_fields_settable_at_construction(self) -> None:
        msg = ChannelMessage(
            sender="u1",
            content="hi",
            channel_name="ch1",
            timestamp="2025-01-01T00:00:00Z",
            metadata={"role": "admin"},
            workshop_name="ws-1",
            agent_name="ag-1",
        )
        assert msg.timestamp == "2025-01-01T00:00:00Z"
        assert msg.metadata == {"role": "admin"}
        assert msg.workshop_name == "ws-1"
        assert msg.agent_name == "ag-1"

    def test_equality_by_value(self) -> None:
        a = ChannelMessage(sender="u1", content="hi", channel_name="ch1")
        b = ChannelMessage(sender="u1", content="hi", channel_name="ch1")
        assert a == b
        assert hash(a) == hash(b)


# ---------------------------------------------------------------------------
# TestChannelStatus
# ---------------------------------------------------------------------------


class TestChannelStatus:
    """Tests for the ChannelStatus frozen dataclass."""

    def test_defaults(self) -> None:
        status = ChannelStatus(name="wechat", connected=False)
        assert status.last_event_at == ""
        assert status.error == ""

    def test_connected_with_error(self) -> None:
        status = ChannelStatus(
            name="feishu",
            connected=False,
            error="timeout",
            last_event_at="2025-01-01T00:00:00Z",
        )
        assert status.name == "feishu"
        assert status.connected is False
        assert status.error == "timeout"
        assert status.last_event_at == "2025-01-01T00:00:00Z"


# ---------------------------------------------------------------------------
# TestDummyChannel
# ---------------------------------------------------------------------------


class TestDummyChannel:
    """Tests for the DummyChannel adapter."""

    def test_initial_state_not_running(self, dummy: DummyChannel) -> None:
        assert dummy.is_running is False

    @pytest.mark.asyncio
    async def test_start_sets_running(self, dummy: DummyChannel) -> None:
        await dummy.start()
        assert dummy.is_running is True

    @pytest.mark.asyncio
    async def test_stop_sets_not_running(self, dummy: DummyChannel) -> None:
        await dummy.start()
        await dummy.stop()
        assert dummy.is_running is False

    @pytest.mark.asyncio
    async def test_send_returns_true(self, dummy: DummyChannel, sample_message: ChannelMessage) -> None:
        result = await dummy.send(sample_message)
        assert result is True

    @pytest.mark.asyncio
    async def test_health_returns_dict(self, dummy: DummyChannel) -> None:
        health = await dummy.health()
        assert health["name"] == "test-dummy"
        assert health["type"] == "DummyChannel"
        assert "running" in health


# ---------------------------------------------------------------------------
# TestRegistry
# ---------------------------------------------------------------------------


class TestRegistry:
    """Tests for the global channel registry functions."""

    def test_register_adds_adapter(
        self, clear_registry: None, dummy: DummyChannel
    ) -> None:
        register("ch1", dummy)
        assert get_adapter("ch1") is dummy

    def test_register_duplicate_overwrites(
        self, clear_registry: None, dummy: DummyChannel
    ) -> None:
        register("ch1", dummy)
        second = DummyChannel(name="second")
        register("ch1", second)
        assert get_adapter("ch1") is second

    def test_unregister_removes_adapter(
        self, clear_registry: None, dummy: DummyChannel
    ) -> None:
        register("ch1", dummy)
        unregister("ch1")
        assert get_adapter("ch1") is None

    def test_unregister_nonexistent_does_not_raise(
        self, clear_registry: None
    ) -> None:
        unregister("ghost")  # should not raise

    def test_get_adapter_missing_returns_none(
        self, clear_registry: None
    ) -> None:
        assert get_adapter("nope") is None

    def test_list_adapters_empty(self, clear_registry: None) -> None:
        assert list_adapters() == []

    def test_list_adapters_returns_registered_names(
        self, clear_registry: None, dummy: DummyChannel
    ) -> None:
        register("a", dummy)
        register("b", DummyChannel(name="b"))
        names = list_adapters()
        assert sorted(names) == ["a", "b"]


# ---------------------------------------------------------------------------
# TestInboundHandler
# ---------------------------------------------------------------------------


class TestInboundHandler:
    """Tests for inbound message handler registration and invocation."""

    @pytest.mark.asyncio
    async def test_on_receive_calls_registered_handler(
        self, clear_registry: None, dummy: DummyChannel, sample_message: ChannelMessage
    ) -> None:
        received: list[ChannelMessage] = []

        async def capture(msg: ChannelMessage) -> None:
            received.append(msg)

        on_inbound(capture)
        await dummy.on_receive(sample_message)
        assert len(received) == 1
        assert received[0] is sample_message

    @pytest.mark.asyncio
    async def test_handler_errors_do_not_crash_on_receive(
        self, clear_registry: None, dummy: DummyChannel, sample_message: ChannelMessage
    ) -> None:
        received: list[ChannelMessage] = []

        async def broken(msg: ChannelMessage) -> None:
            raise RuntimeError("boom")

        async def working(msg: ChannelMessage) -> None:
            received.append(msg)

        on_inbound(broken)
        on_inbound(working)
        await dummy.on_receive(sample_message)
        assert len(received) == 1
        assert received[0] is sample_message

    @pytest.mark.asyncio
    async def test_on_inbound_returns_handler(
        self, clear_registry: None
    ) -> None:
        async def h(msg: ChannelMessage) -> None:
            pass

        result = on_inbound(h)
        assert result is h


# ---------------------------------------------------------------------------
# TestSendToChannel
# ---------------------------------------------------------------------------


class TestSendToChannel:
    """Tests for the send_to_channel convenience function."""

    @pytest.mark.asyncio
    async def test_sends_to_registered_adapter(
        self, clear_registry: None, dummy: DummyChannel, sample_message: ChannelMessage
    ) -> None:
        register("ch1", dummy)
        result = await send_to_channel("ch1", sample_message)
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_for_unknown_channel(
        self, clear_registry: None, sample_message: ChannelMessage
    ) -> None:
        result = await send_to_channel("ghost", sample_message)
        assert result is False


# ---------------------------------------------------------------------------
# TestBroadcast
# ---------------------------------------------------------------------------


class TestBroadcast:
    """Tests for the broadcast function."""

    @pytest.mark.asyncio
    async def test_broadcast_to_multiple_channels(
        self, clear_registry: None, sample_message: ChannelMessage
    ) -> None:
        register("a", DummyChannel(name="a"))
        register("b", DummyChannel(name="b"))
        results = await broadcast(sample_message)
        assert results == {"a": True, "b": True}

    @pytest.mark.asyncio
    async def test_broadcast_empty_registry(
        self, clear_registry: None, sample_message: ChannelMessage
    ) -> None:
        results = await broadcast(sample_message)
        assert results == {}

    @pytest.mark.asyncio
    async def test_broadcast_marks_failing_channel_as_false(
        self, clear_registry: None, sample_message: ChannelMessage
    ) -> None:

        class FailingChannel(ChannelAdapter):
            async def send(self, message: ChannelMessage) -> bool:
                raise RuntimeError("down")

        register("ok", DummyChannel(name="ok"))
        register("bad", FailingChannel(name="bad"))
        results = await broadcast(sample_message)
        assert results["ok"] is True
        assert results["bad"] is False
