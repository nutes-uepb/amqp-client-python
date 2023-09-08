from typing import Callable, Awaitable, Optional, Union, Any, List
from .async_connection import AsyncConnection
from ..domain.utils import ConnectionType
from ..event import IntegrationEvent, AsyncSubscriberHandler
from amqp_client_python.domain.models import Config
from asyncio import AbstractEventLoop
from pika import DeliveryMode
from amqp_client_python.signals import Signal


class AsyncEventbusRabbitMQ:
    def __init__(
        self,
        config: Config,
        loop: Optional[AbstractEventLoop] = None,
        pub_publisher_confirms: bool = True,
        rpc_client_publisher_confirms: bool = True,
        rpc_server_publisher_confirms: bool = False,
        sub_prefetch_count: int = 0,
        rpc_client_prefetch_count: int = 0,
        rpc_server_prefetch_count: int = 0,
        sub_auto_ack: bool = False,
        rpc_client_auto_ack: bool = False,
        rpc_server_auto_ack: bool = False,
    ) -> None:
        """
        Create an AsyncEventbusRabbitMQ object thats interacts with Bus
        thats provides some connection management abstractions.

        Args:
            config: the Config object
            loop: pass an event loop object
            pub_publisher_confirms: set True to allow publisher confirmations on pub connectio
            rpc_client_publisher_confirms: set True to allow publisher confirmations on rpc client connection
            rpc_server_publisher_confirms: set True to allow publisher confirmations on rpc server connection
            sub_prefetch_count: set how many messages to prefetch on sub connection
            rpc_client_prefetch_count: set how many messages to prefetch on rpc client connection
            rpc_server_prefetch_count: set how many messages to prefetch on rpc server connection
            sub_auto_ack: set to True to ack messages before processing on sub connection
            rpc_client_auto_ack: set to True to ack messages before processing on rpc client connection
            rpc_server_auto_ack: set to True to ack messages before processing on rpc server connection

        Returns:
            AsyncEventbusRabbitMQ object

        Raises:

        Examples:
            >>> async_eventbus = AsyncEventbusRabbitMQ(
                config, loop, rpc_client_publisher_confirms=True,
                rpc_server_publisher_confirms=False, rpc_server_auto_ack=False)
            ### register subscribe
            >>> def handler(*body):
                    print(f"do something with: {body}")
            >>> subscribe_event = ExampleEvent("rpc_exchange")
            >>> await eventbus.subscribe(subscribe_event, handler, "user.find")
            ### provide resource
            >>> def handler2(*body):
                    print(f"do something with: {body}")
                    return "response"
            >>> await eventbus.provide_resource("user.find2", handle2)
        """
        self._loop: AbstractEventLoop = loop
        self._signal = Signal()
        self._pub_connection = AsyncConnection(
            self._loop,
            pub_publisher_confirms,
            connection_type=ConnectionType.PUBLISH,
            signal=self._signal
        )
        self._sub_connection = AsyncConnection(
            self._loop, False,
            sub_prefetch_count,
            sub_auto_ack,
            connection_type=ConnectionType.SUBSCRIBE,
            signal=self._signal
        )
        self._rpc_client_connection = AsyncConnection(
            self._loop,
            rpc_client_publisher_confirms,
            rpc_client_prefetch_count,
            rpc_client_auto_ack,
            connection_type=ConnectionType.RPC_CLIENT,
            signal=self._signal
        )
        self._rpc_server_connection = AsyncConnection(
            self._loop,
            rpc_server_publisher_confirms,
            rpc_server_prefetch_count,
            rpc_server_auto_ack,
            connection_type=ConnectionType.RPC_SERVER,
            signal=self._signal
        )
        self.on = self._signal.on
        self.config = config.build()
        self._rpc_server_initialized = False

    async def rpc_client(
        self,
        exchange: str,
        routing_key: str,
        body: List[Any],
        content_type="application/json",
        timeout=5,
        connection_timeout: int = 16,
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
        return await self._rpc_client_connection.add_callback(add_rpc_client, connection_timeout)

    async def publish(
        self,
        event: IntegrationEvent,
        routing_key: str,
        body: List[Any],
        content_type="application/json",
        timeout=5,
        connection_timeout: int = 16,
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
        return await self._pub_connection.add_callback(add_publish, connection_timeout)

    async def provide_resource(
        self,
        name: str,
        callback: Callable[[List[Any]], Awaitable[Union[bytes, str]]],
        response_timeout: int = None,
        connection_timeout: int = 16
    ):
        async def add_resource():
            await self._rpc_server_connection.rpc_subscribe(
                self.config.options.rpc_queue_name,
                self.config.options.rpc_exchange_name,
                name,
                callback,
                response_timeout,
            )

        self._rpc_server_connection.open(self.config.url)
        await self._rpc_server_connection.add_callback(add_resource, connection_timeout)

    async def subscribe(
        self,
        event: IntegrationEvent,
        handler: AsyncSubscriberHandler,
        routing_key: str,
        response_timeout: int = None,
        connection_timeout: int = 16
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
        await self._sub_connection.add_callback(add_subscribe, connection_timeout)

    async def dispose(self, stop_event_loop=True):
        await self._pub_connection.close()
        await self._sub_connection.close()
        await self._rpc_client_connection.close()
        await self._rpc_server_connection.close()
        if stop_event_loop:
            self._loop.stop()
        self._signal.dispose()
