import pytest
from amqp_client_python import (
    EventbusRabbitMQ,
    Config,
    Options,
)


@pytest.fixture(scope="module")
def eventbus():
    config = Config(Options("example", "example.rpc", "example.rpc"))
    return EventbusRabbitMQ(config=config)