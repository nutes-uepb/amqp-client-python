from typing import Dict
from .channel_factory_rabbitmq import ChannelFactoryRabbitMQ
from pika.channel import Channel
from pika import BasicProperties
from functools import partial
from uuid import uuid4
from json import loads, dumps
from concurrent.futures import Future, TimeoutError
import logging


LOGGER = logging.getLogger(__name__)


class ChannelRabbitMQ:
    def __init__(self, auto_ack=True) -> None:
        self.channel_factory = ChannelFactoryRabbitMQ()
        self.rpc_consumer = False
        self.rpc_publisher = False
        self._channel = None
        self._callback_queue = None
        self.auto_ack = auto_ack
        self.consumers = {}
        self.futures: Dict[str, Future] = {}
        self._stopping = False

    def open(self, connection, callback=None):
        self._channel = None
        self.consumers = {}
        self._callback_queue = f"amqp.{uuid4()}"
        self.consumer_tag = None
        self._connection = connection
        self.start = self._connection.start
        self.stop = self._connection.pause
        self.reconnect = self._connection.reset
        self._stopping = self._connection._stopping
        callback = partial(self.on_channel_open, callback=callback)
        self.channel_factory.create_channel(connection._connection, callback)

    def on_channel_open(self, channel, callback=None):
        """This method is invoked by pika when the channel has been opened.
        The channel object is passed in so we can make use of it.
        Since the channel is now open, we'll declare the exchange to use.
        :param pika.channel.Channel channel: The channel object
        """
        LOGGER.debug("Channel opened")
        self._channel: Channel = channel
        self.add_on_channel_close_callback()
        if callback:
            callback("")

    def declare_exchange(self, exchange, exchange_type, durable=True, callback=None):
        """Setup the exchange on RabbitMQ by invoking the Exchange.Declare RPC
        command. When it is complete, the on_exchange_declareok method will
        be invoked by pika.
        :param str|unicode exchange_name: The name of the exchange to declare
        """
        LOGGER.debug("Declaring exchange %s", exchange)
        # Note: using functools.partial is not required, it is demonstrating
        # how arbitrary data can be passed to the callback when it is called
        cb = partial(
            callback or self.on_exchange_declareok, userdata=exchange, callback=callback
        )
        self._channel.exchange_declare(
            exchange=exchange, durable=durable, exchange_type=exchange_type, callback=cb
        )

    def on_exchange_declareok(self, _unused_frame, userdata, callback=None):
        """Invoked by pika when RabbitMQ has finished the Exchange.Declare RPC
        command.
        :param pika.Frame.Method unused_frame: Exchange.DeclareOk response frame
        :param str|unicode userdata: Extra user data (exchange name)
        """
        LOGGER.debug("Exchange declared: %s", userdata)
        if callback:
            callback()

    def queue_declare(
        self, queue_name: str, durable=False, auto_delete=False, callback=None
    ):
        """Setup the queue on RabbitMQ by invoking the Queue.Declare RPC
        command. When it is complete, the on_queue_declareok method will
        be invoked by pika.
        :param str|unicode queue_name: The name of the queue to declare.
        """
        LOGGER.debug("Declaring queue %s", queue_name)
        self._channel.queue_declare(
            queue=queue_name,
            durable=durable,
            auto_delete=auto_delete,
            callback=callback,
        )

    def add_on_return_callback(self, callback):
        LOGGER.debug("Adding channel return callback")
        self._channel.add_on_return_callback(callback)

    def add_on_channel_close_callback(self):
        """This method tells pika to call the on_channel_closed method if
        RabbitMQ unexpectedly closes the channel.
        """
        LOGGER.debug("Adding channel close callback")
        self._channel.add_on_close_callback(self.on_channel_closed)

    def on_channel_closed(self, channel, reason):
        """Invoked by pika when RabbitMQ unexpectedly closes the channel.
        Channels are usually closed if you attempt to do something that
        violates the protocol, such as re-declare an exchange or queue with
        different parameters. In this case, we'll close the connection
        to shutdown the object.
        :param pika.channel.Channel channel: The closed channel
        :param Exception reason: why the channel was closed
        """
        LOGGER.warning("Channel %i was closed: %s", channel, reason)
        if isinstance(reason, tuple) and reason[0] == 406:
            self.open(self._connection, False)
        self._channel = None
        self._channel_rpc = None
        self.rpc_publisher = False
        self.rpc_consumer = False
        if not self._stopping:
            if not self._connection.is_open():
                if self._connection.ioloop_is_open:
                    self._connection.ioloop.call_later(5, self.reconnect)
                # self._connection._connection.ioloop.call_later(5, self._connection.pause)
            else:
                self._connection.close()

    def is_open(self) -> bool:
        return self._channel and self._channel.is_open

    def close_channel(self):
        """Invoke this command to close the channel with RabbitMQ by sending
        the Channel.Close RPC command.
        """
        if self._channel is not None:
            LOGGER.debug("Closing the channel")
            self._channel.close()

    def start_rpc_consumer(self):
        self.rpc_consumer = True
        LOGGER.info("Starting rpc consumer")

        def on_open(channel: Channel):
            LOGGER.info("Channel opened - consumer")
            self._channel_rpc.add_on_close_callback(self.on_channel_closed)

            def on_declare(channel):
                self.consumer_tag = self._channel_rpc.basic_consume(
                    queue=self._callback_queue,
                    on_message_callback=self.__on_response,
                    auto_ack=True,
                    consumer_tag=None,
                )

            LOGGER.info(f"Declaring queue {self._callback_queue}")
            self._channel_rpc.queue_declare(
                queue=self._callback_queue,
                durable=False,
                auto_delete=True,
                callback=on_declare,
            )

        self._channel_rpc: Channel = self.channel_factory.create_channel(
            self._connection._connection, on_channel_open=on_open
        )

    def start_rpc_publisher(self):
        self.rpc_publisher = True

        def on_open(channel: Channel):
            self._channel_rpc.add_on_close_callback(self.on_channel_closed)

        self._channel_rpc: Channel = self.channel_factory.create_channel(
            self._connection._connection, on_channel_open=on_open
        )

    def rpc_client(self, exchange, routing_key, message, content_type, future, timeout):
        message = dumps({"handle": message})
        last_id = str(uuid4())
        self.futures[last_id] = future
        self.response = None
        self._channel.basic_publish(
            exchange,
            routing_key,
            message,
            properties=BasicProperties(
                reply_to=self._callback_queue,
                correlation_id=last_id,
                content_type=content_type,
            ),
        )
        if not self.rpc_consumer:
            self.start_rpc_consumer()

        def prevent_infinite_loop(last_id):
            if last_id in self.futures:
                self.futures[last_id].set_exception(TimeoutError("request timeout!!!"))
                del self.futures[last_id]

        func = partial(prevent_infinite_loop, str(last_id))
        self._connection._connection.ioloop.call_later(timeout, func)

    def publish(self, exchange: str, routing_key: str, message):
        message = dumps({"handle": message})
        self._channel.basic_publish(
            exchange,
            routing_key,
            message,
            properties=BasicProperties(content_type="application/json"),
        )

    def serve_resource(self, ch: Channel, method, props, body: bytes):
        if method.routing_key in self.consumers:
            response = None
            type_message = None
            try:
                body = loads(body)
                response = self.consumers[method.routing_key]["handle"](*body["handle"])
                type_message = "normal"
                if props.reply_to:
                    self._channel_rpc.basic_publish(
                        "",
                        props.reply_to,
                        response,
                        properties=BasicProperties(
                            correlation_id=props.correlation_id,
                            content_type=self.consumers[method.routing_key][
                                "content_type"
                            ],
                            type=type_message,
                        ),
                    )
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except BaseException as err:
                type_message = "error"
                response = str(err)
                if props.reply_to:
                    self._channel_rpc.basic_publish(
                        "",
                        props.reply_to,
                        response,
                        properties=BasicProperties(
                            correlation_id=props.correlation_id,
                            content_type="plain/text",
                            type=type_message,
                        ),
                    )
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    def addResource(self, name: str, resource, content_type="application/json") -> bool:
        if not hasattr(self.consumers, name):
            self.consumers[name] = {"handle": resource, "content_type": content_type}
            return True
        return False

    def rpc_subscribe(
        self,
        queue_name: str,
        exchange: str,
        routing_key: str,
        callback=None,
        auto_ack=True,
        consumer_tag=None,
    ):
        if not self.rpc_publisher:
            self.start_rpc_publisher()
        if self.is_open():
            if not self.consumer_tag:
                self.consumer_tag = self._channel.basic_consume(
                    queue=queue_name,
                    on_message_callback=self.serve_resource,
                    auto_ack=auto_ack,
                    consumer_tag=consumer_tag,
                )
            self.addResource(routing_key, callback)
            self._channel.queue_bind(
                exchange=exchange, queue=queue_name, routing_key=routing_key
            )

    def subscribe(
        self,
        queue_name: str,
        exchange: str,
        routing_key: str,
        callback=None,
        auto_ack=True,
    ):
        if self.is_open():
            if not self.consumer_tag:
                self.consumer_tag = self._channel.basic_consume(
                    queue=queue_name,
                    on_message_callback=self.serve_subscribe,
                    auto_ack=auto_ack,
                    consumer_tag=self.consumer_tag,
                )
            self.addResource(routing_key, callback)
            self._channel.queue_bind(
                exchange=exchange, queue=queue_name, routing_key=routing_key
            )

    def unsubscribe(self, consumer_tag: str):
        self._channel.basic_cancel(consumer_tag)

    def serve_subscribe(self, ch: Channel, method, props, body):
        if method.routing_key in self.consumers:
            try:
                body = loads(body)
                self.consumers[method.routing_key]["handle"](*body["handle"])
            except BaseException as err:
                LOGGER.error(err)

    def __on_response(self, ch: Channel, method, props, body, future=None):
        if props.correlation_id in self.futures:
            future = self.futures[props.correlation_id]
            del self.futures[props.correlation_id]
            if props.type == "error":
                future.set_exception(
                    Exception(f"Internal Server Error: {body.decode('utf-8')}")
                )
            future.set_result(body)

    def close(self):
        if self.is_open():
            self._channel.close()
