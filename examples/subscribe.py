# DEPRECATED
from amqp_client_python import (
    EventbusRabbitMQ,
    Config, Options
)
from amqp_client_python.event import IntegrationEvent, IntegrationEventHandler
from examples.default import queue, rpc_queue, rpc_exchange, rpc_routing_key


class ExampleEvent(IntegrationEvent):
    EVENT_NAME: str = "ExampleEvent"
    ROUTING_KEY: str = rpc_routing_key

    def __init__(self, event_type: str, message = []) -> None:
        super().__init__(self.EVENT_NAME, event_type)
        self.message = message
        self.routing_key = self.ROUTING_KEY


class ExampleEventHandler(IntegrationEventHandler):
    def handle(self, body) -> None:
        print(body)


config = Config(Options(queue, rpc_queue, rpc_exchange))
eventbus = EventbusRabbitMQ(config=config)

def handle(*body):
    print(body)
    return "result"

subscribe_event = ExampleEvent(rpc_exchange)
subscribe_event_handle = ExampleEventHandler()
eventbus.subscribe(subscribe_event, subscribe_event_handle, rpc_routing_key)
# run this example with publish.py to see the complete cicle of sending and receiving messages.