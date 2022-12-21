from amqp_client_python import (
    AsyncEventbusRabbitMQ,
    Config, Options
)
from amqp_client_python.event import IntegrationEvent, IntegrationEventHandler
from default import queue, rpc_queue, rpc_exchange
from asyncio import new_event_loop

loop = new_event_loop()

config = Config(Options(queue, rpc_queue, rpc_exchange))


def handle(*body):
    print(f"body: {body}")
    return b"here"

class ExampleEventHandler(IntegrationEventHandler):
    def handle(self, body) -> None:
        print(body)
    
class ExampleEvent(IntegrationEvent):
    EVENT_NAME: str = "ExampleEvent"
    def __init__(self, event_type: str, message = []) -> None:
        super().__init__(self.EVENT_NAME, event_type)
        self.message = message

from asyncio import sleep
async def run():
    publish_event = ExampleEvent(rpc_exchange, ["message"])
    event_handle = ExampleEventHandler()
    eventbus = AsyncEventbusRabbitMQ(config, loop, rpc_client_publisher_confirms=False)
    await eventbus.provide_resource("user.find", handle)
    #await eventbus.subscribe(publish_event, event_handle, "user.find1")
    while True:
        try:
            print("returned:", await eventbus.rpc_client(rpc_exchange, "user.find", ["content_message"]))
            #print("returned:", await eventbus.publish(publish_event, "user.find1", ["content_message"]))
        except BaseException as err:
            print(f"err: {err}")
            await sleep(3)


loop.create_task(run())
loop.run_forever()