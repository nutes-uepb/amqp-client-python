from .async_eventbus_rabbitmq import AsyncEventbusRabbitMQ
from ..event import IntegrationEvent, IntegrationEventHandler
from amqp_client_python.domain.models import Config
from typing import Any, List
from threading import Thread
from .ioloop_factory import IOLoopFactory
import asyncio
from concurrent.futures import Future


class EventbusWrapperRabbitMQ:

    def __init__(self, config: Config, loop=None, pub_publisher_confirms=True, rpc_client_publisher_confirms=True, rpc_server_publisher_confirms=False,
                sub_prefetch_count=0, rpc_client_prefetch_count=0,rpc_server_prefetch_count=0,
                sub_auto_ack=False, rpc_client_auto_ack=False, rpc_server_auto_ack=False,
                ) -> None:
        self.loop = loop or asyncio.new_event_loop()
        self.async_eventbus = AsyncEventbusRabbitMQ(config, self.loop, pub_publisher_confirms, rpc_client_publisher_confirms, rpc_server_publisher_confirms,
                                                    sub_prefetch_count, rpc_client_prefetch_count, rpc_server_prefetch_count,
                                                    sub_auto_ack, rpc_client_auto_ack, rpc_server_auto_ack)
        self.thread = Thread(target=self.loop.run_forever)
        self.thread.start()

    def rpc_client(self, exchange: str, routing_key: str, body: List[Any], content_type="application/json", timeout=5) -> Future:
        return asyncio.run_coroutine_threadsafe(self.async_eventbus.rpc_client(exchange, routing_key, body, content_type, timeout), self.loop)
    
    async def async_rpc_client(self, exchange: str, routing_key: str, body: List[Any], content_type="application/json", timeout=5):
        await self.async_eventbus.rpc_client(exchange, routing_key, body, content_type, timeout)

    async def async_publish(self, event: IntegrationEvent, routing_key: str, body: List[Any], content_type="application/json", exchange_type: str = "direct", exchange_durable=True, timeout=5):
        await self.async_eventbus.publish(event, routing_key, body, content_type, exchange_type, exchange_durable, timeout)

    def publish(self, event: IntegrationEvent, routing_key: str, body: List[Any], content_type="application/json", exchange_type: str = "direct", exchange_durable=True) -> Future:
        return asyncio.run_coroutine_threadsafe(self.async_eventbus.publish(event, routing_key, body, content_type, exchange_type, exchange_durable), self.loop)

    def subscribe(self, event: IntegrationEvent, handler: IntegrationEventHandler, routing_key: str) -> Future:
        return asyncio.run_coroutine_threadsafe(self.async_eventbus.subscribe(event, handler, routing_key), self.loop)

    def provide_resource(self, name: str, callback)-> Future:
        return asyncio.run_coroutine_threadsafe(self.async_eventbus.provide_resource(name, callback), self.loop)

    def dispose(self):
        asyncio.run_coroutine_threadsafe(self.async_eventbus.dispose(), self.loop)
        self.loop.stop()
