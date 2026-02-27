# DEPRECATED EVENTBUS
from typing import Union
from amqp_client_python import EventbusWrapperRabbitMQ, Config, Options
from examples.default import queue, rpc_queue, rpc_exchange, rpc_routing_key


config = Config(Options(queue, rpc_queue, rpc_exchange))
eventbus = EventbusWrapperRabbitMQ(config=config)


def handle(body) -> Union[str, bytes]:
    print(f"{body}", flush=True)
    return b"result"


eventbus.provide_resource(rpc_routing_key, handle).result()
# run this example with rpc_publish.py to see the complete cicle of sending and receiving messages.
