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

@pytest.fixture(scope="module")
async def async_eventbus(loop):
    config = Config(Options("example", "example.rpc", "example.rpc"))
    return AsyncEventbusRabbitMQ(config, loop)
