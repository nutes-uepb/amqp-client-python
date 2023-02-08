from amqp_client_python.rabbitmq import AsyncChannel


def test_channel_open(connection_mock, channel_mock, channel_factory_mock):
    channel_factory_mock.create_channel.return_value = channel_mock
    channel = AsyncChannel(channel_factory=channel_factory_mock)
    assert not channel.is_open
    channel.open(connection_mock)
    channel_factory_mock.create_channel.assert_called_once()
    assert channel.is_open
    assert channel._connection == connection_mock
    assert channel.ioloop == connection_mock.ioloop
    assert channel._channel == channel_mock
