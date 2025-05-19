import pytest
from amqp_client_python import EventbusWrapperRabbitMQ
from amqp_client_python.event import IntegrationEvent
from asyncio import Future, BaseEventLoop, sleep
from uuid import uuid4


@pytest.mark.asyncio_cooperative
async def test_subscribe(eventbus_wrapper: EventbusWrapperRabbitMQ, loop: BaseEventLoop):
    future = Future(loop = loop)
    async def handle(body):
        if not future.done():
            future.set_result("received message")

    exchange_name = str(uuid4())[:4]
    routing_key = str(uuid4())[:4]
    eventbus_wrapper.subscribe(exchange_name, routing_key, handle).result()
    await sleep(1)
    eventbus_wrapper.publish(exchange_name, routing_key, ["hi"]).result()
    await future
    assert future.done()
    assert future.result
