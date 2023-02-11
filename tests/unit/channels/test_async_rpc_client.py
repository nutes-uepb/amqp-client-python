from amqp_client_python.rabbitmq import AsyncChannel
from amqp_client_python.exceptions import (
    PublishTimeoutException,
    ResponseTimeoutException,
    EventBusException,
)
from asyncio import iscoroutine, Future, wait_for, get_running_loop
import pytest
from json import dumps


@pytest.mark.asyncio_cooperative
async def test_rpc_client(connection_mock, channel_mock, channel_factory_mock):
    exchange, routing_key, body, content_type, timeout = (
        "ex_example",
        "rk_example",
        "bd_example",
        "content_example",
        1,
    )
    expected_result = b"result"
    future_publish = Future()
    future_response = Future()
    future_consumer = Future()
    future_publish.set_result(True)
    future_response.set_result(expected_result)
    future_consumer.set_result(True)
    connection_mock.ioloop.create_future.side_effect = [
        future_response,
        future_publish,
        future_consumer,
    ]
    channel_factory_mock.create_channel.return_value = channel_mock
    channel = AsyncChannel(channel_factory=channel_factory_mock)
    channel.publisher_confirms = False
    channel.open(connection_mock)
    rpc_client = channel.rpc_client(
        exchange, routing_key, body, content_type, timeout, connection_mock.ioloop
    )
    assert iscoroutine(rpc_client)
    result = await rpc_client
    assert channel.rpc_consumer
    channel_mock.basic_publish.assert_called_once()
    assert channel_mock.basic_publish.call_args.args == (
        exchange,
        routing_key,
        dumps({"resource_name": routing_key, "handle": body}),
    )
    assert result == expected_result


@pytest.mark.parametrize("answered", [True])
@pytest.mark.parametrize("published", [True, False])
@pytest.mark.asyncio_cooperative
async def test_rpc_client_publish_confirmation(
    connection_mock, channel_mock, channel_factory_mock, answered, published
):
    loop = get_running_loop()
    exchange, routing_key, body, content_type, timeout = (
        "ex_example",
        "rk_example",
        "bd_example",
        "content_example",
        1,
    )
    result = b"result"
    future_response = Future()
    future_publish = Future()
    future_consumer = Future()
    future_consumer.set_result(True)
    connection_mock.ioloop.create_future.side_effect = [
        future_response,
        future_publish,
        future_consumer,
    ]
    connection_mock.ioloop.call_later = loop.call_later
    channel_factory_mock.create_channel.return_value = channel_mock
    channel = AsyncChannel(channel_factory=channel_factory_mock)
    channel.publisher_confirms = True
    channel.open(connection_mock)
    rpc_client = channel.rpc_client(
        exchange, routing_key, body, content_type, timeout, connection_mock.ioloop
    )
    if published:
        future_publish.set_result(True)
        if answered:
            future_response.set_result(result)
            assert result == await rpc_client
            assert channel.rpc_consumer
        else:
            with pytest.raises(ResponseTimeoutException):
                result = await wait_for(rpc_client, timeout=timeout + 1)
    else:
        with pytest.raises(PublishTimeoutException):
            result = await wait_for(rpc_client, timeout=timeout + 1)


@pytest.mark.parametrize("consumer", [True, False])
@pytest.mark.asyncio_cooperative
async def test_rpc_client_consumer_started(
    connection_mock, channel_mock, channel_factory_mock, consumer
):
    loop = get_running_loop()
    exchange, routing_key, body, content_type, timeout = (
        "ex_example",
        "rk_example",
        "bd_example",
        "content_example",
        1,
    )
    result = b"result"
    future_response = Future()
    future_publish = Future()
    future_consumer = Future()
    future_response.set_result(result)
    future_publish.set_result(True)
    if consumer:
        future_consumer.set_result(True)
    connection_mock.ioloop.create_future.side_effect = [
        future_response,
        future_publish,
        future_consumer,
    ]
    connection_mock.ioloop.call_later = loop.call_later
    channel_factory_mock.create_channel.return_value = channel_mock
    channel = AsyncChannel(channel_factory=channel_factory_mock)
    channel.publisher_confirms = True
    channel.open(connection_mock)
    rpc_client = channel.rpc_client(
        exchange, routing_key, body, content_type, timeout, connection_mock.ioloop
    )
    if consumer:
        assert result == await rpc_client
        assert channel.rpc_consumer is True
    else:
        with pytest.raises(EventBusException):
            assert result == await wait_for(rpc_client, timeout=2.5)
        assert channel.rpc_consumer is False
