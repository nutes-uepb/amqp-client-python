from amqp_client_python.rabbitmq import AsyncChannel
from amqp_client_python.exceptions import PublishTimeoutException, NackException
from asyncio import iscoroutine, Future, wait_for, get_running_loop
from unittest.mock import MagicMock
import pytest
from json import dumps


@pytest.mark.asyncio_cooperative
async def test_channel_publish(connection_mock, channel_mock, channel_factory_mock):
    exchange, routing_key, body, content_type, timeout = (
        "ex_example",
        "rk_example",
        "bd_example",
        "content_example",
        6,
    )
    future_publish = Future()
    future_publish.set_result(True)
    connection_mock.ioloop.create_future.return_value = future_publish
    channel_factory_mock.create_channel.return_value = channel_mock
    channel = AsyncChannel(channel_factory=channel_factory_mock)
    channel.publisher_confirms = False
    channel.open(connection_mock)
    publish = channel.publish(
        exchange, routing_key, body, content_type, timeout, connection_mock.ioloop
    )
    assert channel._channel == channel_mock
    assert iscoroutine(publish)
    result = await publish
    channel_mock.basic_publish.assert_called_once()
    assert channel_mock.basic_publish.call_args.args == (
        exchange,
        routing_key,
        dumps(body),
    )
    assert result is None


@pytest.mark.parametrize("resolve", [True, False])
@pytest.mark.asyncio_cooperative
async def test_async_publish_confirmation(
    connection_mock, channel_mock, channel_factory_mock, resolve
):
    loop = get_running_loop()
    exchange, routing_key, body, content_type, timeout = (
        "ex_example",
        "rk_example",
        "bd_example",
        "content_example",
        1,
    )
    future_publish = Future()
    connection_mock.ioloop.create_future.return_value = future_publish
    connection_mock.ioloop.call_later = loop.call_later
    channel_factory_mock.create_channel.return_value = channel_mock
    channel = AsyncChannel(channel_factory=channel_factory_mock)
    channel.publisher_confirms = True
    channel.futures = {}
    channel.open(connection_mock)
    publish = channel.publish(
        exchange, routing_key, body, content_type, timeout, connection_mock.ioloop
    )
    if resolve:
        future_publish.set_result(True)
        result = await publish
        assert result is True
    else:
        channel._message_number += 1
        channel.futures[channel._message_number] = future_publish
        channel.ioloop.call_later = loop.call_later
        channel.publish_confirmation = channel_mock.publish_confirmation
        with pytest.raises(PublishTimeoutException):
            await wait_for(publish, timeout=timeout + 1)


@pytest.mark.asyncio_cooperative
async def test_channel_publish_raw_bytes(connection_mock, channel_mock, channel_factory_mock):
    exchange, routing_key, body, content_type, timeout = (
        "ex_example",
        "rk_example",
        b'{"raw": "bytes"}',
        "application/json",
        6,
    )
    future_publish = Future()
    future_publish.set_result(True)
    connection_mock.ioloop.create_future.return_value = future_publish
    channel_factory_mock.create_channel.return_value = channel_mock
    channel = AsyncChannel(channel_factory=channel_factory_mock)
    channel.publisher_confirms = False
    channel.open(connection_mock)
    publish = channel.publish(
        exchange, routing_key, body, content_type, timeout, connection_mock.ioloop
    )
    await publish
    channel_mock.basic_publish.assert_called_once()
    # Ensure raw bytes were passed through directly without json.dumps
    assert channel_mock.basic_publish.call_args.args == (
        exchange,
        routing_key,
        b'{"raw": "bytes"}',
    )


@pytest.mark.asyncio_cooperative
async def test_batched_publisher_confirms_multiple():
    """Verify that Basic.Ack with multiple=True confirms all tags <= delivery_tag."""
    loop = get_running_loop()
    channel = AsyncChannel()
    channel.ioloop = loop
    channel._channel = MagicMock()
    channel.add_publish_confirms()

    fut1 = loop.create_future()
    fut2 = loop.create_future()
    fut3 = loop.create_future()

    channel.publish_confirmation(fut1)  # tag 1
    channel.publish_confirmation(fut2)  # tag 2
    channel.publish_confirmation(fut3)  # tag 3

    assert 1 in channel._deliveries
    assert 2 in channel._deliveries
    assert 3 in channel._deliveries

    frame = MagicMock()
    frame.method.NAME = "Basic.Ack"
    frame.method.delivery_tag = 3
    frame.method.multiple = True

    channel.on_delivery_confirmation(frame)

    assert fut1.done() and fut1.result() is True
    assert fut2.done() and fut2.result() is True
    assert fut3.done() and fut3.result() is True
    assert channel._acked == 3


@pytest.mark.asyncio_cooperative
async def test_batched_publisher_confirms_nack_multiple():
    """Verify that Basic.Nack with multiple=True fails all tags <= delivery_tag."""
    loop = get_running_loop()
    channel = AsyncChannel()
    channel.ioloop = loop
    channel._channel = MagicMock()
    channel.add_publish_confirms()

    fut1 = loop.create_future()
    fut2 = loop.create_future()

    channel.publish_confirmation(fut1)  # tag 1
    channel.publish_confirmation(fut2)  # tag 2

    frame = MagicMock()
    frame.method.NAME = "Basic.Nack"
    frame.method.delivery_tag = 2
    frame.method.multiple = True

    channel.on_delivery_confirmation(frame)

    assert fut1.done() and isinstance(fut1.exception(), NackException)
    assert fut2.done() and isinstance(fut2.exception(), NackException)
    assert channel._nacked == 2


@pytest.mark.asyncio_cooperative
async def test_batched_publisher_confirms_no_reprocessing():
    """Verify that consecutive batch ACKs do not re-process or re-count already confirmed tags."""
    loop = get_running_loop()
    channel = AsyncChannel()
    channel.ioloop = loop
    channel._channel = MagicMock()
    channel.add_publish_confirms()

    fut1 = loop.create_future()
    fut2 = loop.create_future()
    fut3 = loop.create_future()

    channel.publish_confirmation(fut1)  # tag 1
    channel.publish_confirmation(fut2)  # tag 2
    channel.publish_confirmation(fut3)  # tag 3

    # First ACK confirms up to tag 2
    frame1 = MagicMock()
    frame1.method.NAME = "Basic.Ack"
    frame1.method.delivery_tag = 2
    frame1.method.multiple = True
    channel.on_delivery_confirmation(frame1)

    assert fut1.done() and fut1.result() is True
    assert fut2.done() and fut2.result() is True
    assert not fut3.done()
    assert channel._acked == 2
    assert 1 not in channel._deliveries
    assert 2 not in channel._deliveries
    assert 3 in channel._deliveries

    # Second ACK confirms up to tag 3
    frame2 = MagicMock()
    frame2.method.NAME = "Basic.Ack"
    frame2.method.delivery_tag = 3
    frame2.method.multiple = True
    channel.on_delivery_confirmation(frame2)

    assert fut3.done() and fut3.result() is True
    assert channel._acked == 3  # Crucial: Must be 3, not 5 (2 + 3)
    assert 3 not in channel._deliveries
