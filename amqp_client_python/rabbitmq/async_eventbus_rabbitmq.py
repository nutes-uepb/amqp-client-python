from .async_connection import AsyncConnection
from ..event import IntegrationEvent, IntegrationEventHandler
from amqp_client_python.domain.models import Config
from typing import Any, List
from asyncio import AbstractEventLoop


class AsyncEventbusRabbitMQ:

    def __init__(self, config: Config, loop=None, pub_publisher_confirms=True, rpc_client_publisher_confirms=True, rpc_server_publisher_confirms=False) -> None:
        self.loop: AbstractEventLoop = loop
        self._pub_connection = AsyncConnection(self.loop, pub_publisher_confirms)
        self._sub_connection = AsyncConnection(self.loop)
        self._rpc_client_connection = AsyncConnection(self.loop, rpc_client_publisher_confirms)
        self._rpc_server_connection = AsyncConnection(self.loop, rpc_server_publisher_confirms)
        self.config = config.build()
        self._rpc_server_initialized = False


    async def rpc_client(self, exchange: str, routing_key: str, body: List[Any], content_type="application/json", timeout=5):
        async def add_rpc_client():
            return await self._rpc_client_connection.rpc_client(exchange, routing_key, body, content_type=content_type, timeout=timeout)
        self._rpc_client_connection.open(self.config.url)
        return await self._rpc_client_connection.add_callback(add_rpc_client)
    
    async def publish(self, event: IntegrationEvent, routing_key: str, body: List[Any], content_type="application/json", exchange_type: str = "direct", exchange_durable=True):
        async def add_publish():
            return await self._pub_connection.publish(event.event_type, routing_key, body, content_type=content_type)
        self._pub_connection.open(self.config.url)
        return await self._pub_connection.add_callback(add_publish)

    async def provide_resource(self, name: str, callback, auto_ack=False):
        async def add_resource():
            await self._rpc_server_connection.rpc_subscribe(self.config.options.rpc_queue_name, self.config.options.rpc_exchange_name,
                    name, callback, auto_ack)
        self._rpc_server_connection.open(self.config.url)
        await self._rpc_server_connection.add_callback(add_resource)
    
    async def subscribe(self, event: IntegrationEvent, handler: IntegrationEventHandler, routing_key: str, auto_ack=False):
        async def add_subscribe():
            await self._sub_connection.subscribe(self.config.options.queue_name, event.event_type,
                    routing_key, handler.handle, auto_ack)
        self._sub_connection.open(self.config.url)
        await self._sub_connection.add_callback(add_subscribe)

    async def dispose(self):
        await self._pub_connection.close()
        await self._sub_connection.close()
        await self._rpc_client_connection.close()
        await self._rpc_server_connection.close()