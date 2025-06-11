import pytest
from amqp_client_python import (
    EventbusWrapperRabbitMQ,
    Config,
    Options,
    SSLOptions
)
from asyncio import get_running_loop
from uuid import uuid4
import os


@pytest.fixture(scope="function")
def loop(): 
    return get_running_loop()

@pytest.fixture(scope="function")
async def eventbus_wrapper():
    config = Config(Options(str(uuid4())[:4], str(uuid4())[:4], str(uuid4())[:4], domain=os.environ.get("AMQP_DOMAIN", "localhost")))
    eventbus = EventbusWrapperRabbitMQ(config)
    yield eventbus
    eventbus.dispose()

@pytest.fixture(scope="function")
async def eventbus_wrapper_ssl():
    config = Config(
        Options(str(uuid4())[:4], str(uuid4())[:4], str(uuid4())[:4], domain=os.environ.get("AMQP_DOMAIN", "localhost")),
        SSLOptions("./.certs/amqp/rabbitmq_cert.pem", "./.certs/amqp/rabbitmq_key.pem", "./.certs/amqp/ca.pem")
    )
    eventbus = EventbusWrapperRabbitMQ(config)
    yield eventbus
    eventbus.dispose()