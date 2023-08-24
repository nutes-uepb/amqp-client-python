# DEPRECATED EVENTBUS
from amqp_client_python import (
    EventbusRabbitMQ,
    Config, Options
)
from examples.default import queue, rpc_queue, rpc_exchange, rpc_routing_key


config = Config(Options(queue, rpc_queue, rpc_exchange))
eventbus = EventbusRabbitMQ(config=config)

def handle(*body):
    print(body)
    return b"result"
    
eventbus.provide_resource(rpc_routing_key, handle)
# run this example with rpc_publish.py to see the complete cicle of sending and receiving messages.