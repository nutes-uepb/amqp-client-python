from amqp_client_python.rabbitmq import AsyncChannel
from amqp_client_python.exceptions import EventBusException
from asyncio import iscoroutine, Future, get_running_loop
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

    future_publisher = Future()
    future_publisher.set_result(True)
    connection_mock.ioloop.create_future.side_effect = [
        future_publisher,
    ]
    channel_factory_mock.create_channel.return_value = channel_mock
    channel = AsyncChannel(channel_factory=channel_factory_mock)
    channel.open(connection_mock)

    async def handle(*body):
        return b"result"

    rpc_subscribe = channel.rpc_subscribe(
        exchange, routing_key, queue_name, handle, content_type, connection_mock.ioloop
    )
    assert channel._channel == channel_mock
    assert iscoroutine(rpc_subscribe)
    assert await rpc_subscribe is None
    channel_mock.basic_consume.assert_called_once()
    assert channel_mock.basic_consume.call_args.args == (queue_name,)


@pytest.mark.parametrize("consumer", [True, False])
@pytest.mark.asyncio_cooperative
async def test_rpc_subscribe_publisher_started(
    connection_mock, channel_mock, channel_factory_mock, consumer
):
    loop = get_running_loop()
    exchange, routing_key, queue_name, content_type = (
        "ex_example",
        "rk_example",
        "qn_example",
        "content_example",
    )
    future_publisher = Future()
    if consumer:
        future_publisher.set_result(True)
    connection_mock.ioloop.create_future.side_effect = [
        future_publisher,
    ]
    connection_mock.ioloop.call_later = loop.call_later
    channel_factory_mock.create_channel.return_value = channel_mock
    channel = AsyncChannel(channel_factory=channel_factory_mock)
    channel.open(connection_mock)

    async def handle(*body):
        return b"result"

    rpc_subscribe = channel.rpc_subscribe(
        exchange, routing_key, queue_name, handle, content_type, connection_mock.ioloop
    )
    if consumer:
        assert await rpc_subscribe is None
        assert channel.rpc_publisher is True
    else:
        with pytest.raises(EventBusException):
            assert await rpc_subscribe is None
        assert channel.rpc_publisher is False
