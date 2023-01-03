from .async_connection_factory import AsyncConnectionFactoryRabbitMQ, AsyncioConnection
from .async_channel import asyncChannel
from asyncio import AbstractEventLoop
from asyncio import sleep
from amqp_client_python.utils import Logger


class AsyncConnection:

    def __init__(self, ioloop: AbstractEventLoop, publisher_confirms=False) -> None:
        self.ioloop = ioloop
        self.publisher_confirms = publisher_confirms
        self.logger = Logger.error_logger
        self.connection_factory = AsyncConnectionFactoryRabbitMQ()
        self._connection: AsyncioConnection = None
        self._channel = None
        self._closing = False
        self._consuming = False
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
        if not self.is_open:
            self._connection = self.connection_factory.create_connection(
                uri=uri,
                on_connection_open=self.on_connection_open,
                on_connection_open_error=self.on_connection_open_error,
                on_connection_closed=self.on_connection_closed,
                custum_ioloop=self.ioloop,
            )
    
    async def close(self):
        if self.is_open:
            self._connection.close()
    
    def on_connection_open(self, _unused_connection):
        self.logger.info("connection openned", self._channel)
        self._channel = asyncChannel(Logger.error_logger)
        self._channel.publisher_confirms = self.publisher_confirms
        self._channel.open(self._connection)
    
    def on_connection_open_error(self, _unused_connection, err):
        self.logger.info(f"connection open error: {err}")
        self.reconnect()
    
    def on_connection_closed(self, _unused_connection, reason):
        """This method is invoked by pika when the connection to RabbitMQ is
        closed unexpectedly. Since it is unexpected, we will reconnect to
        RabbitMQ if it disconnects.
        :param pika.connection.Connection connection: The closed connection obj
        :param Exception reason: exception representing reason for loss of
            connection.
        """
        self.logger.info("connection closed")
        self._channel = None
        if self._closing:
            self._connection.ioloop.stop()
        else:
            self.logger.info(f"Connection closed, reconnect necessary: {reason}")
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
            if self.reconnect_delay>30:
                self.reconnect_delay=30
            self.open(self.url)
            self.ioloop.call_later(self.reconnect_delay, self.retry_connection)
            self.reconnect_delay+=1
        else:
            async def recorvery():
                for routing_key in self.backup["subscribe"]:
                    params=self.backup["subscribe"][routing_key]
                    await self.subscribe(params["queue_name"], params["exchange_name"], routing_key, params["callback"], params["auto_ack"])
                for routing_key in self.backup["rpc_subscribe"]:
                    params=self.backup["rpc_subscribe"][routing_key]
                    await self.rpc_subscribe(params["queue_name"], params["exchange_name"], routing_key, params["callback"], params["auto_ack"])
            self.ioloop.create_task(self.add_callback(recorvery))
            self.reconnect_delay = 1
            self.reconnecting = False

         
        

    @property
    def is_open(self):
        return self._connection and self._connection.is_open
    
    def stop(self):
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
            self.logger.info('Stopping')
            if self._consuming:
                self.stop_consuming()
                self._connection.ioloop.run_forever()
            else:
                self.ioloop.stop()
            self.logger.info('Stopped')


    def set_qos(self):
        """This method sets up the consumer prefetch to only be delivered
        one message at a time. The consumer must acknowledge this message
        before RabbitMQ will deliver another one. You should experiment
        with different prefetch values to achieve desired performance.
        """
        self._channel.basic_qos(
            prefetch_count=self._prefetch_count, callback=self.on_basic_qos_ok)

    def run(self):
        """Run the example consumer by connecting to RabbitMQ and then
        starting the IOLoop to block and allow the AsyncioConnection to operate.
        """
        self._connection = self.connect()
        self._connection.ioloop.run_forever()

    async def rpc_client(self, exchange_name: str, routing_key: str, body, content_type, timeout):
        return await self._channel.rpc_client(exchange_name, routing_key, body, self.ioloop, content_type, timeout)


    async def publish(self, exchange_name: str, routing_key: str, body, content_type):
        return await self._channel.publish(exchange_name, routing_key, body, content_type, loop=self.ioloop)
    
    async def rpc_subscribe(self, queue_name, exchange_name, routing_key, callback, auto_ack):
        self.backup["rpc_subscribe"][routing_key] = {
            "queue_name": queue_name, "exchange_name": exchange_name,
            "routing_key": routing_key, "callback": callback, "auto_ack": auto_ack
        }
        await self._channel.rpc_subscribe(queue_name=queue_name, exchange_name=exchange_name,
            routing_key=routing_key, callback=callback, auto_ack=auto_ack)
    
    async def subscribe(self, queue_name, exchange_name, routing_key, callback, auto_ack):
        self.backup["subscribe"][routing_key] = {
            "queue_name": queue_name, "exchange_name": exchange_name,
            "routing_key": routing_key, "callback": callback, "auto_ack": auto_ack
        }
        await self._channel.subscribe(queue_name=queue_name, exchange_name=exchange_name,
            routing_key=routing_key, callback=callback, auto_ack=auto_ack)
    
    async def add_callback(self, callback, retry=3, delay=2):
        while retry:
            retry-=1
            if self.is_open and self._channel.is_open:
                return await callback()
            else:
                await sleep(delay)