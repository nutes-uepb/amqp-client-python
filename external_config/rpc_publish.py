from amqp_client_python import (
    EventbusRabbitMQ,
    Config, Options,
)
from external_config.default import queue, rpc_queue, rpc_exchange, rpc_routing_key


config = Config(Options(queue, rpc_queue, rpc_exchange))
eventbus = EventbusRabbitMQ(config=config)


print(eventbus.rpc_client(rpc_exchange, rpc_routing_key, ["hello2"]))