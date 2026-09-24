from amqp_client_python.rabbitmq import AsyncChannel
from asyncio import iscoroutine
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
