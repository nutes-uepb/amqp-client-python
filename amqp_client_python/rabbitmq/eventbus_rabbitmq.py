from .connection_rabbitmq import ConnectionRabbitMQ
from ..event import IntegrationEvent, IntegrationEventHandler
from amqp_client_python.domain.models import Config
from typing import Any, List

class EventbusRabbitMQ:

    def __init__(self, config: Config) -> None:
        self.pub_connection = ConnectionRabbitMQ()
        self.sub_connection = ConnectionRabbitMQ()
        self.rpc_client_connection = ConnectionRabbitMQ()
        self.rpc_server_connection = ConnectionRabbitMQ()
        self.config = config.build()
        self._rpc_server_initialized = False
    
    def rpc_client(self, exchange: str, routing_key: str, body: List[Any], content_type="application/json", timeout=5):
        self.rpc_client_connection.open(self.config.url)
        self.rpc_client_connection.channel_open()
        return self.rpc_client_connection.rpc_client(exchange, routing_key, body, content_type=content_type, timeout=timeout)

    def publish(self, event: IntegrationEvent, routing_key: str, exchange_type: str = "direct", exchange_durable=True, ioloop_active = False):
        self.pub_connection.open(self.config.url)
        self.pub_connection.channel_open()
        self.pub_connection.declare_exchange(event.event_type, exchange_type, durable=exchange_durable)
        return self.pub_connection.publish(event.event_type, routing_key, event.message)
    
    def subscribe(self, event: IntegrationEvent, handler: IntegrationEventHandler, routing_key: str, exchange_type: str = "direct", exchange_durable=True, queue_durable=True, queue_auto_delete=False):
        self.sub_connection.open(self.config.url)
        self.sub_connection.channel_open()
        self.sub_connection.declare_exchange(event.event_type, exchange_type, durable=exchange_durable)
        self.sub_connection.declare_queue(self.config.options.queue_name, durable=queue_durable, auto_delete=queue_auto_delete)
        self.sub_connection.subscribe(self.config.options.queue_name, event.event_type, routing_key, callback=handler.handle, auto_ack=True)

    def provide_resource(self, name: str, callback):
        self.initialize_rpc_server()
        self.rpc_server_connection.rpc_subscribe(self.config.options.rpc_queue_name, self.config.options.rpc_queue_name, name, callback=callback)

    def start_consume(self):
        self.sub_connection.start()
    
    def start_rpc_server(self):
        self.rpc_server_connection.start()

    def initialize_rpc_server(self):
        self.rpc_server_connection.open(self.config.url)
        self.rpc_server_connection.channel_open()
        if not self._rpc_server_initialized:
            self.rpc_server_connection.declare_exchange(self.config.options.rpc_exchange_name, "direct")
            self.rpc_server_connection.declare_queue(self.config.options.rpc_queue_name, durable=False)
            self._rpc_server_initialized=True

    def dispose(self):
        if isinstance(self.pub_connection, ConnectionRabbitMQ): self.sub_connection.close()
        if isinstance(self.sub_connection, ConnectionRabbitMQ): self.sub_connection.close()
        if isinstance(self.rpc_client_connection, ConnectionRabbitMQ): self.rpc_client_connection.close()
        if isinstance(self.rpc_server_connection, ConnectionRabbitMQ): self.rpc_server_connection.close()