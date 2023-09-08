from amqp_client_python import (
    AsyncEventbusRabbitMQ,
    Config, Options
)
from amqp_client_python.event import IntegrationEvent, AsyncSubscriberHandler
from default import queue, rpc_queue, rpc_exchange
# from uvloop import new_event_loop # better performance, no windows-OS support
from asyncio import new_event_loop # great performance, great OS compatibility

loop = new_event_loop()

config = Config(
    Options(queue, rpc_queue, rpc_exchange),
    # SSLOptions("../.certs/amqp/rabbitmq_cert.pem", "../.certs/amqp/rabbitmq_key.pem", "../.certs/amqp/ca.pem")
)


async def handle(*body):
    print(f"body: {body}")
    response = await eventbus.rpc_client(rpc_exchange, "user.find2", ["content_message"])
    print("...")
    return response

async def handle2(*body):
    print(f"body: {body}")
    return b"here"

async def handle3(*body):
    print(body)

class ExampleEventHandler(AsyncSubscriberHandler):
    event_type = rpc_exchange
    async def handle(self, body) -> None:
        print(body)
    
class ExampleEvent(IntegrationEvent):
    EVENT_NAME: str = "NAME"
    def __init__(self, event_type: str, message = []) -> None:
        super().__init__(self.EVENT_NAME, event_type)
        self.message = message


publish_event = ExampleEvent(rpc_exchange, ["message"])
event_handle = ExampleEventHandler()

# rpc_client call inside rpc_provider
#if __name__ == "__main__":
eventbus = AsyncEventbusRabbitMQ(config, loop, rpc_client_publisher_confirms=True, rpc_server_publisher_confirms=False, rpc_server_auto_ack=False)

async def run():
    await eventbus.provide_resource("user.find", handle)
    await eventbus.provide_resource("user.find2", handle2)
    await eventbus.subscribe(publish_event, event_handle,"user.find3")
    count = 0
    running = True
    while running:
        try:
            count += 1
            result = await eventbus.rpc_client(rpc_exchange, "user.find", ["content_message"])
            print("returned:", result)
            await eventbus.publish(publish_event, "user.find3", ["content_message"])
        except BaseException as err:
            print(f"err: {err}")


loop.create_task(run())
loop.run_forever()