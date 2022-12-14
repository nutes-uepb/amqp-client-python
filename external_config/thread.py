from amqp_client_python import (
    EventbusRabbitMQ,
    Config, Options
)
from amqp_client_python.event import IntegrationEvent, IntegrationEventHandler
from external_config.default import queue, rpc_queue, rpc_exchange, rpc_routing_key


class ExampleEvent(IntegrationEvent):
    EVENT_NAME: str = "ExampleEvent"
    ROUTING_KEY: str = rpc_routing_key

    def __init__(self, event_type: str, message = []) -> None:
        super().__init__(self.EVENT_NAME, event_type)
        self.message = message
        self.routing_key = self.ROUTING_KEY


class ExampleEventHandler(IntegrationEventHandler):
    def handle(self, body) -> None:
        print(body,"subscribe")


config = Config(Options(queue, rpc_queue, rpc_exchange))
eventbus = EventbusRabbitMQ(config=config)

class ExampleEvent(IntegrationEvent):
    EVENT_NAME: str = "ExampleEvent"
    def __init__(self, event_type: str, message = []) -> None:
        super().__init__(self.EVENT_NAME, event_type)
        self.message = message

def handle(*body):
    print(body, "rpc_provider")
    return b"result"
from time import sleep
subscribe_event = ExampleEvent(rpc_exchange)
publish_event = ExampleEvent(rpc_exchange, ["message"])
subscribe_event_handle = ExampleEventHandler()
eventbus.provide_resource(rpc_routing_key+"2", handle)
eventbus.subscribe(subscribe_event, subscribe_event_handle, rpc_routing_key+"2")
count = 0
running =True
while running:
    try:
        print("received:", eventbus.rpc_client(rpc_exchange, rpc_routing_key+"2", [f"{count}"]))
        eventbus.publish(publish_event, rpc_routing_key, "direct")
        count += 1
        #running = False
    except TimeoutError:
        print("timeout!!!")
