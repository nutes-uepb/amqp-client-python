from typing import MutableMapping, Dict
from .connection_factory_rabbitmq import ConnectionFactoryRabbitMQ
from amqp_client_python.domain.models import Options, SSLOptions
from aio_pika.abc import (
    AbstractRobustChannel,
    AbstractIncomingMessage,
    AbstractRobustExchange,
)
from aio_pika import Message
from asyncio import Future, AbstractEventLoop, get_running_loop, sleep
from uuid import uuid4
from json import dumps, loads
from functools import partial


class ConnectionRabbitMQ:
    def __init__(self) -> None:
        self.connection_factory = ConnectionFactoryRabbitMQ()
        self.connection = None
        self.channels: Dict[str, AbstractRobustChannel] = {}
        self.futures: MutableMapping[str, Future] = {}
        self.callback_queue = None
        self.callback_queue_name = f"amqp.{uuid4()}"
        self.subscribes = {}
        self.loop = None
        self.resorces = {}
        self.consumers = {}
    
    async def open(self, options: Options, ssl_options: SSLOptions, loop: AbstractEventLoop):
        if not self.connection:
            self.loop = loop or get_running_loop()
            self.connection = await self.connection_factory.create_connection(options, ssl_options, loop=loop)
        
    async def create_channel(self, name, publisher_confirms=True, on_return_raises=False):
        if name not in self.channels:
            self.channels[name] = await self.connection.channel(
                publisher_confirms=publisher_confirms,
                on_return_raises=on_return_raises
            )

    def get_channel(self, name):
        if name not in self.channels:
            return self.channels[name]

    async def rpc_client(self, exchange_name: str, routing_key: str, message: str, content_type="text/plain", channel_name="rpc_client", timeout=5):
        exchange = await self.channels[channel_name].declare_exchange(exchange_name)
        if self.connection.is_closed or self.channels[channel_name].is_closed:
            await sleep(timeout)
        if not self.callback_queue:
            self.callback_queue = await self.channels[channel_name].declare_queue(self.callback_queue_name, auto_delete=True)
            await self.callback_queue.bind(exchange_name)
            await self.callback_queue.consume(self.on_response)
        correlation_id = str(uuid4())
        future = self.loop.create_future()
        self.futures[correlation_id] = future
        body = dumps({"handle": message})
        await exchange.publish(
            Message(
                body.encode(),
                content_type=content_type,
                correlation_id=correlation_id,
                reply_to=self.callback_queue.name,
            ),
            routing_key=routing_key,
        )
        def not_loop():
            if correlation_id in self.futures:
                self.futures.pop(correlation_id).set_exception(TimeoutError("timeout limit ranched!!!"))
        self.loop.call_later(timeout, not_loop)

        return await future
    

    async def publish(self,  exchange_name, routing_key, message: str, channel_name="publish", content_type="text/plain"):
        exchange = await self.channels[channel_name].declare_exchange(exchange_name)
        correlation_id = str(uuid4())
        body = dumps({"handle": message})
        await exchange.publish(
            Message(
                body.encode(),
                content_type=content_type,
                correlation_id=correlation_id,
            ),
            routing_key=routing_key
        )
    
    async def on_response(self, message: AbstractIncomingMessage) -> None:
        if message.correlation_id in self.futures:
            future: Future = self.futures.pop(message.correlation_id)
            if message.type == "error":
                future.set_exception(Exception(f"Internal Server Error: {message.body.decode()}"))
            else:
                future.set_result(message.body)
            await message.ack()
    
    async def rpc_subscribe(self, exchange_name, routing_key: str, queue_name: str, callback, content_type, channel_name="provide_resource"):
        await self.add_subscribe(queue_name, routing_key, callback, content_type=content_type)
        exchange = await self.channels[channel_name].declare_exchange(exchange_name)
        queue = await self.channels[channel_name].declare_queue(queue_name)
        await queue.bind(exchange_name, routing_key)
        if queue_name not in self.consumers:
            self.consumers[queue_name] = True
            queue = await self.channels[channel_name].get_queue(queue_name)
            func = partial(self.handle_message, exchange, queue_name)
            await queue.consume(func, no_ack=True)
    
    async def handle_message(self, exchange: AbstractRobustExchange, queue_name: str, message: AbstractIncomingMessage):
        try:
            if queue_name in self.subscribes and message.routing_key in self.subscribes[queue_name]:
                body = loads(message.body)
                response = await self.subscribes[queue_name][message.routing_key]["handle"](*body["handle"])
                if message.reply_to:
                    await exchange.publish(
                        Message(
                            body=response or b"",
                            correlation_id=message.correlation_id,
                            content_type=self.subscribes[queue_name][message.routing_key]["content_type"],
                            type="normal",
                        ),
                        routing_key=message.reply_to
                    )
        except BaseException as err:
            if message.reply_to:
                await exchange.publish(
                    Message(
                        body=str(err).encode(),
                        correlation_id=message.correlation_id,
                        type="error",
                    ),
                    routing_key=message.reply_to
                )

    async def subscribe(self, exchange_name, routing_key: str, queue_name: str, callback, channel_name="subscribe", content_type="text/plain"):
        await self.add_subscribe(queue_name, routing_key, callback, content_type=content_type)
        exchange = await self.channels[channel_name].declare_exchange(exchange_name)
        queue = await self.channels[channel_name].declare_queue(queue_name)
        await queue.bind(exchange_name, routing_key)
        if queue_name not in self.consumers:
            self.consumers[queue_name] = True
            queue = await self.channels[channel_name].get_queue(queue_name)
            func = partial(self.handle_message, exchange, queue_name)
            await queue.consume(func, no_ack=True)

    async def add_subscribe(self, queue_name, routing_key, resource, content_type):
        if queue_name not in self.subscribes:
            if not len(self.subscribes):
                self.subscribes[queue_name] = {}
        if routing_key not in self.subscribes[queue_name]:
            self.subscribes[queue_name][routing_key] = { "handle": resource, "content_type": content_type }

    async def close(self):
        if self.connection.is_closed:
            await self.connection.close()