from .connection_factory_rabbitmq import ConnectionFactoryRabbitMQ
from .channel_rabbitmq import ChannelRabbitMQ
from amqp_client_python.exceptions import EventBusException
from pika import SelectConnection, URLParameters
from .ioloop_factory import IOLoopFactory
import logging


LOGGER = logging.getLogger(__name__)


class ConnectionRabbitMQ:
    _connection: SelectConnection
    _channel: ChannelRabbitMQ

    def __init__(self) -> None:
        self._connectionFactory = ConnectionFactoryRabbitMQ()
        self._connection = None
        self.ioloop_factory = IOLoopFactory
        self.ioloop_factory.add_reconnection(self.reconnect)
        self._stopping = False
        self._channel = ChannelRabbitMQ()
        self._uri = None
        self.backup = {
            "exchange": {},
            "queue": {},
            "subscribe": {},
            "rpc_subscribe": {},
        }

    @property
    def ioloop(self):
        return IOLoopFactory.get_ioloop()

    @property
    def ioloop_is_open(self):
        return IOLoopFactory.running

    def open(self, uri: URLParameters, ioloop=None):
        if not self._connection or self._connection.is_closed:
            self._uri = uri
            self._connection = self._connectionFactory.create_connection(
                uri,
                self.on_connection_open,
                self.on_connection_open_error,
                self.on_connection_closed,
                custum_ioloop=ioloop,
            )

    def reset(self):
        self.ioloop.call_later(2, self.ioloop_factory.reset)

    def reconnect(self):
        LOGGER.debug("reconnect %s", self.ioloop_is_open)
        if not self.is_open():
            self._connection = self._connectionFactory.create_connection(
                self._uri,
                self.on_connection_open,
                self.on_connection_open_error,
                self.on_connection_closed,
                custum_ioloop=self.ioloop,
            )
            self.add_callback(self.restore)

    def restore(self):
        for exchange_name in self.backup["exchange"]:
            params = self.backup["exchange"][exchange_name]
            self.declare_exchange(
                exchange_name, params["type"], params["durable"], params["callback"]
            )
        for queue_name in self.backup["queue"]:
            params = self.backup["queue"][queue_name]
            self.declare_queue(
                queue_name, params["durable"], params["auto_delete"], params["callback"]
            )
        for routing_key in self.backup["subscribe"]:
            params = self.backup["subscribe"][routing_key]
            self.subscribe(
                params["queue"],
                params["exchange"],
                routing_key,
                params["callback"],
                params["auto_ack"],
            )
        for routing_key in self.backup["rpc_subscribe"]:
            params = self.backup["rpc_subscribe"][routing_key]
            self.rpc_subscribe(
                params["queue"], params["exchange"], routing_key, params["callback"]
            )

    def start(self, force=False):
        self._stopping = False
        if not self.ioloop_is_open or force:
            self.ioloop_factory.start()

    def pause(self):
        if self.ioloop_is_open:
            self._connection.ioloop.stop()

    def stop(self):
        self._stopping = True
        if self.ioloop_is_open:
            self._connection.ioloop.stop()

    def declare_exchange(self, exchange, exchange_type, durable=True, callback=None):
        """Setup the exchange on RabbitMQ by invoking the Exchange.Declare RPC
        command. When it is complete, the on_exchange_declareok method will
        be invoked by pika.
        :param str|unicode exchange_name: The name of the exchange to declare
        """
        # Note: using functools.partial is not required, it is demonstrating
        # how arbitrary data can be passed to the callback when it is called
        self.backup["exchange"][exchange] = {
            "type": exchange_type,
            "durable": durable,
            "callback": callback,
        }
        if self.is_open():
            self._channel.declare_exchange(
                exchange=exchange,
                durable=durable,
                exchange_type=exchange_type,
                callback=callback,
            )

    def declare_queue(
        self, queue_name, durable=False, auto_delete=False, callback=lambda x: x
    ):
        self.backup["queue"][queue_name] = {
            "durable": durable,
            "auto_delete": auto_delete,
            "callback": callback,
        }
        self._channel.queue_declare(
            queue_name, durable=durable, auto_delete=auto_delete, callback=callback
        )

    def register_channel_return_callback(self):
        self._channel.register_return_callback(self.pause)

    def on_connection_open(self, _unused_connection):
        """This method is called by pika once the connection to RabbitMQ has
        been established. It passes the handle to the connection object in
        case we need it, but in this case, we'll just mark it unused.
        :param pika.SelectConnection _unused_connection: The connection
        """
        LOGGER.debug("Connection opened")
        if not self.channel_is_open():
            self.channel_open()
        # self.pause()

    def on_connection_open_error(self, _unused_connection, err):
        """This method is called by pika if the connection to RabbitMQ
        can't be established.
        :param pika.SelectConnection _unused_connection: The connection
        :param Exception err: The error
        """
        LOGGER.error("Connection open failed, reopening in 5 seconds: %s", err)
        if self.ioloop_factory.running:
            self.reset()
        # else:
        #    self._connection.ioloop.call_later(5, self.pause)

    def on_connection_closed(self, _unused_connection, reason):
        """This method is invoked by pika when the connection to RabbitMQ is
        closed unexpectedly. Since it is unexpected, we will reconnect to
        RabbitMQ if it disconnects.
        :param pika.connection.Connection connection: The closed connection obj
        :param Exception reason: exception representing reason for loss of
            connection.
        """
        if self._connection.is_closed:
            LOGGER.warning("Connection closed: %s", reason)
            self.reset()

    def add_callback(self, callback, event: str = "channel_open"):
        if event == "channel_open":

            def channel_openned():
                if self.channel_is_open():
                    callback()
                else:
                    self.ioloop.call_later(1, channel_openned)

            self.ioloop.add_callback_threadsafe(channel_openned)

    def channel_open(self, callback=lambda x: x):
        if not self.is_open():
            raise EventBusException("No connection open!")
        if not self.channel_is_open():
            self._channel.open(self, callback)

    def is_open(self) -> bool:
        return self._connection and self._connection.is_open

    def channel_is_open(self):
        return self._channel and self._channel.is_open()

    def publish(self, exchange_name: str, routing_key: str, message: str):
        if not self.is_open():
            raise EventBusException("No connection open!")
        if not self._channel.is_open():
            raise EventBusException("No channel open!")
        return self._channel.publish(exchange_name, routing_key, message)

    def subscribe(
        self,
        queue_name: str,
        exchange_name: str,
        routing_key: str,
        callback,
        auto_ack=True,
    ):
        if not self.is_open():
            raise EventBusException("No connection open!")
        if not self._channel.is_open():
            raise EventBusException("No channel open!")
        self.backup["subscribe"][routing_key] = {
            "exchange": exchange_name,
            "queue": queue_name,
            "callback": callback,
            "auto_ack": auto_ack,
        }
        return self._channel.subscribe(
            queue_name, exchange_name, routing_key, callback=callback, auto_ack=auto_ack
        )

    def rpc_client(
        self,
        exchange_name: str,
        routing_key: str,
        message: str,
        content_type,
        future,
        timeout,
    ):
        if not self.is_open():
            self.reset()
        if not self._channel.is_open():
            self.channel_open()
        return self._channel.rpc_client(
            exchange_name,
            routing_key,
            message,
            content_type=content_type,
            future=future,
            timeout=timeout,
        )

    def rpc_subscribe(
        self, queue_name: str, exchange_name: str, routing_key: str, callback
    ):
        if not self.is_open():
            raise EventBusException("No connection open!")
        if not self._channel.is_open():
            raise EventBusException("No channel open!")
        self.backup["rpc_subscribe"][routing_key] = {
            "exchange": exchange_name,
            "queue": queue_name,
            "callback": callback,
        }
        return self._channel.rpc_subscribe(
            queue_name, exchange_name, routing_key, callback, auto_ack=False
        )

    def close(self):
        self._channel.close()
        if self.is_open():
            self._connection.close()
