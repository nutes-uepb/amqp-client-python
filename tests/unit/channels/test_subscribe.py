import asyncio
from unittest.mock import MagicMock
from amqp_client_python.rabbitmq import AsyncChannel
from asyncio import iscoroutine
from pika import BasicProperties
import pytest


@pytest.mark.asyncio_cooperative
async def test_async_channel_subscribe(
    connection_mock, channel_mock, channel_factory_mock
):
    exchange, routing_key, queue_name, content_type = (
        "ex_example",
        "rk_example",
        "qn_example",
        "content_example",
    )
    channel_factory_mock.create_channel.return_value = channel_mock
    channel = AsyncChannel(channel_factory=channel_factory_mock)
    channel.open(connection_mock)

    async def handle(*body):
        pass

    subscribe = channel.subscribe(
        exchange, routing_key, queue_name, handle, content_type, connection_mock.ioloop
    )
    assert channel._channel == channel_mock
    assert iscoroutine(subscribe)
    assert await subscribe is None
    channel_mock.basic_consume.assert_called_once()
    assert channel_mock.basic_consume.call_args.args == (queue_name,)


@pytest.mark.asyncio_cooperative
async def test_async_channel_on_message_auto_decode_true(
    connection_mock, channel_mock, channel_factory_mock
):
    from unittest.mock import Mock
    from asyncio import Future, get_running_loop
    loop = get_running_loop()
    connection_mock.ioloop = loop

    channel_factory_mock.create_channel.return_value = channel_mock
    channel = AsyncChannel(channel_factory=channel_factory_mock)
    channel.open(connection_mock)

    received = Future()

    async def handle(body):
        received.set_result(body)

    await channel.subscribe(
        "ex", "rk", "qn", handle, 5, content_type="application/json", auto_decode=True
    )

    deliver = Mock(routing_key="rk", delivery_tag=1)
    props = Mock(reply_to=None, correlation_id="123")
    channel.on_message("qn", channel_mock, deliver, props, b'{"hello": "world"}')

    res = await received
    assert res == {"hello": "world"}


@pytest.mark.asyncio_cooperative
async def test_async_channel_on_message_auto_decode_false(
    connection_mock, channel_mock, channel_factory_mock
):
    from unittest.mock import Mock
    from asyncio import Future, get_running_loop
    loop = get_running_loop()
    connection_mock.ioloop = loop

    channel_factory_mock.create_channel.return_value = channel_mock
    channel = AsyncChannel(channel_factory=channel_factory_mock)
    channel.open(connection_mock)

    received = Future()

    async def handle(body):
        received.set_result(body)

    await channel.subscribe(
        "ex", "rk", "qn", handle, 5, content_type="application/json", auto_decode=False
    )

    deliver = Mock(routing_key="rk", delivery_tag=1)
    props = Mock(reply_to=None, correlation_id="123")
    channel.on_message("qn", channel_mock, deliver, props, b'{"hello": "world"}')

    res = await received
    assert res == b'{"hello": "world"}'


@pytest.mark.asyncio_cooperative
async def test_async_channel_on_message_invalid_json_fallback(
    connection_mock, channel_mock, channel_factory_mock
):
    from unittest.mock import Mock
    from asyncio import Future, get_running_loop
    loop = get_running_loop()
    connection_mock.ioloop = loop

    channel_factory_mock.create_channel.return_value = channel_mock
    channel = AsyncChannel(channel_factory=channel_factory_mock)
    channel.open(connection_mock)

    received = Future()

    async def handle(body):
        received.set_result(body)

    await channel.subscribe(
        "ex", "rk", "qn", handle, 5, content_type="application/json", auto_decode=True
    )

    deliver = Mock(routing_key="rk", delivery_tag=1)
    props = Mock(reply_to=None, correlation_id="123")
    channel.on_message("qn", channel_mock, deliver, props, b'non-json-bytes')

    res = await received
    assert res == b'non-json-bytes'


def test_amqp_topic_wildcard_zero_words():
    """Verify AMQP # wildcard matches zero words as well as multiple words."""
    channel = AsyncChannel()

    # user.# matching
    channel._compile_routing_pattern("test_q", "user.#")
    patterns = dict(channel._compiled_patterns["test_q"])
    user_pattern = patterns["user.#"]

    assert user_pattern.match("user") is not None
    assert user_pattern.match("user.created") is not None
    assert user_pattern.match("user.profile.update") is not None
    assert user_pattern.match("order.created") is None

    # #.error matching
    channel._compile_routing_pattern("test_q", "#.error")
    patterns = dict(channel._compiled_patterns["test_q"])
    error_pattern = patterns["#.error"]

    assert error_pattern.match("error") is not None
    assert error_pattern.match("auth.error") is not None
    assert error_pattern.match("sys.auth.error") is not None
    assert error_pattern.match("error.log") is None

    # a.#.z matching
    channel._compile_routing_pattern("test_q", "a.#.z")
    patterns = dict(channel._compiled_patterns["test_q"])
    mid_pattern = patterns["a.#.z"]

    assert mid_pattern.match("a.z") is not None
    assert mid_pattern.match("a.b.z") is not None
    assert mid_pattern.match("a.b.c.z") is not None
    assert mid_pattern.match("a.z.x") is None


@pytest.mark.asyncio_cooperative
async def test_cancelled_error_not_swallowed():
    """Verify that asyncio.CancelledError is re-raised and not swallowed as normal error."""
    loop = asyncio.get_running_loop()
    channel = AsyncChannel()
    channel.ioloop = loop
    channel._channel = MagicMock()
    channel._channel.is_open = True

    async def cancelling_handler(body):
        raise asyncio.CancelledError()

    channel.subscribes["cancel_queue"] = {
        "cancel.event": {
            "handle": cancelling_handler,
            "content_type": "text/plain",
            "response_timeout": 5,
            "auto_decode": False,
        }
    }

    deliver = MagicMock()
    deliver.routing_key = "cancel.event"
    deliver.delivery_tag = 303

    props = BasicProperties()

    channel.on_message("cancel_queue", channel._channel, deliver, props, b"cancel")
    await asyncio.sleep(0.05)

    assert not channel._channel.basic_nack.called
