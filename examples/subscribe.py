# DEPRECATED
from amqp_client_python import EventbusWrapperRabbitMQ, Config, Options
from examples.default import queue, rpc_queue, rpc_exchange, rpc_routing_key


config = Config(Options(queue, rpc_queue, rpc_exchange))
eventbus = EventbusWrapperRabbitMQ(config=config)


def handler(body) -> None:
    print(f"{body}", flush=True)


eventbus.subscribe(rpc_exchange, rpc_routing_key, handler).result()
# run this example with publish.py to see the complete cicle of sending and receiving messages.
