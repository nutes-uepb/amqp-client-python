import pytest
from collections import deque
from unittest.mock import MagicMock, AsyncMock, patch
from asyncio import Future, get_event_loop
from amqp_client_python.rabbitmq.async_channel import AsyncChannel
from amqp_client_python.rabbitmq.async_connection import AsyncConnection
@pytest.mark.asyncio_cooperative
async def test_start_rpc_publisher_concurrency_fix():
    """Verify start_rpc_publisher awaits rpc_publisher_future when starting, avoiding rpc_consumer_future bug."""
    channel = AsyncChannel()
    channel.ioloop = get_event_loop()
    channel.rpc_publisher_starting = True
    channel.rpc_publisher_future = channel.ioloop.create_future()
    channel.rpc_publisher_future.set_result(True)

    result = await channel.start_rpc_publisher()
    assert result is True


@pytest.mark.asyncio_cooperative
async def test_process_callbacks_clears_list():
    """Verify process_callbacks clears the callbacks list so tasks are not executed twice."""
    channel = AsyncChannel()
    called = False

    async def dummy_callback():
        nonlocal called
        called = True
        return True

    loop = get_event_loop()
    future = loop.create_future()
    channel.callbacks = deque([(dummy_callback, future)])

    await channel.process_callbacks()
    assert called is True
    assert len(channel.callbacks) == 0
    assert future.done()
    assert future.result() is True


@pytest.mark.asyncio_cooperative
async def test_auto_recovery_on_connection_open():
    """Verify on_connection_open enqueues recovery callback when reconnecting is True."""
    loop = get_event_loop()
    conn = AsyncConnection(ioloop=loop)
    conn.reconnecting = True
    conn.backup["rpc_subscribe"]["test_key"] = {
        "queue_name": "q_test",
        "exchange_name": "ex_test",
        "callback": AsyncMock(),
        "timeout": 10,
    }

    mock_connection = MagicMock()
    conn.connection_factory.create_connection = MagicMock(return_value=mock_connection)
    
    with patch.object(AsyncChannel, "open") as mock_channel_open:
        conn.on_connection_open(mock_connection)
        assert conn.reconnecting is False
        assert len(conn.callbacks) == 1
        mock_channel_open.assert_called_once()
