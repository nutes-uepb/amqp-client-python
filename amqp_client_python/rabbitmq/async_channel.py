from typing import MutableMapping, Mapping, Optional, Union
from .async_channel_factory import AsyncChannelFactoryRabbitMQ
from amqp_client_python.exceptions import (
    NackException,
    RpcProviderException,
    PublishTimeoutException,
    ResponseTimeoutException,
    EventBusException,
)
from pika.adapters.asyncio_connection import AsyncioConnection
from pika.channel import Channel
from pika import BasicProperties, DeliveryMode
from asyncio import AbstractEventLoop, Future, wait, wait_for, FIRST_COMPLETED
from functools import partial
from json import dumps, loads
from uuid import uuid4
import logging


LOGGER = logging.getLogger(__name__)


class AsyncChannel:
    def __init__(
        self,
        prefetch_count=0,
        auto_ack=True,
        channel_factory=AsyncChannelFactoryRabbitMQ(),
    ) -> None:
        self.ioloop: AbstractEventLoop = None
        self.channel_factory = channel_factory
        self._channel: Channel = None
        self._connection: AsyncioConnection = None
        self._callback_queue = f"amqp.{uuid4()}"
        self.futures: MutableMapping[str, Mapping[str, Future]] = {}
        self.rpc_consumer = False
        self.rpc_consumer_started = False
        self.rpc_consumer_starting = False
        self.rpc_publisher_started = False
        self.rpc_publisher_starting = False
        self.consumer_tag = None
        self._prefetch_count = prefetch_count
        self.auto_ack = auto_ack
        self.subscribes = {}
        self.consumers = {}
        self.publisher_confirms = False
        self._message_number = 0
        self._deliveries = {}
        self.response_timeout = 60

    @property
    def is_open(self):
        return self._channel and self._channel.is_open

    def open(self, connection: AsyncioConnection):
        if not self.is_open:
            self._connection = connection
            self.ioloop: AbstractEventLoop = connection.ioloop
            self._channel: Channel = self.channel_factory.create_channel(
                connection, on_channel_open=self.on_channel_open
            )

    def on_channel_open(self, channel: Channel):
        """This method is invoked by pika when the channel has been opened.
        The channel object is passed in so we can make use of it.
        Since the channel is now open, we"ll declare the exchange to use.
        :param pika.channel.Channel channel: The channel object
        """
        LOGGER.info("Channel opened")
        self._channel = channel
        self.add_on_channel_close_callback()
        self.publisher_confirms and self.add_publish_confirms()
        self._prefetch_count and self.set_qos(self._prefetch_count)

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
        different parameters. In this case, we"ll close the connection
        to shutdown the object.
        :param pika.channel.Channel: The closed channel
        :param Exception reason: why the channel was closed
        """
        LOGGER.info(f"Channel {channel} was closed: {reason}")
        self._consuming = False
        if self._connection.is_closing or self._connection.is_closed:
            LOGGER.info("Connection is closing or already closed")
        else:
            LOGGER.info("Closing connection")
            self._connection.close()

    def add_publish_confirms(self):
        self._acked = 0
        self._nacked = 0
        self._deliveries: MutableMapping[int, Future] = {}
        self._message_number = 0
        self._channel.confirm_delivery(self.on_delivery_confirmation)
        LOGGER.info("Adding Publish Confirmation")

    def on_delivery_confirmation(self, method_frame):
        confirmation_type = method_frame.method.NAME.split(".")[1].lower()
        delivery_tag = method_frame.method.delivery_tag
        if confirmation_type == "ack":
            self._acked += 1
            if delivery_tag in self._deliveries:
                future = self._deliveries[delivery_tag]
                not future.done() and future.set_result(True)
        elif confirmation_type == "nack":
            self._nacked += 1
            if delivery_tag in self._deliveries:
                future = self._deliveries[delivery_tag]
                not future.done() and future.set_exception(
                    NackException(
                        f"Publish confirmation: nack of {delivery_tag} publish"
                    )
                )

    def setup_exchange(self, exchange_name, exchange_type, durable=True):
        """Setup the exchange on RabbitMQ by invoking the Exchange.Declare RPC
        command. When it is complete, the on_exchange_declareok method will
        be invoked by pika.
        :param str|unicode exchange_name: The name of the exchange to declare
        """
        LOGGER.info(f"Declaring exchange: {exchange_name}")
        # Note: using functools.partial is not required, it is demonstrating
        # how arbitrary data can be passed to the callback when it is called
        cb = partial(self.on_exchange_declareok, userdata=exchange_name)
        self._channel.exchange_declare(
            exchange=exchange_name,
            exchange_type=exchange_type,
            durable=durable,
            callback=cb,
        )

    def on_exchange_declareok(self, _unused_frame, userdata):
        """Invoked by pika when RabbitMQ has finished the Exchange.Declare RPC
        command.
        :param pika.Frame.Method unused_frame: Exchange.DeclareOk response frame
        :param str|unicode userdata: Extra user data (exchange name)
        """
        LOGGER.info(f"Exchange declared: {userdata}")

    def queue_declare(
        self, queue_name: str, durable=False, auto_delete=False, callback=None
    ):
        self.setup_queue(
            queue_name, durable=durable, auto_delete=auto_delete, callback=callback
        )

    def setup_queue(self, queue_name, durable, auto_delete, callback):
        """Setup the queue on RabbitMQ by invoking the Queue.Declare RPC
        command. When it is complete, the on_queue_declareok method will
        be invoked by pika.
        :param str|unicode queue_name: The name of the queue to declare.
        """
        LOGGER.info(f"Declaring queue {queue_name}")
        cb = callback or partial(self.on_queue_declareok, userdata=queue_name)
        self._channel.queue_declare(
            queue=queue_name, durable=durable, auto_delete=auto_delete, callback=cb
        )

    def on_queue_declareok(self, _unused_frame, userdata):
        """Method invoked by pika when the Queue.Declare RPC call made in
        setup_queue has completed. In this method we will bind the queue
        and exchange together with the routing key by issuing the Queue.Bind
        RPC command. When this command is complete, the on_bindok method will
        be invoked by pika.
        :param pika.frame.Method _unused_frame: The Queue.DeclareOk frame
        :param str|unicode userdata: Extra user data (queue name)
        """
        LOGGER.info(f"Queue {userdata} declared")

    def queue_bind(
        self, queue_name: str, exchange_name: str, routing_key: str, callback=None
    ):
        LOGGER.info(f"Binding {exchange_name} to {queue_name} with {routing_key}")
        self._channel.queue_bind(
            queue_name,
            exchange=exchange_name,
            routing_key=routing_key,
            callback=callback,
        )

    def set_qos(self, prefetch_count=1, callback=lambda x: x):
        """This method sets up the consumer prefetch to only be delivered
        one message at a time. The consumer must acknowledge this message
        before RabbitMQ will deliver another one. You should experiment
        with different prefetch values to achieve desired performance.
        """
        self._channel.basic_qos(prefetch_count=prefetch_count, callback=callback)

    def on_response(self, _unused_channel, basic_deliver, properties, body):
        """Invoked by pika when a message is delivered from RabbitMQ. The
        channel is passed for your convenience. The basic_deliver object that
        is passed in carries the exchange, routing key, delivery tag and
        a redelivered flag for the message. The properties passed in is an
        instance of BasicProperties with the message properties and the body
        is the message that was sent.
        :param pika.channel.Channel _unused_channel: The channel object
        :param pika.Spec.Basic.Deliver: basic_deliver method
        :param pika.Spec.BasicProperties: properties
        :param bytes body: The message body
        """
        if properties.correlation_id in self.futures:
            future: Future = self.futures[properties.correlation_id]["response"]
            if not future.done():
                if properties.type == "error":
                    future.set_exception(
                        RpcProviderException(f"Provider Error: {body.decode()}")
                    )
                else:
                    future.set_result(body)
            return not self.auto_ack and self._channel_rpc.basic_ack(
                basic_deliver.delivery_tag
            )
        not self.auto_ack and self._channel_rpc.basic_nack(
            basic_deliver.delivery_tag, requeue=False
        )

    def unsubscribe(self, consumer_tag: str):
        self.rpc_consumer_started = False
        if self.rpc_consumer_starting and not self.rpc_consumer_future.done():
            self.rpc_consumer_future.cancel()
        self._channel.basic_cancel(consumer_tag)

    async def start_rpc_consumer(self):
        if self.rpc_consumer_started:
            return True
        if self.rpc_consumer_starting:
            return await self.rpc_consumer_future
        self.rpc_consumer_starting = True

        self.rpc_consumer_future = self.ioloop.create_future()
        LOGGER.info("Starting rpc consumer")

        def on_open(channel: Channel):
            LOGGER.info("Channel opened - consumer")
            self._channel_rpc.add_on_close_callback(self.on_channel_closed)

            def on_declare(channel):
                self.consumer_tag = self._channel_rpc.basic_consume(
                    queue=self._callback_queue,
                    on_message_callback=self.on_response,
                    auto_ack=self.auto_ack,
                    consumer_tag=None,
                )
                self.rpc_consumer_started = True
                self.rpc_consumer_starting = False
                self.rpc_consumer_future.set_result(True)

            LOGGER.info(f"Declaring queue {self._callback_queue}")
            self._channel_rpc.queue_declare(
                queue=self._callback_queue,
                durable=False,
                auto_delete=True,
                callback=on_declare,
            )

        self._channel_rpc: Channel = self.channel_factory.create_channel(
            self._connection, on_channel_open=on_open
        )

        def attemp_failed():
            if not self.rpc_consumer_future.done():
                self.rpc_consumer_started = False
                self.rpc_consumer_starting = False
                self.rpc_consumer_future.set_exception(
                    EventBusException("Error: cannot set rpc_consumer")
                )

        self.ioloop.call_later(2, attemp_failed)
        return await self.rpc_consumer_future

    async def start_rpc_publisher(self):
        if self.rpc_publisher_started:
            return True
        if self.rpc_publisher_starting:
            return await self.rpc_consumer_future
        self.rpc_publisher_starting = True
        self.rpc_publisher_future = self.ioloop.create_future()

        def on_open(channel: Channel):
            self._channel_rpc.add_on_close_callback(self.on_channel_closed)
            self.rpc_publisher_started = True
            self.rpc_publisher_starting = False
            self.rpc_publisher_future.set_result(True)

        self._channel_rpc: Channel = self.channel_factory.create_channel(
            self._connection, on_channel_open=on_open
        )

        def attemp_failed():
            if not self.rpc_publisher_future.done():
                self.rpc_publisher_started = False
                self.rpc_publisher_starting = False
                self.rpc_publisher_future.set_exception(
                    EventBusException("Error: cannot set rpc_publisher")
                )

        self.ioloop.call_later(2, attemp_failed)
        return await self.rpc_publisher_future

    async def rpc_client(
        self,
        exchange_name: str,
        routing_key: str,
        body,
        content_type,
        timeout,
        delivery_mode=DeliveryMode.Transient,
        expiration: Optional[Union[str, None]] = None,
        **key_args,
    ):
        future = self.ioloop.create_future()
        message = dumps({"resource_name": routing_key, "handle": body})
        corr_id = str(uuid4())
        self.futures[corr_id] = {"response": future}
        clean_response = partial(self.clean_rpc_response, corr_id)
        future.add_done_callback(clean_response)

        await self.start_rpc_consumer()

        self._channel.basic_publish(
            exchange_name,
            routing_key,
            message,
            properties=BasicProperties(
                reply_to=self._callback_queue,
                correlation_id=corr_id,
                content_type=content_type,
                delivery_mode=delivery_mode,
                expiration=expiration,
                **key_args,
            ),
            mandatory=False,
        )

        def not_arrived(id):
            if id in self.futures:
                future = self.futures[id]
                if self.publisher_confirms and not future["published"].done():
                    return future["published"].set_exception(
                        PublishTimeoutException("PublishTimeout: time limit reached")
                    )
                if not future["response"].done():
                    return future["response"].set_exception(
                        ResponseTimeoutException("ResponseTimeout: time limit reached")
                    )

        func = partial(not_arrived, corr_id)
        self.ioloop.call_later(timeout, func)

        if self.publisher_confirms:
            return await self.handle_publish(future, corr_id)
        return await future

    async def handle_publish(self, future, corr_id):
        publish_future = self.ioloop.create_future()
        self.futures[corr_id]["published"] = publish_future
        self.publish_confirmation(publish_future)
        done_all, pending_all = await wait(
            [publish_future, future], return_when=FIRST_COMPLETED
        )
        exception = done_all.pop().exception()
        if exception:
            [undone.cancel() for undone in pending_all]
            raise exception
        elif len(pending_all):
            return await future
        else:
            return future.result()

    async def publish(
        self,
        exchange_name: str,
        routing_key: str,
        body,
        content_type: str,
        timeout=5,
        delivery_mode=DeliveryMode.Transient,
        expiration: Optional[Union[str, None]] = None,
        **key_args,
    ):
        message = dumps({"handle": body})
        self._channel.basic_publish(
            exchange_name,
            routing_key,
            message,
            properties=BasicProperties(
                reply_to=self._callback_queue,
                content_type=content_type,
                delivery_mode=delivery_mode,
                expiration=expiration,
                **key_args,
            ),
            mandatory=False,
        )
        if self.publisher_confirms:
            publish_future = self.ioloop.create_future()
            self.publish_confirmation(publish_future)

            def not_arrived(id):
                if id in self.futures:
                    self.futures[id].set_exception(
                        PublishTimeoutException("Timeout: time limit reached")
                    )

            func = partial(not_arrived, self._message_number)
            self.ioloop.call_later(timeout, func)
            return await publish_future

    def publish_confirmation(self, future: Future):
        self._message_number += 1
        self.futures[self._message_number] = future
        self._deliveries[self._message_number] = future
        clean = partial(self.clean_publish_confirmation, self._message_number)
        future.add_done_callback(clean)

    def clean_publish_confirmation(self, meassage_id, _fut):
        self.futures.pop(meassage_id)
        self._deliveries.pop(meassage_id)

    def clean_rpc_response(self, corr_id, _fut):
        self.futures.pop(corr_id)

    async def rpc_subscribe(
        self,
        exchange_name,
        routing_key: str,
        queue_name: str,
        callback,
        response_timeout,
        content_type="application/json",
        exchange_type="direct",
    ):
        await self.start_rpc_publisher()
        self.add_subscribe(
            queue_name,
            routing_key,
            callback,
            content_type=content_type,
            response_timeout=response_timeout,
        )
        self.setup_exchange(exchange_name, exchange_type)
        self.queue_declare(queue_name)
        self.queue_bind(queue_name, exchange_name, routing_key)
        if queue_name not in self.consumers:
            self.consumers[queue_name] = True
            func = partial(self.on_message, queue_name)
            self._channel.basic_consume(
                queue_name, on_message_callback=func, auto_ack=self.auto_ack
            )

    async def subscribe(
        self,
        exchange_name,
        routing_key: str,
        queue_name: str,
        callback,
        response_timeout,
        content_type="application/json",
        exchange_type="direct",
    ):
        self.add_subscribe(
            queue_name,
            routing_key,
            callback,
            content_type=content_type,
            response_timeout=response_timeout,
        )
        self.setup_exchange(exchange_name, exchange_type)
        self.queue_declare(queue_name, durable=True)
        self.queue_bind(queue_name, exchange_name, routing_key)
        if queue_name not in self.consumers:
            self.consumers[queue_name] = True
            func = partial(self.on_message, queue_name)
            self._channel.basic_consume(
                queue_name, on_message_callback=func, auto_ack=self.auto_ack
            )

    def on_message(
        self, queue_name, _unused_channel, basic_deliver, props: BasicProperties, body
    ):
        """Invoked by pika when a message is delivered from RabbitMQ. The
        channel is passed for your convenience. The basic_deliver object that
        is passed in carries the exchange, routing key, delivery tag and
        a redelivered flag for the message. The properties passed in is an
        instance of BasicProperties with the message properties and the body
        is the message that was sent.
        :param pika.channel.Channel _unused_channel: The channel object
        :param pika.Spec.Basic.Deliver: basic_deliver method
        :param pika.Spec.BasicProperties: properties
        :param bytes body: The message body
        """

        async def handle_message(queue_name, basic_deliver, props, body):
            try:
                if basic_deliver.routing_key in self.subscribes[queue_name]:
                    body = loads(body)
                    response = await wait_for(
                        self.subscribes[queue_name][basic_deliver.routing_key][
                            "handle"
                        ](*body["handle"]),
                        timeout=self.subscribes[queue_name][basic_deliver.routing_key][
                            "response_timeout"
                        ],
                    )
                    if self.rpc_publisher_started and response and props.reply_to:
                        self._channel_rpc.basic_publish(
                            "",
                            props.reply_to,
                            response,
                            properties=BasicProperties(
                                correlation_id=props.correlation_id,
                                content_type=self.subscribes[queue_name][
                                    basic_deliver.routing_key
                                ]["content_type"],
                                type="normal",
                            ),
                        )
                    not self.auto_ack and not self._channel.basic_ack(
                        basic_deliver.delivery_tag
                    )
                else:
                    if self.rpc_publisher_started and props.reply_to:
                        self._channel_rpc.basic_publish(
                            "",
                            props.reply_to,
                            "Provider Error: routing_key not binded",
                            properties=BasicProperties(
                                correlation_id=props.correlation_id,
                                content_type="text/plain",
                                type="error",
                            ),
                        )
                    not self.auto_ack and self._channel.basic_nack(
                        basic_deliver.delivery_tag, requeue=False
                    )
            except BaseException as err:
                if self.rpc_publisher_started and props.reply_to:
                    self._channel_rpc.basic_publish(
                        "",
                        props.reply_to,
                        str(err),
                        properties=BasicProperties(
                            correlation_id=props.correlation_id,
                            content_type=self.subscribes[queue_name][
                                basic_deliver.routing_key
                            ]["content_type"],
                            type="error",
                        ),
                    )
                not self.auto_ack and self._channel.basic_nack(
                    basic_deliver.delivery_tag, requeue=False
                )

        self.ioloop.create_task(handle_message(queue_name, basic_deliver, props, body))

    def add_subscribe(
        self, queue_name, routing_key, handle, content_type, response_timeout=None
    ):
        if queue_name not in self.subscribes:
            if not len(self.subscribes):
                self.subscribes[queue_name] = {}
        if routing_key not in self.subscribes[queue_name]:
            self.subscribes[queue_name][routing_key] = {
                "handle": handle,
                "content_type": content_type,
                "response_timeout": response_timeout or self.response_timeout,
            }
