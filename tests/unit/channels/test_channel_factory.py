from amqp_client_python.rabbitmq import (
    AsyncChannelFactoryRabbitMQ,
    ChannelFactoryRabbitMQ,
)
from pika.channel import Channel
import pytest


@pytest.mark.parametrize(
    "channel_factory", [AsyncChannelFactoryRabbitMQ, ChannelFactoryRabbitMQ]
)
@pytest.mark.asyncio_cooperative
async def test_channel_factory(connection_mock, channel_factory):
    def on_open(_):
        pass

    channel_factory = channel_factory()
    connection_mock.channel.return_value = Channel(connection_mock, 1, on_open)
    result = channel_factory.create_channel(connection_mock, on_open)
    connection_mock.channel.assert_called_once_with(on_open_callback=on_open)
    assert isinstance(result, Channel)
