from amqp_client_python import AsyncEventbusRabbitMQ, DeliveryMode
from amqp_client_python.event import IntegrationEvent
from asyncio import iscoroutinefunction
from tests.unit.eventbus.default import async_add_callback
import pytest
from random import randint


@pytest.mark.asyncio_cooperative
async def test_async_eventbus_publish_surface(async_connection_mock, config_mock):
    event_name, exchange, routing_key, body, connection_timeout = (
        "example_event",
        "ex_example",
        "rk_example",
        ["content"],
        randint(1, 16)
    )
    eventbus = AsyncEventbusRabbitMQ(config_mock)
    eventbus._pub_connection = async_connection_mock
    # create event
    event = IntegrationEvent(event_name, exchange)

    assert iscoroutinefunction(eventbus.publish)
    assert await eventbus.publish(event, routing_key, body, connection_timeout=connection_timeout) is not None
    # test connection will be open
    eventbus._pub_connection.open.assert_called_once_with(config_mock.build().url)
    # test if will try when connection and channel is open
    eventbus._pub_connection.add_callback.assert_called_once()
    assert len(eventbus._pub_connection.add_callback.call_args.args) == 2
    iscoroutinefunction(eventbus._pub_connection.add_callback.call_args.args[0])
    assert eventbus._pub_connection.add_callback.call_args.args[1] == connection_timeout


@pytest.mark.asyncio_cooperative
async def test_async_eventbus_publish_deep(async_connection_mock, config_mock):
    (
        event_name,
        exchange,
        routing_key,
        body,
        content_type,
        timeout,
    ) = (
        "example_event",
        "ex_example",
        "rk_example",
        ["content"],
        "text",
        4,
    )
    eventbus = AsyncEventbusRabbitMQ(config_mock)
    eventbus._pub_connection = async_connection_mock
    eventbus._pub_connection.add_callback = async_add_callback
    # create event
    event = IntegrationEvent(event_name, exchange)

    assert iscoroutinefunction(eventbus.publish)
    assert (
        await eventbus.publish(
            event,
            routing_key,
            body,
            content_type,
            timeout,
        )
        is not None
    )
    # test connection will be open
    eventbus._pub_connection.open.assert_called_once_with(config_mock.build().url)
    # test if will try when connection and channel is open
    eventbus._pub_connection.publish.assert_called_once_with(
        event.event_type,
        routing_key,
        body,
        content_type,
        timeout,
        DeliveryMode.Transient,
        None,
    )
