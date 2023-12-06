There are 3 types of eventbus available:

1. AsyncEventBus
    - It uses an eventloop as core, like asyncio and uvloop.
<details><summary>async usage </summary>

<br>

```Python
# basic configuration
from amqp_client_python import (
    AsyncEventbusRabbitMQ,
    Config, Options
)
from amqp_client_python.event import IntegrationEvent, IntegrationEventHandler
config = Config(Options("queue", "rpc_queue", "rpc_exchange"))
eventbus = AsyncEventbusRabbitMQ(config)
# publish
class ExampleEvent(IntegrationEvent):
    EVENT_NAME: str = "ExampleEvent"
    def __init__(self, event_type: str, message = []) -> None:
        super().__init__(self.EVENT_NAME, event_type)
        self.message = message

publish_event = ExampleEvent(rpc_exchange, ["message"])
eventbus.publish(publish_event, rpc_routing_key, "direct")
# subscribe
class ExampleEventHandler(IntegrationEventHandler):
    async def handle(self, body) -> None:
        print(body) # handle messages
await eventbus.subscribe(subscribe_event, subscribe_event_handle, rpc_routing_key)
# rpc_publish
response = await eventbus.rpc_client(rpc_exchange, "user.find", ["content_message"])
# provider
async def handle2(*body) -> bytes:
    print(f"body: {body}")
    return b"content"
await eventbus.provide_resource("user.find", handle)
```
</details>
2. Eventbus
    - It uses a basic IoLoop that runs on separated thread
<details><summary>sync usage</summary>

```Python
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
count = 0
running = True
from concurrent.futures import TimeoutError
while running:
    try:
        count += 1
        if str(count) != eventbus.rpc_client(rpc_exchange, rpc_routing_key+"2", [f"{count}"]).decode("utf-8"):
            running = False
        #eventbus.publish(publish_event, rpc_routing_key, "direct")
        #running = False
    except TimeoutError as err:
        print("timeout!!!: ", str(err))
    except KeyboardInterrupt:
        running=False
    except BaseException as err:
        print("Err:", err)
```
</details>
3. EventbusWrapper
    - It uses an eventloop that run on separeted thread.
<details><summary>sync wrapper usage</summary>

```Python
from amqp_client_python import EventbusWrapperRabbitMQ, Config, Options
from amqp_client_python.event import IntegrationEvent, IntegrationEventHandler

config = Config(Options(queue, rpc_queue, rpc_exchange))
eventbus = EventbusWrapperRabbitMQ(config=config)

class ExampleEvent(IntegrationEvent):
    EVENT_NAME: str = "ExampleEvent"
    def __init__(self, event_type: str, message = []) -> None:
        super().__init__(self.EVENT_NAME, event_type)
        self.message = message
class ExampleEventHandler(IntegrationEventHandler):
    async def handle(self, body) -> None:
        print(body,"subscribe")

async def handle(*body):
    print(body[0], "rpc_provider")
    return f"{body[0]}".encode("utf-8")

subscribe_event = ExampleEvent(rpc_exchange)
publish_event = ExampleEvent(rpc_exchange, ["message"])
subscribe_event_handle = ExampleEventHandler()
# rpc_provider
eventbus.provide_resource(rpc_routing_key+"2", handle).result()
# subscribe
eventbus.subscribe(subscribe_event, subscribe_event_handle, rpc_routing_key).result()
count = 0
running = True
while running:
    try:
        count += 1
        # rpc_client call
        eventbus.rpc_client(rpc_exchange, rpc_routing_key+"2", [f"{count}"]).result().decode("utf-8")
        # publish
        eventbus.publish(publish_event, rpc_routing_key, "direct").result()
        #running = False
    except KeyboardInterrupt:
        running=False
    except BaseException as err:
        print("Err:", err)
```
</details>