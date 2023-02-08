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
        return b"result"

    rpc_subscribe = channel.rpc_subscribe(
        exchange, routing_key, queue_name, handle, content_type, connection_mock.ioloop
    )
    assert channel._channel == channel_mock
    assert iscoroutine(rpc_subscribe)
    assert await rpc_subscribe is None
    channel_mock.basic_consume.assert_called_once()
    assert channel_mock.basic_consume.call_args.args == (queue_name,)
