import pytest
from amqp_client_python import (
    EventbusWrapperRabbitMQ,
    Config,
    Options,
    SSLOptions
)
from asyncio import get_running_loop


@pytest.fixture(scope="function")
def loop(): 
    return get_running_loop()

@pytest.fixture(scope="function")
async def eventbus_wrapper():
    config = Config(Options("example", "example.rpc", "example.rpc"))
    eventbus = EventbusWrapperRabbitMQ(config)
    yield eventbus
    eventbus.dispose()

@pytest.fixture(scope="function")
async def eventbus_wrapper_ssl():
    config = Config(
        Options("example", "example.rpc", "example.rpc"),
        SSLOptions("./.certs/amqp/rabbitmq_cert.pem", "./.certs/amqp/rabbitmq_key.pem", "./.certs/amqp/ca.pem")
    )
    eventbus = EventbusWrapperRabbitMQ(config)
    yield eventbus
    eventbus.dispose()