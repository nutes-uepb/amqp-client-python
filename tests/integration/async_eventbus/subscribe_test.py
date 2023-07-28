import pytest
from amqp_client_python import AsyncEventbusRabbitMQ
from amqp_client_python.event import IntegrationEvent, IntegrationEventHandler
from asyncio import Future, BaseEventLoop, sleep, wait_for


subscribe_event = IntegrationEvent("test", "test", ["hello"])


@pytest.mark.asyncio_cooperative
async def test_subscribe(async_eventbus: AsyncEventbusRabbitMQ, loop: BaseEventLoop):
    future = Future(loop = loop)
    class SubscribeEventHandler(IntegrationEventHandler):
        async def handle(self, body):
            future.set_result("received message")

    await async_eventbus.subscribe(subscribe_event, SubscribeEventHandler(), "sub.receive")
    await async_eventbus.publish(subscribe_event, "sub.receive", ["hi"])
    await future
    assert future.done()
    assert future.result
