from .async_eventbus_rabbitmq import AsyncEventbusRabbitMQ
from ..event import IntegrationEvent, IntegrationEventHandler
from ..exceptions import BlockingException, ThreadUnsafeException
from amqp_client_python.domain.models import Config
from typing import Any, List
from threading import Thread, current_thread
from asyncio import new_event_loop, run_coroutine_threadsafe
from concurrent.futures import Future


class EventbusWrapperRabbitMQ:
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
        self._loop = loop or new_event_loop()
        self._async_eventbus = AsyncEventbusRabbitMQ(
            config,
            self._loop,
            pub_publisher_confirms,
            rpc_client_publisher_confirms,
            rpc_server_publisher_confirms,
            sub_prefetch_count,
            rpc_client_prefetch_count,
            rpc_server_prefetch_count,
            sub_auto_ack,
            rpc_client_auto_ack,
            rpc_server_auto_ack,
        )
        self._thread = Thread(target=self._loop.run_forever)
        self._thread.start()

    def rpc_client(
        self,
        exchange: str,
        routing_key: str,
        body: List[Any],
        content_type="application/json",
        timeout=5,
    ) -> Future:
        if self._thread.ident == current_thread().ident:
            raise BlockingException(
                "Cannot run sync blocking call on async thread, try to use async methods with an await expression"
            )
        return run_coroutine_threadsafe(
            self._async_eventbus.rpc_client(
                exchange, routing_key, body, content_type, timeout
            ),
            self._loop,
        )

    async def async_rpc_client(
        self,
        exchange: str,
        routing_key: str,
        body: List[Any],
        content_type="application/json",
        timeout=5,
    ):
        if self._thread.ident != current_thread().ident:
            raise ThreadUnsafeException(
                "Cannot run async call on this thread, try to use sync thread safe methods"
            )
        return await self._async_eventbus.rpc_client(
            exchange, routing_key, body, content_type, timeout
        )

    async def async_publish(
        self,
        event: IntegrationEvent,
        routing_key: str,
        body: List[Any],
        content_type="application/json",
        exchange_type: str = "direct",
        exchange_durable=True,
        timeout=5,
    ):
        if self._thread.ident != current_thread().ident:
            raise ThreadUnsafeException(
                "Cannot run async call on this thread, try to use sync thread safe methods"
            )
        await self._async_eventbus.publish(
            event,
            routing_key,
            body,
            content_type,
            exchange_type,
            exchange_durable,
            timeout,
        )

    def publish(
        self,
        event: IntegrationEvent,
        routing_key: str,
        body: List[Any],
        content_type="application/json",
        exchange_type: str = "direct",
        exchange_durable=True,
    ) -> Future:
        if self._thread.ident == current_thread().ident:
            raise BlockingException(
                "Cannot run sync blocking call on async thread, try to use async methods with an await expression"
            )
        return run_coroutine_threadsafe(
            self._async_eventbus.publish(
                event, routing_key, body, content_type, exchange_type, exchange_durable
            ),
            self._loop,
        )

    def subscribe(
        self,
        event: IntegrationEvent,
        handler: IntegrationEventHandler,
        routing_key: str,
        response_timeout: int = None,
    ) -> Future:
        if self._thread.ident == current_thread().ident:
            raise BlockingException(
                "Cannot run sync blocking call on async thread, try to use async methods with an await expression"
            )
        return run_coroutine_threadsafe(
            self._async_eventbus.subscribe(
                event, handler, routing_key, response_timeout
            ),
            self._loop,
        )

    async def async_subscribe(
        self,
        event: IntegrationEvent,
        handler: IntegrationEventHandler,
        routing_key: str,
        response_timeout: int = None,
    ):
        if self._thread.ident != current_thread().ident:
            raise ThreadUnsafeException(
                "Cannot run async call on this thread, try to use sync thread safe methods"
            )
        await self._async_eventbus.subscribe(
            event, handler, routing_key, response_timeout
        )

    def provide_resource(
        self, name: str, callback, response_timeout: int = None
    ) -> Future:
        if self._thread.ident == current_thread().ident:
            raise BlockingException(
                "Cannot run sync blocking call on async thread, try to use async methods with an await expression"
            )
        return run_coroutine_threadsafe(
            self._async_eventbus.provide_resource(name, callback, response_timeout),
            self._loop,
        )

    async def async_provide_resource(
        self, name: str, callback, response_timeout: int = None
    ):
        if self._thread.ident != current_thread().ident:
            raise ThreadUnsafeException(
                "Cannot run async call on this thread, try to use sync thread safe methods"
            )
        await self._async_eventbus.provide_resource(name, callback, response_timeout)

    def dispose(self):
        run_coroutine_threadsafe(self._async_eventbus.dispose(), self._loop)

    async def async_dispose(self, stop_event_loop=True):
        if self._thread.ident != current_thread().ident:
            raise ThreadUnsafeException(
                "Cannot run async call on this thread, try to use sync thread safe methods"
            )
        await self._async_eventbus.dispose(stop_event_loop=stop_event_loop)
