from amqp_client_python import (
    EventbusRabbitMQ,
    Config, Options
)
from external_config.default import queue, rpc_queue, rpc_exchange, rpc_routing_key


config = Config(Options(queue, rpc_queue, rpc_exchange))
eventbus = EventbusRabbitMQ(config=config)

def handle(body):
    print(body)
    return "result"
    
eventbus.provide_resource(rpc_routing_key, handle, auto_ack=False)
eventbus.start_rpc_server()