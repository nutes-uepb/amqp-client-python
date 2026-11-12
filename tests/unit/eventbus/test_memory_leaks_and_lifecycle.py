import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock
from asyncio import Future, get_running_loop
from amqp_client_python.rabbitmq.async_connection import AsyncConnection
from amqp_client_python.rabbitmq.async_channel import AsyncChannel
from amqp_client_python.exceptions import (
    AutoReconnectException,
    EventBusException,
)
from amqp_client_python.rabbitmq.connection_rabbitmq import ConnectionRabbitMQ
from amqp_client_python.rabbitmq.channel_rabbitmq import ChannelRabbitMQ
from amqp_client_python.rabbitmq.ioloop_factory import IOLoopFactory
from pika.spec import BasicProperties


@pytest.mark.asyncio_cooperative
async def test_add_callback_timeout_cleanup():
    """Verify that timed out callbacks do not leak in AsyncConnection.callbacks."""
    loop = get_running_loop()
    conn = AsyncConnection(loop)

    for _ in range(5):
        with pytest.raises(AutoReconnectException):
            await conn.add_callback(lambda: None, connection_timeout=0.005)

    assert len(conn.callbacks) == 0, "Timed out callbacks should be removed from deque"


@pytest.mark.asyncio_cooperative
async def test_add_callback_cancellation_cleanup():
    """Verify that cancelled callbacks do not leak in AsyncConnection.callbacks."""
    loop = get_running_loop()
    conn = AsyncConnection(loop)

    task = loop.create_task(conn.add_callback(lambda: None, connection_timeout=10.0))
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert len(conn.callbacks) == 0, "Cancelled callbacks should be removed from deque"


@pytest.mark.asyncio_cooperative
async def test_prevent_zombie_callback_execution():
    """Verify that expired callbacks are skipped and not executed when channel opens."""
    loop = get_running_loop()
    conn = AsyncConnection(loop)
    executed = []

    async def sample_op(val):
        executed.append(val)

    # Queue callbacks that will time out
    for i in range(3):
        with pytest.raises(AutoReconnectException):
            await conn.add_callback(lambda i=i: sample_op(i), connection_timeout=0.005)

    # Even if somehow a done future remained in deque, process_callbacks must skip it
    fake_fut = Future()
    fake_fut.cancel()
    conn.callbacks.append((lambda: sample_op("zombie"), fake_fut))

    channel = AsyncChannel()
    channel.callbacks = conn.callbacks
    channel.ioloop = loop
    await channel.process_callbacks()

    assert len(executed) == 0, "Zombie callbacks must not be executed after timeout/cancel"


@pytest.mark.asyncio_cooperative
async def test_rpc_client_timer_cancelled_on_response():
    """Verify that TimerHandle is cancelled when RPC response arrives."""
    loop = get_running_loop()
    channel = AsyncChannel()
    channel.ioloop = loop
    channel.start_rpc_consumer = AsyncMock(return_value=True)
    channel._channel = MagicMock()

    task = loop.create_task(
        channel.rpc_client("ex", "rk", {}, "application/json", response_timeout=30)
    )
    await asyncio.sleep(0.01)

    corr_id = list(channel.rpc_futures.keys())[0]
    timer = channel.rpc_futures[corr_id]["timer"]
    assert not timer.cancelled(), "Timer should be active before response"

    # Simulate response delivery
    props = BasicProperties(correlation_id=corr_id, type="normal")
    deliver = MagicMock(delivery_tag=1)
    channel._channel_rpc = MagicMock(is_open=True)
    channel.on_response(None, deliver, props, b'{"result": "ok"}')

    await task
    assert timer.cancelled(), "Timer must be cancelled when response arrives"
    assert corr_id not in channel.rpc_futures, "corr_id must be removed from rpc_futures"


