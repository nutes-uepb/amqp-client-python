from amqp_client_python import AsyncEventbusRabbitMQ
from asyncio import iscoroutinefunction
from tests.unit.eventbus.default import async_add_callback
import pytest


@pytest.mark.asyncio_cooperative
async def test_async_eventbus_rpc_client_surface(async_connection_mock, config_mock):
    exchange, routing_key, body, content_type, timeout = (
        "ex_example",
        "rk_example",
        ["content"],
        "text",
        4,
    )
    eventbus = AsyncEventbusRabbitMQ(config_mock)
    eventbus._rpc_client_connection = async_connection_mock

    assert iscoroutinefunction(eventbus.rpc_client)
    assert (
        await eventbus.rpc_client(exchange, routing_key, body, content_type, timeout)
        is not None
    )
    # test connection will be open
    eventbus._rpc_client_connection.open.assert_called_once_with(
        config_mock.build().url
    )
    # test if will try when connection and channel is open
    eventbus._rpc_client_connection.add_callback.called_once()
    assert len(eventbus._rpc_client_connection.add_callback.call_args.args) == 1
    iscoroutinefunction(eventbus._rpc_client_connection.add_callback.call_args.args[0])


@pytest.mark.asyncio_cooperative
async def test_async_eventbus_rpc_client_deep(async_connection_mock, config_mock):
    exchange, routing_key, body, content_type, timeout = (
        "ex_example",
        "rk_example",
        ["content"],
        "text",
        4,
    )
    eventbus = AsyncEventbusRabbitMQ(config_mock)
    eventbus._rpc_client_connection = async_connection_mock
    eventbus._rpc_client_connection.add_callback = async_add_callback

    assert iscoroutinefunction(eventbus.rpc_client)
    assert (
        await eventbus.rpc_client(exchange, routing_key, body, content_type, timeout)
        is not None
    )
    # test connection will be open
    eventbus._rpc_client_connection.open.assert_called_once_with(
        config_mock.build().url
    )
    # test if will try when connection and channel is open
    eventbus._rpc_client_connection.rpc_client.assert_called_once_with(
        exchange, routing_key, body, content_type=content_type, timeout=timeout
    )
