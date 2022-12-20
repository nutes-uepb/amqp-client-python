from typing import List
from .connection_rabbitmq import ConnectionRabbitMQ
from amqp_client_python.domain.models import Config


class EventbusRabbitMQ:
    def __init__(self, config: Config, loop=None):
        self.loop = loop
        self.config = config.build()
        self.pub_connection = ConnectionRabbitMQ()
        self.sub_connection = ConnectionRabbitMQ()
        self.rpc_client_connection = ConnectionRabbitMQ()
        self.rpc_server_connection = ConnectionRabbitMQ()

    async def rpc_client(self, exchange_name: str, routing_key: str, message: List[str], content_type="application/json", timeout=5):
        await self.rpc_client_connection.open(self.config.options, self.config.ssl_options, self.loop)
        await self.rpc_client_connection.create_channel("rpc_client")
        return await self.rpc_client_connection.rpc_client(exchange_name, routing_key, message, content_type=content_type, timeout=timeout)

    async def publish(self, exchange_name: str, routing_key: str, message: List[str], content_type="application/json"):
        await self.pub_connection.open(self.config.options, self.config.ssl_options, self.loop)
        await self.pub_connection.create_channel("publish")
        return await self.pub_connection.publish(exchange_name, routing_key, message, content_type=content_type)

    async def provide_resource(self, exchange_name, routing_key, handle: callable, content_type="application/json"):
        await self.rpc_server_connection.open(self.config.options, self.config.ssl_options, self.loop)
        await self.rpc_server_connection.create_channel("provide_resource")
        await self.rpc_server_connection.rpc_subscribe(exchange_name, routing_key, queue_name=self.config.options.rpc_queue_name, callback=handle, content_type=content_type)
    
    async def subscribe(self, exchange_name, routing_key, handle: callable, content_type="application/json"):
        await self.sub_connection.open(self.config.options, self.config.ssl_options, self.loop)
        await self.sub_connection.create_channel("subscribe")
        await self.sub_connection.subscribe(exchange_name, routing_key, queue_name=self.config.options.queue_name, callback=handle, content_type=content_type)

    async def dispose(self):
        await self.pub_connection.close()
        await self.sub_connection.close()
        await self.rpc_client_connection.close()
        await self.rpc_server_connection.close()
