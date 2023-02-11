from amqp_client_python import AsyncEventbusRabbitMQ
from asyncio import iscoroutinefunction
from tests.unit.eventbus.default import async_add_callback
import pytest


@pytest.mark.asyncio_cooperative
async def test_async_eventbus_provide_resource_surface(
    async_connection_mock, config_mock
):
    routing_key = "rk_example"
    eventbus = AsyncEventbusRabbitMQ(config_mock)
    eventbus._rpc_server_connection = async_connection_mock

    async def handle(*body):
        return b"result"

    assert iscoroutinefunction(eventbus.provide_resource)
    assert await eventbus.provide_resource(routing_key, handle) is None
    # test connection will be open
    eventbus._rpc_server_connection.open.assert_called_once_with(
        config_mock.build().url
    )
    # test if will try when connection and channel is open
    eventbus._rpc_server_connection.add_callback.called_once()
    assert len(eventbus._rpc_server_connection.add_callback.call_args.args) == 1
    iscoroutinefunction(eventbus._rpc_server_connection.add_callback.call_args.args[0])


@pytest.mark.asyncio_cooperative
async def test_async_eventbus_provide_resource_deep(async_connection_mock, config_mock):
    routing_key = "rk_example"
    config = config_mock.build()
    eventbus = AsyncEventbusRabbitMQ(config_mock)
    eventbus._rpc_server_connection = async_connection_mock
    eventbus._rpc_server_connection.add_callback = async_add_callback

    async def handle(*body):
        return b"result"

    assert iscoroutinefunction(eventbus.provide_resource)
    assert await eventbus.provide_resource(routing_key, handle) is None
    # test connection will be open
    eventbus._rpc_server_connection.open.assert_called_once_with(
        config_mock.build().url
    )
    # test if will try when connection and channel is open
    eventbus._rpc_server_connection.rpc_subscribe.assert_called_once_with(
        config.options.rpc_queue_name,
        config.options.rpc_exchange_name,
        routing_key,
        handle,
    )
