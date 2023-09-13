from amqp_client_python import EventbusRabbitMQ, Config, Options, SSLOptions
from amqp_client_python.event import IntegrationEvent, SubscriberHandler
from default import queue, rpc_queue, rpc_exchange


# do not use if you need use a rpc_client call inside a rpc_provider
config = Config(
    Options(queue, rpc_queue, rpc_exchange),
    # SSLOptions("../.certs/amqp/rabbitmq_cert.pem", "../.certs/amqp/rabbitmq_key.pem", "../.certs/amqp/ca.pem")
)
eventbus = EventbusRabbitMQ(config)
try:
    def handle(*body):
        print(f"body1: {body}")
        return b"response"

    def handle3(*body):
        print(body)

    class ExampleEventHandler(SubscriberHandler):
        event_type = rpc_exchange

        def handle(self, *body) -> None:
            print(body)

    class ExampleEvent(IntegrationEvent):
        EVENT_NAME: str = "NAME"

        def __init__(self, event_type: str, message=[]) -> None:
            super().__init__(self.EVENT_NAME, event_type)
            self.message = message

    publish_event = ExampleEvent(rpc_exchange, ["message"])
    event_handle = ExampleEventHandler()

    eventbus.provide_resource("user.find", handle)
    eventbus.subscribe(publish_event, event_handle, "user.find3")
    count = 0
    running = True
    while running:
        try:
            count += 1
            result = eventbus.rpc_client(rpc_exchange, "user.find", ["content_message"])
            print("returned:", result)
            eventbus.publish(publish_event, "user.find3")
        except BaseException as err:
            running = False
            print(f"err: {err}")
except (KeyboardInterrupt, BaseException) as err:
    print("err", err)
from time import sleep
eventbus.dispose()
