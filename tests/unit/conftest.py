from amqp_client_python.rabbitmq import AsyncConnection, AsyncChannelFactoryRabbitMQ
from unittest.mock import Mock, MagicMock, AsyncMock
import pytest


@pytest.fixture
async def connection_mock():
    mock = Mock()
    yield mock
    mock.reset_mock()


@pytest.fixture
async def async_connection_mock():
    mock = AsyncMock(AsyncConnection)
    mock.ioloop = Mock()
    yield mock
    mock.reset_mock()


@pytest.fixture
async def channel_factory_mock():
    mock = Mock()
    yield mock
    mock.reset_mock()


@pytest.fixture
async def channel_mock():
    mock = Mock()
    yield mock
    mock.reset_mock()


@pytest.fixture
async def config_mock():
    mock = Mock()
    yield mock
    mock.reset_mock()
