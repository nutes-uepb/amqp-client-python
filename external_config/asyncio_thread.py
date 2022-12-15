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

from time import sleep
from random import randint
def handle(*body):
    print(body[0], "rpc_provider")
    return f"{body[0]}".encode("utf-8")

subscribe_event = ExampleEvent(rpc_exchange)
publish_event = ExampleEvent(rpc_exchange, ["message"])
subscribe_event_handle = ExampleEventHandler()
eventbus.subscribe(subscribe_event, subscribe_event_handle, rpc_routing_key)
eventbus.provide_resource(rpc_routing_key+"2", handle)

from concurrent.futures import TimeoutError
import asyncio
loop = asyncio.new_event_loop()
def create_tasks(st, end):
    return [eventbus.async_rpc_client(rpc_exchange, rpc_routing_key+"2", [f"{count}"], loop=loop) for count in range(st,end)]

async def start():
    count = 0
    running = True
    while running:
        try:
            count += 1
            result = await eventbus.async_rpc_client(rpc_exchange, rpc_routing_key+"2", [f"{count}"], loop=loop)
            if str(count) != result.result().decode("utf-8"):
                running = False
            #eventbus.publish(publish_event, rpc_routing_key, "direct")
            #running = False
        except TimeoutError as err:
            print("timeout!!!: ", str(err))
        except KeyboardInterrupt:
            running=False
        except BaseException as err:
            print("Err:", err)

loop.create_task(start())
loop.run_forever()
