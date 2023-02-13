from amqp_client_python.rabbitmq import AsyncChannel
from amqp_client_python.exceptions import NackException
from unittest.mock import Mock
from asyncio import get_running_loop
import pytest
from random import randint


@pytest.mark.asyncio_cooperative
async def test_channel_open_surface(
    async_connection_mock, channel_mock, channel_factory_mock
):
    channel_factory_mock.create_channel.return_value = channel_mock
    channel = AsyncChannel(channel_factory=channel_factory_mock)
    assert not channel.is_open
    channel.open(async_connection_mock)
    channel_factory_mock.create_channel.assert_called_once()
    assert channel.is_open
    assert channel._connection == async_connection_mock
    assert channel.ioloop == async_connection_mock.ioloop
    assert channel._channel == channel_mock


@pytest.mark.parametrize("prefetch", [0, 1, 2])
@pytest.mark.parametrize("pub_confirm", [True, False])
@pytest.mark.asyncio_cooperative
async def test_channel_open_deep(
    async_connection_mock, channel_mock, channel_factory_mock, pub_confirm, prefetch
):
    channel_factory_mock.create_channel = (
        lambda connection, on_channel_open: on_channel_open(channel_mock)
    )
    channel = AsyncChannel(
        prefetch_count=prefetch, channel_factory=channel_factory_mock
    )
    channel.publisher_confirms = pub_confirm
    channel.add_on_channel_close_callback = Mock()
    channel.add_publish_confirms = Mock()
    channel.set_qos = Mock()
    assert not channel.is_open
    channel.open(async_connection_mock)
    channel.add_on_channel_close_callback.assert_called_once()
    pub_confirm and channel.add_publish_confirms.assert_called_once()
    if prefetch:
        channel.set_qos.assert_called_once_with(channel._prefetch_count)
    else:
        channel.set_qos.assert_not_called()


@pytest.mark.asyncio_cooperative
async def test_channel_add_on_close_callback(channel_mock, channel_factory_mock):
    channel_factory_mock.create_channel = (
        lambda connection, on_channel_open: on_channel_open(channel_mock)
    )
    channel = AsyncChannel()
    channel._channel = Mock()
    channel.on_channel_closed = Mock()
    channel.add_on_channel_close_callback()
    channel._channel.add_on_close_callback.assert_called_once_with(
        channel.on_channel_closed
    )


@pytest.mark.parametrize("is_closing", [True, False])
@pytest.mark.parametrize("closed", [True, False])
@pytest.mark.asyncio_cooperative
async def test_channel_on_channel_closed(channel_mock, is_closing, closed):
    channel = AsyncChannel()
    channel._connection = Mock()
    channel._connection.is_closing = is_closing
    channel._connection.is_closed = closed
    assert callable(channel.on_channel_closed)
    assert channel.on_channel_closed(channel_mock, None) is None
    if is_closing or closed:
        channel._connection.close.assert_not_called()
    else:
        channel._connection.close.assert_called_once()


@pytest.mark.asyncio_cooperative
async def test_channel_add_publish_confirms(channel_mock, channel_factory_mock):
    channel_factory_mock.create_channel = (
        lambda connection, on_channel_open: on_channel_open(channel_mock)
    )
    channel = AsyncChannel()
    channel._channel = Mock()
    channel.confirm_delivery = Mock()
    channel.add_publish_confirms()
    assert channel._acked == 0
    assert channel._nacked == 0
    assert channel._deliveries == {}
    assert channel._message_number == 0
    channel._channel.confirm_delivery.assert_called_once_with(
        channel.on_delivery_confirmation
    )


@pytest.mark.parametrize("confimation_type", ["ack", "nack"])
@pytest.mark.parametrize("done", [True, False])
@pytest.mark.asyncio_cooperative
async def test_channel_on_delivery_confirmation(confimation_type, done):
    loop = get_running_loop()
    delivery_tag = randint(0, 10000)
    future = loop.create_future()
    done and future.set_result(True)
    channel = AsyncChannel()
    channel._acked = delivery_tag - 1
    channel._nacked = delivery_tag - 1
    channel._deliveries[delivery_tag] = future
    method_frame = Mock()
    method_frame.method.NAME.split.return_value = ["njashdu13", confimation_type]
    method_frame.method.delivery_tag = delivery_tag
    channel.on_delivery_confirmation(method_frame)
    if confimation_type == "ack":
        assert future.done()
        assert channel._acked == delivery_tag
    elif confimation_type == "nack":
        assert future.done()
        assert channel._nacked == delivery_tag
        if not done:
            with pytest.raises(NackException):
                await future
