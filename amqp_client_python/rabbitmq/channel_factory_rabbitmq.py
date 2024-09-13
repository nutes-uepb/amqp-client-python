from typing import Callable
from pika import SelectConnection
from pika.channel import Channel


class ChannelFactoryRabbitMQ:
    def create_channel(self, connection: SelectConnection, on_channel_open: Callable[[Channel], None]) -> Channel:
        return connection.channel(on_open_callback=on_channel_open)
