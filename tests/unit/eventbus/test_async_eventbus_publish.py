from amqp_client_python import AsyncEventbusRabbitMQ
from amqp_client_python.event import IntegrationEvent
from asyncio import iscoroutinefunction
from tests.unit.eventbus.default import async_add_callback
import pytest


@pytest.mark.asyncio_cooperative
async def test_async_eventbus_publish_surface(async_connection_mock, config_mock):
    event_name, exchange, routing_key, body = (
        "example_event",
        "ex_example",
        "rk_example",
        ["content"],
    )
    eventbus = AsyncEventbusRabbitMQ(config_mock)
    eventbus._pub_connection = async_connection_mock
    # create event
    event = IntegrationEvent(event_name, exchange)

    assert iscoroutinefunction(eventbus.publish)
    assert await eventbus.publish(event, routing_key, body) is not None
    # test connection will be open
    eventbus._pub_connection.open.assert_called_once_with(config_mock.build().url)
    # test if will try when connection and channel is open
    eventbus._pub_connection.add_callback.called_once()
    assert len(eventbus._pub_connection.add_callback.call_args.args) == 1
    iscoroutinefunction(eventbus._pub_connection.add_callback.call_args.args[0])


@pytest.mark.asyncio_cooperative
async def test_async_eventbus_publish_deep(async_connection_mock, config_mock):
    (
        event_name,
        exchange,
        routing_key,
        body,
        exchange_type,
        exchange_durable,
        content_type,
        timeout,
    ) = (
        "example_event",
        "ex_example",
        "rk_example",
        ["content"],
        "ex_type",
        "ex_durable",
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
            exchange_type,
            exchange_durable,
            timeout,
        )
        is not None
    )
    # test connection will be open
    eventbus._pub_connection.open.assert_called_once_with(config_mock.build().url)
    # test if will try when connection and channel is open
    eventbus._pub_connection.publish.assert_called_once_with(
        event.event_type, routing_key, body, content_type=content_type, timeout=timeout
    )
