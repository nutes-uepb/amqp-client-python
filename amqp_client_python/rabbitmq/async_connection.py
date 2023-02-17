from .async_connection_factory import AsyncConnectionFactoryRabbitMQ, AsyncioConnection
from .async_channel import AsyncChannel
from ..exceptions import AutoReconnectException
from asyncio import AbstractEventLoop
from asyncio import sleep, get_event_loop
import logging


LOGGER = logging.getLogger(__name__)


class AsyncConnection:
    def __init__(
        self,
        ioloop: AbstractEventLoop,
        publisher_confirms=False,
        prefetch_count=0,
        auto_ack=True,
    ) -> None:
        self.ioloop = ioloop
        self.publisher_confirms = publisher_confirms
        self.connection_factory = AsyncConnectionFactoryRabbitMQ()
        self._connection: AsyncioConnection = None
        self._prefetch_count = prefetch_count
        self._auto_ack = auto_ack
        self._channel = AsyncChannel(self._prefetch_count, self._auto_ack)
        self._closing = False
        self._consuming = False
        self.openning = False
        self.reconnecting = False
        self.reconnect_delay = 1
        self.backup = {
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
        self.openning = False
        self._channel = AsyncChannel(self._prefetch_count, self._auto_ack)
        self._channel.publisher_confirms = self.publisher_confirms
        self._channel.open(self._connection)

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

        self.should_reconnect = True
        if not self.reconnecting:
            self.reconnecting = True
            self.retry_connection()

    def retry_connection(self):
        if not self.is_open:
            if self.reconnect_delay > 30:
                self.reconnect_delay = 30
            self.open(self.url)
            self.ioloop.call_later(self.reconnect_delay, self.retry_connection)
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
                    )
                for routing_key in self.backup["rpc_subscribe"]:
                    params = self.backup["rpc_subscribe"][routing_key]
                    await self.rpc_subscribe(
                        params["queue_name"],
                        params["exchange_name"],
                        routing_key,
                        params["callback"],
                    )

            self.ioloop.create_task(self.add_callback(recorvery))
            self.reconnect_delay = 1
            self.reconnecting = False

    @property
    def is_open(self) -> bool:
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
            LOGGER.warn("Stopping intentionally")
            if self._consuming:
                self.stop_consuming()
                self._connection.ioloop.run_forever()
            else:
                self.ioloop.stop()
            LOGGER.warn("Stopped")

    def set_qos(self) -> None:
        """This method sets up the consumer prefetch to only be delivered
        one message at a time. The consumer must acknowledge this message
        before RabbitMQ will deliver another one. You should experiment
        with different prefetch values to achieve desired performance.
        """
        self._channel.basic_qos(
            prefetch_count=self._prefetch_count, callback=self.on_basic_qos_ok
        )

    def run(self) -> None:
        """Run the example consumer by connecting to RabbitMQ and then
        starting the IOLoop to block and allow the AsyncioConnection to operate.
        """
        self._connection = self.connect()
        self._connection.ioloop.run_forever()

    async def rpc_client(
        self,
        exchange_name: str,
        routing_key: str,
        body,
        content_type,
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
        body,
        content_type,
        timeout,
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

    async def add_callback(self, callback, retry=4, delay=1):
        while retry > 0:
            retry -= 1
            if self.is_open and self._channel and self._channel.is_open:
                return await callback()
            else:
                delay *= 2
                await sleep(delay)
        raise AutoReconnectException("Timeout: failed to connect, order rejected...")
