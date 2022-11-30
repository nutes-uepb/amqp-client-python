from .connection_factory_rabbitmq import ConnectionFactoryRabbitMQ
from .channel_rabbitmq import ChannelRabbitMQ
from amqp_client_python.exceptions import EventBusException
from .channel_rabbitmq import ChannelRabbitMQ
from pika import SelectConnection, URLParameters
from amqp_client_python.utils import Logger


class ConnectionRabbitMQ:
    _connection:SelectConnection
    _channel:ChannelRabbitMQ
    _ioloop_is_open=False

    def __init__(self) -> None:
        self._connectionFactory = ConnectionFactoryRabbitMQ()
        self._connection = None
        self._stopping = False
        self._channel = ChannelRabbitMQ(Logger.error_logger)
        self._uri = None
        self.logger = Logger.error_logger
        self.backup = {
            "exchange": {},
            "queue": {},
            "subscribe": {},
        }

    def open(self, uri: URLParameters, ioloop_active = False):
        if not self._connection or self._connection.is_closed:
            self._uri = uri
            self._connection = self._connectionFactory.create_connection(uri, self.on_connection_open, self.on_connection_open_error, self.on_connection_closed)
            if not self.is_open() and not ioloop_active:
                self.start()
            

    def reconnect(self):
        self.logger.debug('reconnect %s',self._ioloop_is_open)
        self._stopping=False
        self._ioloop_is_open=False
        def connection_open(unused_connection):
            self.logger.debug("connection reopened  %s",unused_connection)
            self.stop()
        self._connection=self._connectionFactory.create_connection(self._uri, connection_open, self.on_connection_open_error, self.on_connection_closed)
        self.start()
        self._channel.open(self, self._ioloop_is_open)
        self.restore()
    
    def restore(self):
        for exchange_name in self.backup["exchange"]:
            params = self.backup["exchange"][exchange_name]
            self.declare_exchange(exchange_name, params["type"], params["durable"], params["callback"])
        for queue_name in self.backup["queue"]:
            params = self.backup["queue"][queue_name]
            self.declare_queue(queue_name, params["durable"], params["auto_delete"], params["callback"])
        for routing_key in self.backup["subscribe"]:
            params = self.backup["subscribe"][routing_key]
            self.subscribe(params["queue"], params["exchange"], routing_key, params["callback"], params["auto_ack"])
        

    def start(self, force = False):
        self._stopping=False
        if not self._ioloop_is_open or force:
            self._ioloop_is_open=True
            self._connection.ioloop.start()
    
    def pause(self):
        if self._ioloop_is_open:
            self._ioloop_is_open=False
            self._connection.ioloop.stop()

    def stop(self):
        self._stopping=True
        if self._ioloop_is_open:
            self._ioloop_is_open=False
            self._connection.ioloop.stop()

    def declare_exchange(self, exchange, exchange_type, durable=True, callback=None):
        """Setup the exchange on RabbitMQ by invoking the Exchange.Declare RPC
        command. When it is complete, the on_exchange_declareok method will
        be invoked by pika.
        :param str|unicode exchange_name: The name of the exchange to declare
        """
        # Note: using functools.partial is not required, it is demonstrating
        # how arbitrary data can be passed to the callback when it is called
        self.backup["exchange"][exchange] = { "type": exchange_type, "durable": durable, "callback": callback }
        if self.is_open():
            self._channel.declare_exchange(
                exchange=exchange, durable=durable,
                exchange_type=exchange_type,
                callback=callback)
            self.start()

    def declare_queue(self, queue_name, durable=False, auto_delete=False, callback=lambda x:x):
        self.backup["queue"][queue_name] = { "durable": durable, "auto_delete": auto_delete, "callback": callback }
        self._channel.queue_declare(queue_name, durable=durable, auto_delete=auto_delete, callback=callback)

    def register_channel_return_callback(self):
        self._channel.register_return_callback(self.pause)

    def on_connection_open(self, _unused_connection):
        """This method is called by pika once the connection to RabbitMQ has
        been established. It passes the handle to the connection object in
        case we need it, but in this case, we'll just mark it unused.
        :param pika.SelectConnection _unused_connection: The connection
        """
        self.logger.debug('Connection opened')
        self.pause()
    
    def on_connection_open_error(self, _unused_connection, err):
        """This method is called by pika if the connection to RabbitMQ
        can't be established.
        :param pika.SelectConnection _unused_connection: The connection
        :param Exception err: The error
        """
        self.logger.error('Connection open failed, reopening in 5 seconds: %s', err)
        self._connection.ioloop.call_later(5, self.pause)

    def on_connection_closed(self, _unused_connection, reason):
        """This method is invoked by pika when the connection to RabbitMQ is
        closed unexpectedly. Since it is unexpected, we will reconnect to
        RabbitMQ if it disconnects.
        :param pika.connection.Connection connection: The closed connection obj
        :param Exception reason: exception representing reason for loss of
            connection.
        """
        if self._stopping:
            self.logger.warning('Connection closed %s', reason)
            self.stop()
        else:
            if self._connection.is_closed:
                self.logger.warning('Connection closed: %s', reason)
                self.stop()
                #self._connection.ioloop.call_later(5, self.pause)
            else:
                self.logger.warning('Connection closed, reopening in 5 seconds: %s', reason)
                self._connection.ioloop.call_later(5, self.pause)
        
    def channel_open(self, ioloop_active = False):
        if not self.is_open(): return EventBusException('No connection open!')
        if self.channel_is_open(): return EventBusException('channel already open!')
        self._channel.open(self, ioloop_active)

    def is_open(self)->bool:
        return self._connection and self._connection.is_open
    
    def channel_is_open(self):
        return self._channel and self._channel.is_open()
    
    def publish(self, exchange_name: str, routing_key: str, message:str):
        if not self.is_open(): raise EventBusException('No connection open!')
        if not self._channel.is_open(): raise EventBusException("No channel open!")
        return self._channel.publish(exchange_name, routing_key, message)
    
    def subscribe(self, queue_name: str, exchange_name: str, routing_key: str, callback, auto_ack=True):
        if not self.is_open(): raise EventBusException('No connection open!')
        if not self._channel.is_open(): raise EventBusException("No channel open!")
        self.backup["subscribe"][routing_key] = { "exchange": exchange_name, "queue": queue_name, "callback": callback, "auto_ack": auto_ack }
        return self._channel.subscribe(queue_name, exchange_name, routing_key, callback=callback, auto_ack=auto_ack)

    def rpc_client(self, exchange_name: str, routing_key: str, message:str):
        if not self.is_open(): self.reconnect()
        if not self._channel.is_open(): self.channel_open()
        return self._channel.rpc_client(exchange_name, routing_key, message, self.start)
    
    def rpc_subscribe(self, queue: str, exchange_name: str, routing_key: str, callback):
        if not self.is_open(): raise EventBusException('No connection open!')
        if not self._channel.is_open(): raise EventBusException("No channel open!")
        return self._channel.rpc_subscribe(queue, exchange_name, routing_key, callback, auto_ack=False)

    def close(self):
        self._channel.close()
        if self.is_open():
            self._connection.close()
