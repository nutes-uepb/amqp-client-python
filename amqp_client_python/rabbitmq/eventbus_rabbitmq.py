from .connection_rabbitmq import ConnectionRabbitMQ
from ..event import IntegrationEvent
from amqp_client_python.domain.models import Config


class EventbusRabbitMQ:

    def __init__(self, pub_connection:ConnectionRabbitMQ, sub_connection:ConnectionRabbitMQ, rpc_connection:ConnectionRabbitMQ, config: Config) -> None:
        self.pub_connection = pub_connection
        self.sub_connection = sub_connection
        self.rpc_connection = rpc_connection
        self.config = config
        self._rpc_server_initialized = False
    

    def rpc_client(self, exchange: str, routing_key: str, body: str):
        self.rpc_connection.open(self.config.url)
        self.rpc_connection.channel_open()
        return self.rpc_connection.rpc_client(exchange, routing_key, body)

    def publish(self, event:IntegrationEvent, routing_key: str, ioloop_active = False):
        self.pub_connection.open(self.config.url)
        self.pub_connection.channel_open()
        self.pub_connection.declare_exchange(event.event_type, "topic")
        return self.pub_connection.publish(event.event_type, routing_key, event.to_json())
    
    def subscribe(self, event:IntegrationEvent, routing_key: str, callback, auto_ack=True):
        self.sub_connection.open(self.config.url)
        self.sub_connection.channel_open()
        self.sub_connection.declare_exchange(event.event_type, "topic")
        self.sub_connection.subscribe(self.config.queue_name, event.event_type, routing_key, callback=callback, auto_ack=auto_ack)


    def provide_resource(self, name: str, callback, auto_ack=False):
        self.initialize_rpc_server()
        self.rpc_connection.subscribe(self.config.rpc_queue_name, self.config.rpc_queue_name, name, callback=callback, auto_ack=auto_ack)


    def start_consume(self):
        self.sub_connection.start()
    
    def start_rpc_server(self):
        self.rpc_connection.start()


    def initialize_rpc_server(self):
        self.rpc_connection.open(self.config.url)
        self.rpc_connection.channel_open()
        if not self._rpc_server_initialized:
            self.rpc_connection.declare_exchange(self.config.rpc_exchange_name, "direct")
            self.rpc_connection.declare_queue(self.config.rpc_queue_name, durable=True)
            self._rpc_server_initialized=True


    def dispose(self):
        if isinstance(self.pub_connection, ConnectionRabbitMQ): self.sub_connection.close()
        if isinstance(self.sub_connection, ConnectionRabbitMQ): self.sub_connection.close()
        if isinstance(self.rpc_connection, ConnectionRabbitMQ): self.rpc_connection.close()