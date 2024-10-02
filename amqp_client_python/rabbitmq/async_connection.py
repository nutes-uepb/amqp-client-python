from typing import Optional, Callable, Awaitable, Tuple, Dict, List, Any
from .async_connection_factory import AsyncConnectionFactoryRabbitMQ, AsyncioConnection
from .async_channel import AsyncChannel
from ..exceptions import AutoReconnectException
from asyncio import AbstractEventLoop, Future, wait_for, get_event_loop, TimeoutError
import logging
from ..domain.utils import ConnectionType
from amqp_client_python.signals import Signal, Event


LOGGER = logging.getLogger(__name__)


class AsyncConnection:
    def __init__(
        self,
        ioloop: Optional[AbstractEventLoop],
        publisher_confirms=False,
        prefetch_count=0,
        auto_ack=True,
        connection_type: Optional[ConnectionType] = None,
        signal=Signal(),
    ) -> None:
        self.ioloop = ioloop
        self.publisher_confirms = publisher_confirms
        self.connection_factory = AsyncConnectionFactoryRabbitMQ()
        self._connection: Optional[AsyncioConnection] = None
        self._prefetch_count = prefetch_count
        self._auto_ack = auto_ack
        self.signal = signal
        self._closing = False
        self._consuming = False
        self.openning = False
        self.reconnecting = False
        self.reconnect_delay = 1
        self.callbacks: List[Tuple[Callable, Future]] = []
        self.type = connection_type
        self.backup: Dict[str, Dict[str, Any]] = {
            "exchange": {},
            "queue": {},
            "subscribe": {},
            "rpc_subscribe": {},
        }

    def open(self, uri):
        self.url = uri
        if not self.is_open and not self.openning:
            if not self.ioloop:
                self.ioloop = get_event_loop()
            self.openning = True
            self._connection = self.connection_factory.create_connection(
                uri=uri,
                on_connection_open=self.on_connection_open,
                on_connection_open_error=self.on_connection_open_error,
                on_connection_closed=self.on_connection_closed,
                custum_ioloop=self.ioloop,
            )

    async def close(self):
        if self.is_open:
            self._closing = True
            self._connection.close()

    def on_connection_open(self, _unused_connection):
        LOGGER.info(f"connection openned {_unused_connection}, {self._connection}")
        self.signal.emmit(Event.CONNECTED, condiction=self.type, loop=self.ioloop)
        self.openning = False
        self._channel = AsyncChannel(
            self._prefetch_count,
            self._auto_ack,
            channel_type=self.type,
            signal=self.signal,
        )
        self._channel.publisher_confirms = self.publisher_confirms
        self._channel.open(self._connection, self.callbacks)

    def on_connection_open_error(self, _unused_connection, err):
        LOGGER.info(f"connection open error: {err}, will attempt a connection")
        self.openning = False
        self.reconnect()

    def on_connection_closed(self, _unused_connection, reason):
        """This method is invoked by pika when the connection to RabbitMQ is
        closed unexpectedly. Since it is unexpected, we will reconnect to
        RabbitMQ if it disconnects.
        :param pika.connection.Connection connection: The closed connection obj
        :param Exception reason: exception representing reason for loss of
            connection.
        """
        self._channel = None
        if self._closing:
            LOGGER.warn("connection closed intentionally")
            # self._connection.ioloop.stop()
        else:
            LOGGER.warn(
                f"Connection closed, reason: {reason}, will attempt a connection"
            )
            self.reconnect()

    def reconnect(self):
        """Will be invoked if the connection can't be opened or is
        closed. Indicates that a reconnect is necessary then stops the
        ioloop.
        """
        if not self.reconnecting:
            self.reconnecting = True
            self.retry_connection()

    def retry_connection(self):
        if not self.is_open:
            if self.reconnect_delay > 30:
                self.reconnect_delay = 30
            self.open(self.url)
            self.ioloop.call_later(  # type: ignore
                self.reconnect_delay, self.retry_connection
            )
            self.reconnect_delay += 1
        else:

            async def recorvery():
                for routing_key in self.backup["subscribe"]:
                    params = self.backup["subscribe"][routing_key]
                    await self.subscribe(
                        params["queue_name"],
                        params["exchange_name"],
                        routing_key,
                        params["callback"],
                        params["response_timeout"],
                    )
                for routing_key in self.backup["rpc_subscribe"]:
                    params = self.backup["rpc_subscribe"][routing_key]
                    await self.rpc_subscribe(
                        params["queue_name"],
                        params["exchange_name"],
                        routing_key,
                        params["callback"],
                        params["response_timeout"],
                    )

            self.ioloop.create_task(self.add_callback(recorvery))  # type: ignore
            self.reconnect_delay = 1
            self.reconnecting = False

    @property
    def is_open(self) -> Optional[bool]:
        return self._connection and self._connection.is_open

    def stop(self) -> None:
        """Cleanly shutdown the connection to RabbitMQ by stopping the consumer
        with RabbitMQ. When RabbitMQ confirms the cancellation, on_cancelok
        will be invoked by pika, which will then closing the channel and
        connection. The IOLoop is started again because this method is invoked
        when CTRL-C is pressed raising a KeyboardInterrupt exception. This
        exception stops the IOLoop which needs to be running for pika to
        communicate with RabbitMQ. All of the commands issued prior to starting
        the IOLoop will be buffered but not processed.
        """
        if not self._closing:
            self._closing = True
            LOGGER.warning("Stopping intentionally")
            if self._consuming:
                self._connection.ioloop.run_forever()  # type: ignore
            else:
                self.ioloop.stop()  # type: ignore
            LOGGER.warning("Stopped")

    async def rpc_client(
        self,
        exchange_name: str,
        routing_key: str,
        body: Any,
        content_type: str,
        timeout,
        delivery_mode,
        expiration,
        **kwargs,
    ):
        return await self._channel.rpc_client(
            exchange_name,
            routing_key,
            body,
            content_type,
            timeout,
            delivery_mode,
            expiration,
            **kwargs,
        )

    async def publish(
        self,
        exchange_name: str,
        routing_key: str,
        body: Any,
        content_type,
        timeout: float,
        delivery_mode,
        expiration,
        **kwargs,
    ):
        return await self._channel.publish(
            exchange_name,
            routing_key,
            body,
            content_type,
            timeout,
            delivery_mode,
            expiration,
            **kwargs,
        )

    async def rpc_subscribe(
        self, queue_name, exchange_name, routing_key, callback, response_timeout
    ):
        self.backup["rpc_subscribe"][routing_key] = {
            "queue_name": queue_name,
            "exchange_name": exchange_name,
            "callback": callback,
            "response_timeout": response_timeout,
        }
        await self._channel.rpc_subscribe(
            queue_name=queue_name,
            exchange_name=exchange_name,
            routing_key=routing_key,
            callback=callback,
            response_timeout=response_timeout,
        )

    async def subscribe(
        self, queue_name, exchange_name, routing_key, callback, response_timeout
    ):
        self.backup["subscribe"][routing_key] = {
            "queue_name": queue_name,
            "exchange_name": exchange_name,
            "callback": callback,
            "response_timeout": response_timeout,
        }
        await self._channel.subscribe(
            exchange_name=exchange_name,
            queue_name=queue_name,
            routing_key=routing_key,
            callback=callback,
            response_timeout=response_timeout,
        )

    async def add_callback(
        self,
        callback: Callable[..., Awaitable[Any]],
        connection_timeout: Optional[float] = None,
    ):
        try:
            if self.is_open and self._channel.is_open:
                return await callback()
            else:
                future: Future = Future(loop=self.ioloop)
                self.callbacks.append((callback, future))
                return await wait_for(future, connection_timeout)
        except TimeoutError:
            raise AutoReconnectException(
                "Timeout: failed to connect, order rejected..."
            )
