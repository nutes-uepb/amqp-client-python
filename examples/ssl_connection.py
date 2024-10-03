# DEPRECATED EVENTBUS
from typing import Union
from amqp_client_python import EventbusWrapperRabbitMQ, Config, Options, SSLOptions
from examples.default import (
    queue,
    rpc_queue,
    rpc_exchange,
    rpc_routing_key,
    certfile_path,
    keyfile_path,
    ca_certs_path,
    port,
)


config = Config(
    Options(queue, rpc_queue, rpc_exchange, port=port),
    SSLOptions(certfile_path, keyfile_path, ca_certs_path),
)
eventbus = EventbusWrapperRabbitMQ(config=config)


def handle(body) -> Union[str, bytes]:
    print(f"{body}", flush=True)
    return "result"


eventbus.provide_resource(rpc_routing_key, handle).result()
