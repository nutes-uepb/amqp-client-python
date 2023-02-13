from pika.adapters.asyncio_connection import AsyncioConnection


class AsyncChannelFactoryRabbitMQ:
    def create_channel(self, connection: AsyncioConnection, on_channel_open: callable):
        return connection.channel(on_open_callback=on_channel_open)
