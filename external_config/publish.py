from amqp_client_python import (
    EventbusRabbitMQ,
    Config, Options
)
from amqp_client_python.event import IntegrationEvent
from external_config.default import queue, rpc_queue, rpc_exchange, rpc_routing_key


class ExampleEvent(IntegrationEvent):
    EVENT_NAME: str = "ExampleEvent"
    def __init__(self, event_type: str, message = []) -> None:
        super().__init__(self.EVENT_NAME, event_type)
        self.message = message


config = Config(Options(queue, rpc_queue, rpc_exchange))
eventbus = EventbusRabbitMQ(config=config)


publish_event = ExampleEvent("EventName", rpc_exchange, ["message"])
print(eventbus.publish(publish_event, rpc_routing_key, "direct"))