from .channel_factory_rabbitmq import ChannelFactoryRabbitMQ
from pika.channel import Channel
from pika import BasicProperties
from functools import partial
from uuid import uuid4
from urllib.parse import parse_qs
from json import loads, dumps
from json.decoder import JSONDecodeError
import re


class ChannelRabbitMQ:
    def __init__(self, channel_factory:ChannelFactoryRabbitMQ, logger) -> None:
        self.channel_factory = channel_factory
        self.consumer_tag = None
        self.logger = logger
        self._channel = None
        self.corr_id = None
        self._callback_queue = None
        self.consumers = {}
        self._stopping=False
    
    def open(self, connection, ioloop_active = False):
        self._channel = None
        self.consumers = {}
        self._callback_queue = f"amqp.{uuid4()}"
        self.consumer_tag = None
        self._connection = connection
        self.start = self._connection.start
        self.stop = self._connection.pause
        self.reconnect = self._connection.reconnect
        self._stopping = self._connection._stopping
        callback=partial(self.on_channel_open, ioloop_actor= None if ioloop_active else self.stop)
        self.channel_factory.create_channel(connection._connection, callback)
        if not ioloop_active:
            self.start()
    
    def on_channel_open(self,channel, ioloop_actor=None):
        """This method is invoked by pika when the channel has been opened.
        The channel object is passed in so we can make use of it.
        Since the channel is now open, we'll declare the exchange to use.
        :param pika.channel.Channel channel: The channel object
        """
        self.logger.debug('Channel opened')
        self._channel:Channel = channel
        self.add_on_channel_close_callback()
        if ioloop_actor:
            ioloop_actor()
    
    def config_exchange(self, exchange_name, exchange_type, routing_key, durable=True):
        self.exchange_name = exchange_name
        self.exchange_type = exchange_type
        self.routing_key = routing_key
        self.exchange_durable = durable

    def declare_exchange(self, exchange, exchange_type, durable=True, callback=None):
        """Setup the exchange on RabbitMQ by invoking the Exchange.Declare RPC
        command. When it is complete, the on_exchange_declareok method will
        be invoked by pika.
        :param str|unicode exchange_name: The name of the exchange to declare
        """
        self.logger.debug('Declaring exchange %s', exchange)
        # Note: using functools.partial is not required, it is demonstrating
        # how arbitrary data can be passed to the callback when it is called
        cb = partial(
            callback or self.on_exchange_declareok, userdata=exchange, callback=callback)
        self._channel.exchange_declare(
            exchange=exchange, durable=durable,
            exchange_type=exchange_type,
            callback=cb)
    
    def on_exchange_declareok(self, _unused_frame, userdata, callback=None):
        """Invoked by pika when RabbitMQ has finished the Exchange.Declare RPC
        command.
        :param pika.Frame.Method unused_frame: Exchange.DeclareOk response frame
        :param str|unicode userdata: Extra user data (exchange name)
        """
        self.logger.debug('Exchange declared: %s', userdata)
        if callback:
            callback()
        self.stop()

    def queue_declare(self, queue_name: str, durable=False, auto_delete=False, callback=None):
        """Setup the queue on RabbitMQ by invoking the Queue.Declare RPC
        command. When it is complete, the on_queue_declareok method will
        be invoked by pika.
        :param str|unicode queue_name: The name of the queue to declare.
        """
        self.logger.debug('Declaring queue %s', queue_name)
        self._channel.queue_declare(
            queue=queue_name, durable=durable, auto_delete=auto_delete, callback=callback)

    def queue_bind(self, queue="", exchange="", routing_key="", stop_ioloop: bool=False):
        """Method invoked by pika when the Queue.Declare RPC call made in
        setup_queue has completed. In this method we will bind the queue
        and exchange together with the routing key by issuing the Queue.Bind
        RPC command. When this command is complete, the on_bindok method will
        be invoked by pika.
        :param pika.frame.Method method_frame: The Queue.DeclareOk frame
        """
        self.logger.debug('Binding %s to %s with %s', exchange, queue,
                    routing_key)
        self._channel.queue_bind(
            queue,
            exchange,
            routing_key=routing_key,
            callback=self.on_bindok)
        if stop_ioloop:
            self._connection.stop()

    def on_bindok(self, _unused_frame):
        """This method is invoked by pika when it receives the Queue.BindOk
        response from RabbitMQ. Since we know we're now setup and bound, it's
        time to start publishing."""
        self.logger.debug('Queue bound')

    def add_on_return_callback(self, callback):
        self.logger.debug('Adding channel return callback')
        self._channel.add_on_return_callback(callback)


    def add_on_channel_close_callback(self):
        """This method tells pika to call the on_channel_closed method if
        RabbitMQ unexpectedly closes the channel.
        """
        self.logger.debug('Adding channel close callback')
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
        self.logger.warning('Channel %i was closed: %s', channel, reason)

        if(reason[0]==406):
            self.open(self._connection, False)

        self._channel = None
        if not self._stopping:
            if not self._connection.is_open():
                self.reconnect()
                #self._connection._connection.ioloop.call_later(5, self._connection.pause)
            else:
                self._connection.close()
        
    def is_open(self)->bool:
        return self._channel and self._channel.is_open
    
    def close_channel(self):
        """Invoke this command to close the channel with RabbitMQ by sending
        the Channel.Close RPC command.
        """
        if self._channel is not None:
            self.logger.debug('Closing the channel')
            self._channel.close()

    def rpc_client(self, exchange, routing_key, message, ioloop_actor = None):
        message = dumps({"handle": message})
        self.corr_id = str(uuid4())
        self.response=None
        self._channel.basic_publish(exchange, routing_key, message, properties=BasicProperties(
                reply_to=self._callback_queue,
                correlation_id=self.corr_id,
                content_type='application/json'
            ))
        def on_declare():
            self._channel.basic_consume(
                queue=self._callback_queue,
                on_message_callback = self.__on_response,
                auto_ack=True,
                consumer_tag=None
            )
        self.queue_declare(self._callback_queue, durable=False, auto_delete=True, callback=lambda result:on_declare())
        
        self.start(force=True)
        if self.response:
            return self.response
        self.logger.warning("Empty response")
        return '[]'
    
    def publish(self, exchange:str, routing_key:str, message):
        self._channel.confirm_delivery(lambda x: self.stop() )
        self._channel.basic_publish(exchange,routing_key, message, properties=BasicProperties(
                content_type='application/json'
            ))
        self.start()
    
    def serve_resource(self, ch: Channel, method, props, body: bytes):
        if method.routing_key in self.consumers:
            try:
                body = self.mount_body(body)
                content = self.consumers[method.routing_key](body)
                ch.basic_publish(exchange='', routing_key=props.reply_to, properties=BasicProperties(correlation_id=props.correlation_id), body=content)
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception:
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    def mount_body(self, body: bytes):
        try:
            body = loads(body)
            if "handle" in body:
                body = body["handle"]
                if isinstance(body, str) and self.is_qs(body):
                    body = parse_qs(body[1:])
        except JSONDecodeError:
            body=body.decode("utf8")
            if isinstance(body, str) and self.is_qs(body):
                body = parse_qs(body[1:])
        finally:
            return body

    @staticmethod
    def is_qs(string: str):
        return re.match(r"^([?])([a-z_A-Z]{0,20})=", string)
            
    def addResource(self, name: str, resource) -> bool:
        if not hasattr(self.consumers, name): 
            self.consumers[name] = resource
            return True
        return False


    def subscribe(self, queue_name:str, exchange:str, routing_key:str, callback=None, auto_ack=True, consumer_tag=None, auto_delete=False):
        if self.is_open():
            if not self.consumer_tag:
                self.consumer_tag = self._channel.basic_consume(
                queue = queue_name,
                on_message_callback = self.serve_resource or self.__on_response,
                auto_ack=auto_ack,
                consumer_tag=consumer_tag
            )
            self.addResource(routing_key, callback)
            self._channel.queue_bind(exchange=exchange,
                queue=queue_name, routing_key=routing_key)
            self.queue_declare(queue_name, durable=True, auto_delete=auto_delete, callback=lambda result:result)

            # self._channel.add_on_return_callback(self.serve_resource or self.__on_response)
    
    def unsubscribe(self, consumer_tag:str):
        self._channel.basic_cancel(consumer_tag, callback=lambda x: self.stop())
    
    def __on_response(self, ch:Channel, method, props, body):
        if self.corr_id == props.correlation_id:
            self.response = body
            # ch.basic_ack(delivery_tag=method.delivery_tag)
        else:
            self.response = None
            # ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        self.stop()

    def close(self):
        if self.is_open():
            self._channel.close()
