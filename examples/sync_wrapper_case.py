from amqp_client_python import EventbusWrapperRabbitMQ, Config, Options  # , SSLOptions
from default import queue, rpc_queue, rpc_exchange, rpc_routing_key


config = Config(
    Options(queue, rpc_queue, rpc_exchange),
    # SSLOptions("../.certs/amqp/rabbitmq_cert.pem", "../.certs/amqp/rabbitmq_key.pem", "../.certs/amqp/ca.pem")
)
eventbus = EventbusWrapperRabbitMQ(config=config)


async def subscribe_handler(body) -> None:
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


eventbus.subscribe(rpc_exchange, rpc_routing_key, subscribe_handler).result()
eventbus.provide_resource(rpc_routing_key + "2", handle).result()
eventbus.provide_resource(rpc_routing_key + "3", handle2).result()
count = 0
running = True
while running:
    try:
        count += 1
        if str(count) != eventbus.rpc_client(
            rpc_exchange, rpc_routing_key + "2", count
        ).result().decode("utf-8"):
            running = False
        eventbus.publish(rpc_exchange, rpc_routing_key, "message_content").result()
        # running = False
    except KeyboardInterrupt:
        running = False
    except BaseException as err:
        running = False
        print("Err:", err)

eventbus.dispose()
