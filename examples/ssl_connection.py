# DEPRECATED EVENTBUS
from amqp_client_python import (
    EventbusRabbitMQ,
    Config, Options,
    SSLOptions
)
from examples.default import ( queue, rpc_queue, rpc_exchange, rpc_routing_key,
    certfile_path, keyfile_path, ca_certs_path, port
)


config = Config(Options(queue, rpc_queue, rpc_exchange, port=port), SSLOptions(certfile_path, keyfile_path, ca_certs_path))
eventbus = EventbusRabbitMQ(config=config)

def handle(body):
    print(body)
    return "result"
    
eventbus.provide_resource(rpc_routing_key, handle)
eventbus.start_rpc_server()