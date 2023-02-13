from .connection_rabbitmq import ConnectionRabbitMQ
from ..event import IntegrationEvent, IntegrationEventHandler
from amqp_client_python.domain.models import Config
from typing import Any, List
from threading import Thread
from .ioloop_factory import IOLoopFactory
from concurrent.futures import Future as syncFuture
from asyncio import AbstractEventLoop
import asyncio


class EventbusRabbitMQ:
    def __init__(self, config: Config) -> None:
        self.pub_connection = ConnectionRabbitMQ()
        self.sub_connection = ConnectionRabbitMQ()
        self.rpc_client_connection = ConnectionRabbitMQ()
        self.rpc_server_connection = ConnectionRabbitMQ()
        self.config = config.build()
        self._rpc_server_initialized = False
        self.thread = Thread(target=IOLoopFactory.start).start()

    @property
    def event_loop(self):
        return IOLoopFactory.get_ioloop()

    def rpc_client(
        self,
        exchange: str,
        routing_key: str,
        body: List[Any],
        content_type="application/json",
        timeout=5,
    ):
        promise = syncFuture()

        def add_rpc_client():
            def on_channel_openned():
                self.rpc_client_connection.rpc_client(
                    exchange,
                    routing_key,
                    body,
                    content_type=content_type,
                    future=promise,
                    timeout=timeout,
                )

            self.rpc_client_connection.open(self.config.url, ioloop=self.event_loop)
            self.rpc_client_connection.add_callback(on_channel_openned)

        self.event_loop.add_callback_threadsafe(add_rpc_client)
        return promise.result(timeout)

    async def async_rpc_client(
        self,
        exchange: str,
        routing_key: str,
        body: List[Any],
        content_type="application/json",
        timeout=5,
        loop: AbstractEventLoop = None,
    ):
        promise = loop.create_future()

        def on_channel_openned():
            self.rpc_client_connection.rpc_client(
                exchange,
                routing_key,
                body,
                content_type=content_type,
                future=promise,
                timeout=timeout,
            )

        self.rpc_client_connection.open(self.config.url, ioloop=self.event_loop)
        self.rpc_client_connection.add_callback(on_channel_openned)
        while not promise.done():
            await asyncio.sleep(0.002)
        return promise.result()

    def publish(
        self,
        event: IntegrationEvent,
        routing_key: str,
        exchange_type: str = "direct",
        exchange_durable=True,
    ):
        def add_publish():
            def after_channel_openned():
                self.pub_connection.declare_exchange(
                    event.event_type, exchange_type, durable=exchange_durable
                )
                self.pub_connection.publish(
                    event.event_type, routing_key=routing_key, message=event.message
                )

            self.pub_connection.open(self.config.url, ioloop=self.event_loop)
            self.pub_connection.add_callback(after_channel_openned)

        self.event_loop.add_callback_threadsafe(add_publish)

    def subscribe(
        self,
        event: IntegrationEvent,
        handler: IntegrationEventHandler,
        routing_key: str,
        exchange_type: str = "direct",
        exchange_durable=True,
        queue_durable=True,
        queue_auto_delete=False,
    ):
        def add_subscribe():
            def after_channel_openned():
                self.sub_connection.declare_exchange(
                    event.event_type, exchange_type, durable=exchange_durable
                )
                self.sub_connection.declare_queue(
                    self.config.options.queue_name,
                    durable=queue_durable,
                    auto_delete=queue_auto_delete,
                )
                self.sub_connection.subscribe(
                    self.config.options.queue_name,
                    event.event_type,
                    routing_key,
                    callback=handler.handle,
                    auto_ack=True,
                )

            self.sub_connection.open(self.config.url, ioloop=self.event_loop)
            self.sub_connection.add_callback(after_channel_openned)

        self.event_loop.add_callback_threadsafe(add_subscribe)

    def provide_resource(self, name: str, callback):
        self.initialize_rpc_server()

        def add_provider():
            def after_channel_oppened():
                self.rpc_server_connection.rpc_subscribe(
                    self.config.options.rpc_queue_name,
                    self.config.options.rpc_exchange_name,
                    name,
                    callback=callback,
                )

            self.rpc_server_connection.add_callback(after_channel_oppened)

        self.event_loop.add_callback_threadsafe(add_provider)

    def initialize_rpc_server(self):
        if not self._rpc_server_initialized:

            def rpc_server_setup():
                def after_channel_openned():
                    self.rpc_server_connection.declare_exchange(
                        self.config.options.rpc_exchange_name, "direct"
                    )
                    self.rpc_server_connection.declare_queue(
                        self.config.options.rpc_queue_name, durable=False
                    )
                    self._rpc_server_initialized = True

                self.rpc_server_connection.open(self.config.url, ioloop=self.event_loop)
                self.rpc_server_connection.add_callback(after_channel_openned)

            self.event_loop.add_callback_threadsafe(rpc_server_setup)

    def dispose(self):
        if isinstance(self.pub_connection, ConnectionRabbitMQ):
            self.pub_connection.close()
        if isinstance(self.sub_connection, ConnectionRabbitMQ):
            self.sub_connection.close()
        if isinstance(self.rpc_client_connection, ConnectionRabbitMQ):
            self.rpc_client_connection.close()
        if isinstance(self.rpc_server_connection, ConnectionRabbitMQ):
            self.rpc_server_connection.close()
