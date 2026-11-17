import asyncio
from unittest.mock import MagicMock
from amqp_client_python.rabbitmq import AsyncChannel
from amqp_client_python.exceptions import EventBusException
from amqp_client_python import ConnectionType
from asyncio import iscoroutine, Future, get_running_loop
from pika import BasicProperties
import pytest


@pytest.mark.asyncio_cooperative
async def test_async_channel_subscribe(
    connection_mock, channel_mock, channel_factory_mock
):
    loop = get_running_loop()
    exchange, routing_key, queue_name, content_type = (
        "ex_example",
        "rk_example",
        "qn_example",
        "content_example",
    )

    future_publisher = Future(loop=loop)
    future_publisher.set_result(True)
    connection_mock.ioloop.call_later = loop.call_later
    connection_mock.ioloop.create_future.return_value = future_publisher
    channel_factory_mock.create_channel.return_value = channel_mock
    channel = AsyncChannel(
        channel_factory=channel_factory_mock, channel_type=ConnectionType.RPC_SERVER
    )
    channel.open(connection_mock)

    async def handle(*body):
        return b"result"

    rpc_subscribe = channel.rpc_subscribe(
        exchange, routing_key, queue_name, handle, content_type, connection_mock.ioloop
    )
    assert channel._channel == channel_mock
    assert iscoroutine(rpc_subscribe)
    assert (await rpc_subscribe) is None
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
    future_publisher = Future(loop=loop)
    if consumer:
        future_publisher.set_result(True)
    connection_mock.ioloop.create_future.return_value = future_publisher
    connection_mock.ioloop.call_later = loop.call_later
    channel_factory_mock.create_channel.return_value = channel_mock
    channel = AsyncChannel(channel_factory=channel_factory_mock)
    channel.open(connection_mock)

    async def handle(*body):
        return b"result"

    rpc_subscribe = channel.rpc_subscribe(
        exchange, routing_key, queue_name, handle, content_type
    )
    if consumer:
        assert (await rpc_subscribe) is None
        assert channel.rpc_publisher_starting is True
    else:
        with pytest.raises(EventBusException):
            assert await rpc_subscribe is None
        assert channel.rpc_publisher_started is False


@pytest.mark.asyncio_cooperative
async def test_rpc_server_dict_and_list_serialization():
    """Verify that RPC server responses returning dicts are serialized without AttributeError."""
    loop = asyncio.get_running_loop()
    channel = AsyncChannel()
    channel.ioloop = loop
    channel._channel = MagicMock()
    channel._channel.is_open = True
    channel.rpc_publisher_started = True
    channel._channel_rpc = MagicMock()
    channel._channel_rpc.is_open = True

    async def my_dict_handler(body):
        return {"status": "success", "user_id": 42}

    channel.subscribes["rpc_queue"] = {
        "user.get": {
            "handle": my_dict_handler,
            "content_type": "application/json",
            "response_timeout": 5,
            "auto_decode": True,
        }
    }

    deliver = MagicMock()
    deliver.routing_key = "user.get"
    deliver.delivery_tag = 101

    props = BasicProperties(
        reply_to="amq.gen-reply",
        correlation_id="corr-1234",
    )

    published = loop.create_future()
    channel._channel_rpc.basic_publish = MagicMock(
        side_effect=lambda *args, **kwargs: not published.done() and published.set_result(True)
    )

    channel.on_message("rpc_queue", channel._channel, deliver, props, b"{}")
    await asyncio.wait_for(published, timeout=5.0)

    assert channel._channel_rpc.basic_publish.called
    args, kwargs = channel._channel_rpc.basic_publish.call_args
    assert args[0] == ""
    assert args[1] == "amq.gen-reply"
    assert isinstance(args[2], (bytes, str))
    assert '"status": "success"' in args[2] or b'"status": "success"' in args[2]
