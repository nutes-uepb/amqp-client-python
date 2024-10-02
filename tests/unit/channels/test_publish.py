from amqp_client_python.rabbitmq import AsyncChannel
from amqp_client_python.exceptions import PublishTimeoutException
from asyncio import iscoroutine, Future, wait_for, get_running_loop
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
