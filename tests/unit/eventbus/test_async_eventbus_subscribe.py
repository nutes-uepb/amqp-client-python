from amqp_client_python import AsyncEventbusRabbitMQ
from amqp_client_python.event import IntegrationEvent, IntegrationEventHandler
from asyncio import iscoroutinefunction
from tests.unit.eventbus.default import async_add_callback
import pytest


@pytest.mark.asyncio_cooperative
async def test_async_eventbus_subscribe_deep(async_connection_mock, config_mock):
    event_name, exchange, routing_key = "example_event", "ex_example", "rk_example"
    config = config_mock.build()
    eventbus = AsyncEventbusRabbitMQ(config_mock)
    eventbus._sub_connection = async_connection_mock
    eventbus._sub_connection.add_callback = async_add_callback
    # create event
    event = IntegrationEvent(event_name, exchange)
    # create event handler

    class CreateUserEventHandler(IntegrationEventHandler):
        # inject dependencies
        # def __init__(self, repository) -> None:
        # self.repository = repository

        async def handle(self, *body):
            # validate input here!!
            # can use pydantic model -> user = User(*body)
            # do stuff here:
            # self.repository.create_user(user)
            pass

    event_handler = CreateUserEventHandler()

    assert iscoroutinefunction(eventbus.subscribe)
    assert await eventbus.subscribe(event, event_handler, routing_key) is None
    # test connection will be open
    eventbus._sub_connection.open.assert_called_once_with(config.url)
    # test connection.subscribe will be called with right fields
    eventbus._sub_connection.subscribe.assert_called_once_with(
        config.options.queue_name, event.event_type, routing_key, event_handler.handle
    )
