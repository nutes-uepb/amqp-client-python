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
        """
        Manages asynchronous connections to RabbitMQ with automatic reconnection capabilities.

        This class handles connection lifecycle, channel management, and provides methods for
        publishing messages, subscribing to queues, and implementing RPC patterns.

        Args:
            ioloop: The asyncio event loop to use for async operations
            publisher_confirms: Whether to enable publisher confirmations for this connection
            prefetch_count: Maximum number of unacknowledged messages to prefetch
            auto_ack: Whether to automatically acknowledge messages
            connection_type: Type of connection (PUBLISH, SUBSCRIBE, RPC_CLIENT, RPC_SERVER)
            signal: Signal object for event handling

        Returns:
            None: None

        Examples:
            >>> connection = AsyncConnection(
                    get_event_loop(),
                    publisher_confirms=True,
                    prefetch_count=10,
                    auto_ack=False,
                    connection_type=ConnectionType.PUBLISH
                )
            >>> connection.open("amqp://guest:guest@localhost:5672/%2F")
        """
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
        """
        Opens a connection to RabbitMQ using the provided URI.

        If the connection is not already open and not in the process of opening,
        this method will initiate a new connection.

        Args:
            uri: The AMQP URI to connect to (e.g., "amqp://guest:guest@localhost:5672/")

        Examples:
            >>> connection.open("amqp://guest:guest@localhost:5672/")
        """
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
        """
        Closes the connection to RabbitMQ gracefully.

        This method will only close the connection if it is currently open.

        Examples:
            >>> await connection.close()
        """
        if self.is_open:
            self._closing = True
            self._connection.close()

    def on_connection_open(self, _unused_connection):
        """
        Callback invoked when the connection to RabbitMQ is established.

        This method creates a channel and emits a connection event.

        Args:
            _unused_connection: The connection object (not used)
        """
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
        """
        Callback invoked when the connection to RabbitMQ is established.

        This method creates a channel and emits a connection event.

        Args:
            _unused_connection: The connection object (not used)
        """
        LOGGER.info(f"connection open error: {err}, will attempt a connection")
        self.openning = False
        self.reconnect()

    def on_connection_closed(self, _unused_connection, reason):
        """
        Callback invoked when the connection to RabbitMQ is closed unexpectedly.

        This method is invoked by pika when the connection to RabbitMQ is
        closed unexpectedly. Since it is unexpected, we will reconnect to
        RabbitMQ if it disconnects.

        Args:
            _unused_connection: The closed connection object
            reason: Exception representing reason for loss of connection
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
        """
        Initiates the reconnection process.

        Will be invoked if the connection can't be opened or is closed.
        Indicates that a reconnect is necessary.
        """
        if not self.reconnecting:
            self.reconnecting = True
            self.retry_connection()

    def retry_connection(self):
        """
        Attempts to reconnect to RabbitMQ with exponential backoff.

        If reconnection is successful, this method will recover previous subscriptions
        and RPC handlers.
        """
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
                        params["timeout"],
                    )
                for routing_key in self.backup["rpc_subscribe"]:
                    params = self.backup["rpc_subscribe"][routing_key]
                    await self.rpc_subscribe(
                        params["queue_name"],
                        params["exchange_name"],
                        routing_key,
                        params["callback"],
                        params["timeout"],
                    )

            self.ioloop.create_task(self.add_callback(recorvery))  # type: ignore
            self.reconnect_delay = 1
            self.reconnecting = False

    @property
    def is_open(self) -> Optional[bool]:
        """
        Checks if the connection is currently open.

        Returns:
            Optional[bool]: True if the connection is open, False otherwise, or None if no connection exists
        """
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
        response_timeout,
        delivery_mode,
        expiration,
        **kwargs,
    ):
        """
        Sends an RPC request and waits for a response.

        Args:
            exchange_name: The exchange to publish to
            routing_key: The routing key for the message
            body: The message body to send
            content_type: Content type of the message
            response_timeout: Timeout in seconds for waiting for a response
            delivery_mode: Delivery mode (persistent or transient)
            expiration: Maximum lifetime of the message in the queue
            **kwargs: Additional message properties

        Returns:
            Any: The response from the RPC server

        Raises:
            PublishTimeoutException: If publisher confirmation times out
            NackException: If the message is rejected by the broker
            ResponseTimeoutException: If no response is received within the response_timeout

        Examples:
            >>> response = await connection.rpc_client(
                    "rpc_exchange",
                    "user.find",
                    {"id": 123},
                    "application/json",
                    5.0,
                    DeliveryMode.Transient,
                    "60000"
                )
        """
        return await self._channel.rpc_client(
            exchange_name,
            routing_key,
            body,
            content_type,
            response_timeout,
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
        """
        Publishes a message to RabbitMQ.

        Args:
            exchange_name: The exchange to publish to
            routing_key: The routing key for the message
            body: The message body to send
            content_type: Content type of the message
            timeout: Timeout in seconds for publisher confirmation
            delivery_mode: Delivery mode (persistent or transient)
            expiration: Maximum lifetime of the message in the queue
            **kwargs: Additional message properties

        Returns:
            Optional[bool]: True if publisher confirms enabled and message was confirmed,
                           None if publisher confirms disabled

        Raises:
            PublishTimeoutException: If publisher confirmation times out
            NackException: If the message is rejected by the broker

        Examples:
            >>> result = await connection.publish(
                    "notifications",
                    "email.send",
                    {"to": "user@example.com", "subject": "Hello"},
                    "application/json",
                    5.0,
                    DeliveryMode.Persistent,
                    "60000"
                )
        """
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
        self, queue_name, exchange_name, routing_key, callback, timeout
    ):
        """
        Registers an RPC handler for a specific routing key.

        Args:
            queue_name: The queue to consume from
            exchange_name: The exchange to bind to
            routing_key: The routing key to subscribe to
            callback: The function to call when a message is received
            timeout: Timeout in seconds for processing the received message

        Examples:
            >>> async def handle_rpc(body):
                    result = process_request(body)
                    return json.dumps(result).encode()
            >>> await connection.rpc_subscribe(
                    "rpc_queue",
                    "rpc_exchange",
                    "user.find",
                    handle_rpc,
                    10.0
                )
        """
        self.backup["rpc_subscribe"][routing_key] = {
            "queue_name": queue_name,
            "exchange_name": exchange_name,
            "callback": callback,
            "timeout": timeout,
        }
        await self._channel.rpc_subscribe(
            queue_name=queue_name,
            exchange_name=exchange_name,
            routing_key=routing_key,
            callback=callback,
            timeout=timeout,
        )

    async def subscribe(
        self,
        queue_name: str,
        exchange_name: str,
        routing_key: str,
        callback: Callable[[Any], Awaitable[None]],
        timeout: Optional[float],
    ):
        """
        Subscribes to messages with a specific routing key.

        Args:
            queue_name: The queue to consume from
            exchange_name: The exchange to bind to
            routing_key: The routing key to subscribe to
            callback: The function to call when a message is received
            timeout: Timeout in seconds for processing the received message

        Examples:
            >>> async def handle_message(body):
                    print(f"Received: {body}")
            >>> await connection.subscribe(
                    "notifications_queue",
                    "notifications",
                    "email.send",
                    handle_message,
                    5.0
                )
        """
        self.backup["subscribe"][routing_key] = {
            "queue_name": queue_name,
            "exchange_name": exchange_name,
            "callback": callback,
            "timeout": timeout,
        }
        await self._channel.subscribe(
            exchange_name=exchange_name,
            queue_name=queue_name,
            routing_key=routing_key,
            callback=callback,
            timeout=timeout,
        )

    async def add_callback(
        self,
        callback: Callable[..., Awaitable[Any]],
        connection_timeout: Optional[float] = None,
    ):
        """
        Executes a callback when the connection is ready or queues it for later execution.

        If the connection and channel are open, executes the callback immediately.
        Otherwise, queues the callback to be executed when the connection is established.

        Args:
            callback: The async function to call
            connection_timeout: Maximum time to wait for the connection to be established

        Returns:
            Any: The result of the callback

        Raises:
            AutoReconnectException: When the connection cannot be established within the timeout

        Examples:
            >>> async def my_operation():
                    return await connection.publish(...)
            >>> result = await connection.add_callback(my_operation, 10.0)
        """
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
