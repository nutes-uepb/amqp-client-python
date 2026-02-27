import pytest
from amqp_client_python import (
    AsyncEventbusRabbitMQ,
    Config,
    Options,
    SSLOptions
)
from asyncio import get_running_loop
from uuid import uuid4
import os

@pytest.fixture()
def loop(): 
    return get_running_loop()

@pytest.fixture(scope="function")
async def async_eventbus(loop):
    config = Config(Options(str(uuid4())[:4], str(uuid4())[:4], str(uuid4())[:4], domain=os.environ.get("AMQP_DOMAIN", "localhost")))
    eventbus = AsyncEventbusRabbitMQ(config, loop)
    yield eventbus
    await eventbus.dispose(stop_event_loop=False)

@pytest.fixture(scope="function")
async def async_eventbus_ssl(loop):
    config = Config(
        Options(str(uuid4())[:4], str(uuid4())[:4], str(uuid4())[:4], domain=os.environ.get("AMQP_DOMAIN", "localhost")),
        SSLOptions("./.certs/amqp/rabbitmq_cert.pem", "./.certs/amqp/rabbitmq_key.pem", "./.certs/amqp/ca.pem")
    )
    eventbus = AsyncEventbusRabbitMQ(config, loop)
    yield eventbus
    await eventbus.dispose(stop_event_loop=False)
