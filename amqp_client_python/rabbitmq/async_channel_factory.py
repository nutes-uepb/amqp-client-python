from typing import Callable
from pika.adapters.asyncio_connection import AsyncioConnection
from pika.channel import Channel


class AsyncChannelFactoryRabbitMQ:
    def create_channel(self, connection: AsyncioConnection, on_channel_open: Callable[[Channel], None]) -> Channel:
        return connection.channel(on_open_callback=on_channel_open)
