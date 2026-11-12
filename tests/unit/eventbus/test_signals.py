import pytest
from asyncio import get_running_loop
from amqp_client_python.signals import Signal, Event
from amqp_client_python.domain.utils import ConnectionType


@pytest.mark.asyncio_cooperative
async def test_signal_str_and_enum_matching():
    """Verify that signal events match whether registered with str or Enum."""
    sig = Signal()
    loop = get_running_loop()
    called = []

    # Register with string
    @sig.on("connected", condiction="publish")
    def on_conn_str():
        called.append("str")

    # Register with Enum
    @sig.on(Event.CONNECTED, condiction=ConnectionType.PUBLISH)
    def on_conn_enum():
        called.append("enum")

    # Emit with Event.CONNECTED and ConnectionType.PUBLISH
    sig.emmit(Event.CONNECTED, condiction=ConnectionType.PUBLISH, loop=loop)

    assert "str" in called
    assert "enum" in called


@pytest.mark.asyncio_cooperative
async def test_signal_sync_callback_with_loop():
    """Verify that a synchronous callback does not crash when loop is provided."""
    sig = Signal()
    loop = get_running_loop()
    called = []

    @sig.on(Event.CONNECTED, condiction="test")
    def sync_cb():
        called.append("sync_done")
        return "result"

    sig.emmit(Event.CONNECTED, condiction="test", loop=loop)
    assert "sync_done" in called


@pytest.mark.asyncio_cooperative
async def test_signal_async_callback_with_loop():
    """Verify that an async coroutine callback is scheduled as a task."""
    sig = Signal()
    loop = get_running_loop()
    called = []

    @sig.on(Event.CHANNEL_OPENNED, condiction="test")
    async def async_cb():
        called.append("async_done")

    tasks = sig.emmit(Event.CHANNEL_OPENNED, condiction="test", loop=loop)
    assert len(tasks) == 1
    await tasks[0]
    assert "async_done" in called
