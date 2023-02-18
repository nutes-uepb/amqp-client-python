from amqp_client_python import EventbusWrapperRabbitMQ, Config, Options
from amqp_client_python.event import IntegrationEvent, IntegrationEventHandler
from default import queue, rpc_queue, rpc_exchange, rpc_routing_key


config = Config(Options(queue, rpc_queue, rpc_exchange))
eventbus = EventbusWrapperRabbitMQ(config=config)


class ExampleEvent(IntegrationEvent):
    EVENT_NAME: str = "ExampleEvent"

    def __init__(self, event_type: str, message=[]) -> None:
        super().__init__(self.EVENT_NAME, event_type)
        self.message = message


class ExampleEventHandler(IntegrationEventHandler):
    async def handle(self, body) -> None:
        print(body, "subscribe")


async def handle(*body):
    print(body[0], "rpc_provider")
    result: bytes = await eventbus.async_rpc_client(
        rpc_exchange, rpc_routing_key + "3", [body[0]]
    )
    print("...")
    return result


async def handle2(*body):
    print(body[0], "rpc_provider2")
    return f"{body[0]}".encode("utf-8")


subscribe_event = ExampleEvent(rpc_exchange)
publish_event = ExampleEvent(rpc_exchange, ["message"])
subscribe_event_handle = ExampleEventHandler()
eventbus.subscribe(subscribe_event, subscribe_event_handle, rpc_routing_key).result()
eventbus.provide_resource(rpc_routing_key + "2", handle).result()
eventbus.provide_resource(rpc_routing_key + "3", handle2).result()
count = 0
running = True
while running:
    try:
        count += 1
        if str(count) != eventbus.rpc_client(
            rpc_exchange, rpc_routing_key + "2", [f"{count}"]
        ).result().decode("utf-8"):
            running = False
        eventbus.publish(publish_event, rpc_routing_key, "direct").result()
        # running = False
    except KeyboardInterrupt:
        running = False
    except BaseException as err:
        running = False
        print("Err:", err)

eventbus.dispose()
