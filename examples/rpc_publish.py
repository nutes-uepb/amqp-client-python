from amqp_client_python import (
    EventbusRabbitMQ,
    Config, Options,
)
from examples.default import queue, rpc_queue, rpc_exchange, rpc_routing_key


config = Config(Options(queue, rpc_queue, rpc_exchange))
eventbus = EventbusRabbitMQ(config=config)


print(eventbus.rpc_client(rpc_exchange, rpc_routing_key, ["hello2"]))
# run this example with rpc_subscribe.py to see the complete cicle of sending and receiving messages.