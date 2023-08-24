import pytest
from amqp_client_python import EventbusWrapperRabbitMQ
from amqp_client_python.event import IntegrationEvent, IntegrationEventHandler
from asyncio import Future, BaseEventLoop, sleep


subscribe_event = IntegrationEvent("test", "test", ["hello"])


@pytest.mark.asyncio_cooperative
async def test_subscribe(eventbus_wrapper: EventbusWrapperRabbitMQ, loop: BaseEventLoop):
    future = Future(loop = loop)
    class SubscribeEventHandler(IntegrationEventHandler):
        async def handle(self, body):
            if not future.done():
                future.set_result("received message")

    eventbus_wrapper.subscribe(subscribe_event, SubscribeEventHandler(), "sub.receive").result()
    eventbus_wrapper.publish(subscribe_event, "sub.receive", ["hi"]).result()
    await future
    assert future.done()
    assert future.result
    await sleep(1)
