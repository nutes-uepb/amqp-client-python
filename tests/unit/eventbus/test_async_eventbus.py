from amqp_client_python import AsyncEventbusRabbitMQ
from asyncio import iscoroutinefunction
import pytest
from unittest.mock import AsyncMock


@pytest.mark.asyncio_cooperative
async def test_async_eventbus_build_config(config_mock):
    AsyncEventbusRabbitMQ(config_mock)
    config_mock.build.assert_called_once()


@pytest.mark.asyncio_cooperative
async def test_async_eventbus_dispose(config_mock):
    eventbus = AsyncEventbusRabbitMQ(config_mock)
    eventbus._pub_connection = AsyncMock()
    eventbus._sub_connection = AsyncMock()
    eventbus._rpc_client_connection = AsyncMock()
    eventbus._rpc_server_connection = AsyncMock()
    assert iscoroutinefunction(eventbus.dispose)
    assert await eventbus.dispose() is None
    eventbus._pub_connection.close.assert_called_once()
    eventbus._sub_connection.close.assert_called_once()
    eventbus._rpc_client_connection.close.assert_called_once()
    eventbus._rpc_server_connection.close.assert_called_once()
