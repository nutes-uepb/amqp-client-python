import pytest
from amqp_client_python import (
    AsyncEventbusRabbitMQ,
    Config,
    Options,
    SSLOptions
)
from asyncio import get_running_loop


@pytest.fixture()
def loop(): 
    return get_running_loop()

@pytest.fixture(scope="function")
async def async_eventbus(loop):
    config = Config(Options("example", "example.rpc", "example.rpc"))
    eventbus = AsyncEventbusRabbitMQ(config, loop)
    yield eventbus
    await eventbus.dispose(stop_event_loop=False)

@pytest.fixture(scope="function")
async def async_eventbus_ssl(loop):
    config = Config(
        Options("example", "example.rpc", "example.rpc"),
        SSLOptions("./.certs/amqp/rabbitmq_cert.pem", "./.certs/amqp/rabbitmq_key.pem", "./.certs/amqp/ca.pem")
    )
    eventbus = AsyncEventbusRabbitMQ(config, loop)
    yield eventbus
    await eventbus.dispose(stop_event_loop=False)