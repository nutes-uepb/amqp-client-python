from amqp_client_python import AsyncEventbusRabbitMQ
from asyncio import iscoroutinefunction
from tests.unit.eventbus.default import async_add_callback
import pytest


@pytest.mark.asyncio_cooperative
async def test_async_eventbus_subscribe_deep(async_connection_mock, config_mock):
    exchange, routing_key, response_time = (
        "ex_example",
        "rk_example",
        None,
    )
    config = config_mock.build()
    eventbus = AsyncEventbusRabbitMQ(config_mock)
    eventbus._sub_connection = async_connection_mock
    eventbus._sub_connection.add_callback = async_add_callback
    # create event
    # create event handler

    async def handle(body) -> None:
        # validate input here!!
        # can use pydantic model -> user = User(*body)
        # do stuff here:
        # self.repository.create_user(user)
        pass

    assert iscoroutinefunction(eventbus.subscribe)
    assert await eventbus.subscribe(exchange, routing_key, handle) is None
    # test connection will be open
    eventbus._sub_connection.open.assert_called_once_with(config.url)
    # test connection.subscribe will be called with right fields
    eventbus._sub_connection.subscribe.assert_called_once_with(
        config.options.queue_name,
        exchange,
        routing_key,
        handle,
        response_time,
    )