@pytest.mark.asyncio_cooperative
async def test_publish_timer_cancelled_on_ack():
    """Verify that TimerHandle is cancelled when publisher confirmation arrives."""
    loop = get_running_loop()
    channel = AsyncChannel()
    channel.ioloop = loop
    channel.publisher_confirms = True
    channel._channel = MagicMock()

    task = loop.create_task(
        channel.publish("ex", "rk", {}, "application/json", timeout=10)
    )
    await asyncio.sleep(0.01)

    msg_id = channel._message_number
    timer = channel._publish_timers.get(msg_id)
    assert timer is not None and not timer.cancelled()

    # Confirm message via ACK
    method = MagicMock()
    method.NAME = "basic.ack"
    method.delivery_tag = msg_id
    method_frame = MagicMock(method=method)
    channel.on_delivery_confirmation(method_frame)

    result = await task
    assert result is True
    assert timer.cancelled(), "Timer must be cancelled when ACK arrives"
    assert msg_id not in channel._publish_timers


@pytest.mark.asyncio_cooperative
async def test_rpc_client_cleans_up_on_setup_failure():
    """Verify that rpc_futures does not leak if setup raises an error."""
    loop = get_running_loop()
    channel = AsyncChannel()
    channel.ioloop = loop
    channel.start_rpc_consumer = AsyncMock(side_effect=EventBusException("Setup failed"))
    channel._channel = MagicMock()

    with pytest.raises(EventBusException):
        await channel.rpc_client("ex", "rk", {}, "application/json", response_timeout=5)

    assert len(channel.rpc_futures) == 0, "corr_id must not leak on setup error"


@pytest.mark.asyncio_cooperative
async def test_on_channel_closed_aborts_inflight_operations():
    """Verify that on_channel_closed immediately fails all in-flight RPCs and publishes."""
    loop = get_running_loop()
    channel = AsyncChannel()
    channel.ioloop = loop
    channel.publisher_confirms = True
    channel.start_rpc_consumer = AsyncMock(return_value=True)
    channel._channel = MagicMock()
    channel._connection = MagicMock(is_closing=False, is_closed=False)

    rpc_task = loop.create_task(
        channel.rpc_client("ex", "rk", {}, "application/json", response_timeout=60)
    )
    pub_task = loop.create_task(
        channel.publish("ex", "rk", {}, "application/json", timeout=60)
    )
    await asyncio.sleep(0.01)

    # Simulate unexpected channel closure
    channel.on_channel_closed(None, "Broker restart")

    with pytest.raises(AutoReconnectException):
        await rpc_task

    with pytest.raises(AutoReconnectException):
        await pub_task

    assert len(channel.rpc_futures) == 0
    assert len(channel.futures) == 0
    assert len(channel._deliveries) == 0


@pytest.mark.asyncio_cooperative
async def test_close_cancels_reconnect_timer():
    """Verify that close() cancels active reconnect timer and prevents reconnect loop."""
    loop = get_running_loop()
    conn = AsyncConnection(loop)
    conn.url = "amqp://dummy"
    conn.connection_factory = MagicMock()

    conn.on_connection_open_error(None, "Connection failed")
    assert conn.reconnecting is True
    assert conn._reconnect_timer is not None
    assert not conn._reconnect_timer.cancelled()

    await conn.close()
    assert conn._closing is True
    assert conn.reconnecting is False
    assert conn._reconnect_timer is None or conn._reconnect_timer.cancelled()

    # Wait to ensure no reconnect attempts happen after close
    await asyncio.sleep(0.05)
    assert conn.connection_factory.create_connection.call_count == 1


def test_ioloop_factory_no_duplicate_reconnection():
    """Verify that ConnectionRabbitMQ does not leak reconnect handlers in IOLoopFactory."""
    initial_len = len(IOLoopFactory._reconnection_list)
    conn = ConnectionRabbitMQ("pub")
    # Adding same reconnect won't duplicate
    conn2 = ConnectionRabbitMQ("pub")
    conn.stop()
    conn2.stop()
    assert len(IOLoopFactory._reconnection_list) <= initial_len + 1


from concurrent.futures import Future as ConcurrentFuture


def test_sync_channel_on_response_error():
    """Verify that sync ChannelRabbitMQ does not raise InvalidStateError on error response."""
    channel = ChannelRabbitMQ()
    fut = ConcurrentFuture()
    channel.futures["corr-1"] = fut

    props = BasicProperties(correlation_id="corr-1", type="error")
    # Must not raise InvalidStateError
    channel._ChannelRabbitMQ__on_response(None, None, props, b"Error message")

    assert fut.done()
    assert fut.exception() is not None
