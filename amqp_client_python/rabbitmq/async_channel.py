from typing import MutableMapping
from .async_channel_factory import AsyncChannelFactoryRabbitMQ
from amqp_client_python.exceptions import NackException, RpcProviderException, TimeoutException
from pika.adapters.asyncio_connection import AsyncioConnection
from pika.channel import Channel
from pika import BasicProperties
from functools import partial
from asyncio import Future
from json import dumps, loads
from uuid import uuid4
from asyncio import AbstractEventLoop
import asyncio


class Message(object):
    """ messaggio ricevuto o di conferma usato nella classe 
    amqpConsumerProducer
    body è il payload del messaggio
    delivery_tag il tag amqp del messaggio
    se il messaggio è usato per conferma/disconferma
    il payload dovrà contenere rispettivamente Treue for "acked"
    and False for "nacked"
    """

    def __init__(self,body,delivery_tag=None):
        self.delivery_tag=delivery_tag
        self.body=body


class asyncChannel:

    def __init__(self, logger) -> None:
        self.logger = logger
        self.ioloop: AbstractEventLoop = None
        self.channel_factory = AsyncChannelFactoryRabbitMQ()
        self._channel: Channel = None
        self._connection:AsyncioConnection = None
        self._callback_queue = f"amqp.{uuid4()}"
        self.futures: MutableMapping[str, Future] = {}
        self.consumer_tag = None
        self.subscribes = {}
        self.consumers = {}
        self.publisher_confirms = False

    @property
    def is_open(self):
        return self._channel and self._channel.is_open

    def open(self, connection: AsyncioConnection):
        if not self.is_open:
            self._connection = connection
            self.ioloop: AbstractEventLoop = connection.ioloop
            self._channel: Channel = self.channel_factory.create_channel(connection, on_channel_open=self.on_channel_open)

    def on_channel_open(self, channel):
        """This method is invoked by pika when the channel has been opened.
        The channel object is passed in so we can make use of it.
        Since the channel is now open, we"ll declare the exchange to use.
        :param pika.channel.Channel channel: The channel object
        """
        self.logger.info("Channel opened")
        self._channel = channel
        self.add_on_channel_close_callback()
        self.publisher_confirms and self.add_publish_confirms()

    def add_on_channel_close_callback(self):
        """This method tells pika to call the on_channel_closed method if
        RabbitMQ unexpectedly closes the channel.
        """
        self.logger.debug("Adding channel close callback")
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
        self.logger.info(f"Channel {channel} was closed: {reason}")
        self._consuming = False
        if self._connection.is_closing or self._connection.is_closed:
            self.logger.info("Connection is closing or already closed")
        else:
            self.logger.info("Closing connection")
            self._connection.close()

    def add_publish_confirms(self):
        self._acked = 0
        self._nacked= 0
        self._deliveries = {}
        self._message_number = 0
        self._channel.confirm_delivery(self.on_delivery_confirmation)
        self.logger.info("Adding Publish Confirmation")
    
    def on_delivery_confirmation(self, method_frame):
        confirmation_type = method_frame.method.NAME.split(".")[1].lower()
        delivery_tag = method_frame.method.delivery_tag
    
        if confirmation_type == "ack":
            self._acked += 1
            if self._deliveries[delivery_tag] == delivery_tag:
                self.futures.pop(delivery_tag).set_result(True)
        elif confirmation_type == "nack":
            self._nacked += 1
            if self._deliveries[delivery_tag] in self.futures:
                self.futures.pop(self._deliveries[delivery_tag]).set_exception(NackException(f"Publish confirmation: nack of {delivery_tag} publish"))

    def setup_exchange(self, exchange_name, exchange_type, durable=True):
        """Setup the exchange on RabbitMQ by invoking the Exchange.Declare RPC
        command. When it is complete, the on_exchange_declareok method will
        be invoked by pika.
        :param str|unicode exchange_name: The name of the exchange to declare
        """
        self.logger.info(f"Declaring exchange: {exchange_name}")
        # Note: using functools.partial is not required, it is demonstrating
        # how arbitrary data can be passed to the callback when it is called
        cb = partial(
            self.on_exchange_declareok, userdata=exchange_name)
        self._channel.exchange_declare(
            exchange=exchange_name,
            exchange_type=exchange_type,
            durable=durable,
            callback=cb)

    def on_exchange_declareok(self, _unused_frame, userdata):
        """Invoked by pika when RabbitMQ has finished the Exchange.Declare RPC
        command.
        :param pika.Frame.Method unused_frame: Exchange.DeclareOk response frame
        :param str|unicode userdata: Extra user data (exchange name)
        """
        self.logger.info(f"Exchange declared: {userdata}")
    
    def queue_declare(self, queue_name: str, durable=False, auto_delete=False, callback=None):
        self.setup_queue(queue_name, durable=durable, auto_delete=auto_delete, callback=callback)
    
    def setup_queue(self, queue_name, durable, auto_delete, callback):
        """Setup the queue on RabbitMQ by invoking the Queue.Declare RPC
        command. When it is complete, the on_queue_declareok method will
        be invoked by pika.
        :param str|unicode queue_name: The name of the queue to declare.
        """
        self.logger.info(f"Declaring queue {queue_name}")
        cb = callback or partial(self.on_queue_declareok, userdata=queue_name)
        self._channel.queue_declare(queue=queue_name, durable=durable,
            auto_delete=auto_delete, callback=cb)
    
    def on_queue_declareok(self, _unused_frame, userdata):
        """Method invoked by pika when the Queue.Declare RPC call made in
        setup_queue has completed. In this method we will bind the queue
        and exchange together with the routing key by issuing the Queue.Bind
        RPC command. When this command is complete, the on_bindok method will
        be invoked by pika.
        :param pika.frame.Method _unused_frame: The Queue.DeclareOk frame
        :param str|unicode userdata: Extra user data (queue name)
        """
        self.logger.info(f"Queue {userdata} declared")
    
    def queue_bind(self, queue_name: str, exchange_name: str, routing_key: str,  callback=None):
        self.logger.info(f"Binding {exchange_name} to {queue_name} with {routing_key}")
        self._channel.queue_bind(
            queue_name,
            exchange=exchange_name,
            routing_key=routing_key,
            callback=callback)
    
    def set_qos(self, prefetch_count=1, callback=lambda x:x):
        """This method sets up the consumer prefetch to only be delivered
        one message at a time. The consumer must acknowledge this message
        before RabbitMQ will deliver another one. You should experiment
        with different prefetch values to achieve desired performance.
        """
        self._channel.basic_qos(
            prefetch_count=prefetch_count, callback=callback)
    
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
            future: Future = self.futures.pop(properties.correlation_id)
            if properties.type == "error":
                future.set_exception(RpcProviderException(f"Provider Error: {body.decode()}"))
            else:
                future.set_result(body)
            self._channel.basic_ack(basic_deliver.delivery_tag)
            return
        self._channel.basic_nack(basic_deliver.delivery_tag, requeue=False)

    async def rpc_client(self, exchange_name: str, routing_key: str, body, loop: AbstractEventLoop, content_type, timeout):
        future = loop.create_future()
        message = dumps({"handle": body})
        corr_id = str(uuid4())
        self.futures[corr_id] = future
        
        self._channel.basic_publish(exchange_name, routing_key, message, properties=BasicProperties(
                reply_to=self._callback_queue,
                correlation_id=corr_id,
                content_type=content_type,
            ))
        if not self.consumer_tag:
            def on_declare():
                self.consumer_tag = self._channel.basic_consume(
                    queue=self._callback_queue,
                    on_message_callback=self.on_response,
                    auto_ack=False,
                    consumer_tag=None
                )
            self.queue_declare(self._callback_queue, durable=False, auto_delete=True, callback=lambda result: on_declare())
        def not_loop(id):
            if id in self.futures:
                self.futures.pop(id).set_exception(TimeoutException("Timeout: time limit reached"))
        func = partial(not_loop, corr_id)
        loop.call_later(timeout, func)
        if self.publisher_confirms:
            publish_future = loop.create_future()
            self._message_number += 1
            self.futures[self._message_number] = publish_future
            self._deliveries[self._message_number] = int(self._message_number)
            await publish_future
        
        return await future
    
    async def publish(self, exchange_name: str, routing_key: str, body, content_type: str, loop: AbstractEventLoop=None):      
        message = dumps({"handle": body})
        self._channel.basic_publish(exchange_name, routing_key, message, properties=BasicProperties(
                reply_to=self._callback_queue,
                content_type=content_type,
            ))
        if self.publisher_confirms:
            future = loop.create_future()
            self._message_number += 1
            self.futures[self._message_number] = future
            self._deliveries[self._message_number] = self._message_number
            return await future

    async def rpc_subscribe(self, exchange_name, routing_key: str, queue_name: str, callback, content_type="application/json", exchange_type="direct", auto_ack=True):
        self.add_subscribe(queue_name, routing_key, callback, content_type=content_type)
        self.setup_exchange(exchange_name, exchange_type)
        self.queue_declare(queue_name)
        self.queue_bind(queue_name, exchange_name, routing_key)
        if queue_name not in self.consumers:
            self.consumers[queue_name] = True
            func = partial(self.on_message, queue_name)
            self._channel.basic_consume(queue_name, on_message_callback=func, auto_ack=auto_ack)
    
    async def subscribe(self, exchange_name, routing_key: str, queue_name: str, callback, content_type="application/json", exchange_type="direct", auto_ack=True):
        self.add_subscribe(queue_name, routing_key, callback, content_type=content_type, rpc=False)
        self.setup_exchange(exchange_name, exchange_type)
        self.queue_declare(queue_name, durable=True)
        self.queue_bind(queue_name, exchange_name, routing_key)
        if queue_name not in self.consumers:
            self.consumers[queue_name] = True
            func = partial(self.on_message, queue_name)
            self._channel.basic_consume(queue_name, on_message_callback=func, auto_ack=auto_ack)

    def on_message(self, queue_name, _unused_channel, basic_deliver, props: BasicProperties, body):
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
        async def handle_message(body):
            try:
                if queue_name in self.subscribes and basic_deliver.routing_key in self.subscribes[queue_name]:
                    body = loads(body)
                    response = await self.subscribes[queue_name][basic_deliver.routing_key]["handle"](*body["handle"])
                    if props.reply_to and self.subscribes[queue_name][basic_deliver.routing_key]["rpc"]:
                        self._channel.basic_publish("", props.reply_to, response, properties=BasicProperties(
                            correlation_id=props.correlation_id,
                            content_type=self.subscribes[queue_name][basic_deliver.routing_key]["content_type"],
                            type="normal",
                        ))
                    self._channel.basic_ack(basic_deliver.delivery_tag)
                else:
                    self._channel.basic_nack(basic_deliver.delivery_tag, requeue=False)
            except BaseException as err:
                if props.reply_to and self.subscribes[queue_name][basic_deliver.routing_key]["rpc"]:
                    self._channel.basic_publish("", props.reply_to, str(err), properties=BasicProperties(
                        correlation_id=props.correlation_id,
                        content_type=self.subscribes[queue_name][basic_deliver.routing_key]["content_type"],
                        type="error",
                    ))
                self._channel.basic_nack(basic_deliver.delivery_tag, requeue=False)
         
        self.ioloop.create_task(handle_message(body))
        

    def add_subscribe(self, queue_name, routing_key, resource, content_type, rpc=True):
        if queue_name not in self.subscribes:
            if not len(self.subscribes):
                self.subscribes[queue_name] = {}
        if routing_key not in self.subscribes[queue_name]:
            self.subscribes[queue_name][routing_key] = { "handle": resource, "content_type": content_type, "rpc": rpc }