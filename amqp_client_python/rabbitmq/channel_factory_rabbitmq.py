from pika import SelectConnection


class ChannelFactoryRabbitMQ:
    def create_channel(self, connection: SelectConnection, on_channel_open: callable):
        return connection.channel(on_open_callback=on_channel_open)
