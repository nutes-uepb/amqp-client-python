from .connection_rabbitmq import ConnectionRabbitMQ
from ..event import IntegrationEvent, IntegrationEventHandler
from amqp_client_python.domain.models import Config
from typing import Any, List

class EventbusRabbitMQ:

    def __init__(self, config: Config) -> None:
        self.pub_connection = ConnectionRabbitMQ()
        self.sub_connection = ConnectionRabbitMQ()
        self.rpc_connection = ConnectionRabbitMQ()
        self.config = config.build()
        self._rpc_server_initialized = False
    
    def rpc_client(self, exchange: str, routing_key: str, body: List[Any]):
        self.rpc_connection.open(self.config.url)
        self.rpc_connection.channel_open()
        return self.rpc_connection.rpc_client(exchange, routing_key, body)

    def publish(self, event: IntegrationEvent, routing_key: str, exchange_type: str = "direct", ioloop_active = False):
        self.pub_connection.open(self.config.url)
        self.pub_connection.channel_open()
        self.pub_connection.declare_exchange(event.event_type, exchange_type)
        return self.pub_connection.publish(event.event_type, routing_key, event.message)
    
    def subscribe(self, event: IntegrationEvent, handler: IntegrationEventHandler, routing_key: str, exchange_type: str = "direct"):
        self.sub_connection.open(self.config.url)
        self.sub_connection.channel_open()
        self.sub_connection.declare_exchange(event.event_type, exchange_type)
        self.sub_connection.declare_queue(self.config.options.queue_name, durable=True)
        self.sub_connection.subscribe(self.config.options.queue_name, event.event_type, routing_key, callback=handler.handle, auto_ack=True)

    def provide_resource(self, name: str, callback):
        self.initialize_rpc_server()
        self.rpc_connection.rpc_subscribe(self.config.options.rpc_queue_name, self.config.options.rpc_queue_name, name, callback=callback)

    def start_consume(self):
        self.sub_connection.start()
    
    def start_rpc_server(self):
        self.rpc_connection.start()

    def initialize_rpc_server(self):
        self.rpc_connection.open(self.config.url)
        self.rpc_connection.channel_open()
        if not self._rpc_server_initialized:
            self.rpc_connection.declare_exchange(self.config.options.rpc_exchange_name, "direct")
            self.rpc_connection.declare_queue(self.config.options.rpc_queue_name, durable=False)
            self._rpc_server_initialized=True

    def dispose(self):
        if isinstance(self.pub_connection, ConnectionRabbitMQ): self.sub_connection.close()
        if isinstance(self.sub_connection, ConnectionRabbitMQ): self.sub_connection.close()
        if isinstance(self.rpc_connection, ConnectionRabbitMQ): self.rpc_connection.close()