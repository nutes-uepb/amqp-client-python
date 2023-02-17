from typing import Any, List, Optional, Union
from .async_connection import AsyncConnection
from ..event import IntegrationEvent, IntegrationEventHandler
from amqp_client_python.domain.models import Config
from asyncio import AbstractEventLoop
from pika import DeliveryMode


class AsyncEventbusRabbitMQ:
    def __init__(
        self,
        config: Config,
        loop=None,
        pub_publisher_confirms=True,
        rpc_client_publisher_confirms=True,
        rpc_server_publisher_confirms=False,
        sub_prefetch_count=0,
        rpc_client_prefetch_count=0,
        rpc_server_prefetch_count=0,
        sub_auto_ack=False,
        rpc_client_auto_ack=False,
        rpc_server_auto_ack=False,
    ) -> None:
        self._loop: AbstractEventLoop = loop
        self._pub_connection = AsyncConnection(self._loop, pub_publisher_confirms)
        self._sub_connection = AsyncConnection(
            self._loop, False, sub_prefetch_count, sub_auto_ack
        )
        self._rpc_client_connection = AsyncConnection(
            self._loop,
            rpc_client_publisher_confirms,
            rpc_client_prefetch_count,
            rpc_client_auto_ack,
        )
        self._rpc_server_connection = AsyncConnection(
            self._loop,
            rpc_server_publisher_confirms,
            rpc_server_prefetch_count,
            rpc_server_auto_ack,
        )
        self.config = config.build()
        self._rpc_server_initialized = False

    async def rpc_client(
        self,
        exchange: str,
        routing_key: str,
        body: List[Any],
        content_type="application/json",
        timeout=5,
        delivery_mode=DeliveryMode.Transient,
        expiration: Optional[Union[str, None]] = None,
        **kwargs
    ):
        async def add_rpc_client():
            return await self._rpc_client_connection.rpc_client(
                exchange,
                routing_key,
                body,
                content_type,
                timeout,
                delivery_mode,
                expiration,
                **kwargs
            )

        self._rpc_client_connection.open(self.config.url)
        return await self._rpc_client_connection.add_callback(add_rpc_client)

    async def publish(
        self,
        event: IntegrationEvent,
        routing_key: str,
        body: List[Any],
        content_type="application/json",
        timeout=5,
        delivery_mode=DeliveryMode.Transient,
        expiration: Optional[Union[str, None]] = None,  # example: '60000' -> 60s
        **kwargs
    ):
        async def add_publish():
            return await self._pub_connection.publish(
                event.event_type,
                routing_key,
                body,
                content_type,
                timeout,
                delivery_mode,
                expiration,
                **kwargs
            )

        self._pub_connection.open(self.config.url)
        return await self._pub_connection.add_callback(add_publish)

    async def provide_resource(self, name: str, callback, response_timeout: int = None):
        async def add_resource():
            await self._rpc_server_connection.rpc_subscribe(
                self.config.options.rpc_queue_name,
                self.config.options.rpc_exchange_name,
                name,
                callback,
                response_timeout,
            )

        self._rpc_server_connection.open(self.config.url)
        await self._rpc_server_connection.add_callback(add_resource)

    async def subscribe(
        self,
        event: IntegrationEvent,
        handler: IntegrationEventHandler,
        routing_key: str,
        response_timeout: int = None,
    ):
        async def add_subscribe():
            await self._sub_connection.subscribe(
                self.config.options.queue_name,
                event.event_type,
                routing_key,
                handler.handle,
                response_timeout,
            )

        self._sub_connection.open(self.config.url)
        await self._sub_connection.add_callback(add_subscribe)

    async def dispose(self, stop_event_loop=True):
        await self._pub_connection.close()
        await self._sub_connection.close()
        await self._rpc_client_connection.close()
        await self._rpc_server_connection.close()
        if stop_event_loop:
            self._loop.stop()
