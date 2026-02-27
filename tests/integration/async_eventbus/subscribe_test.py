import pytest
from amqp_client_python import AsyncEventbusRabbitMQ
from amqp_client_python.event import IntegrationEvent, IntegrationEventHandler
from asyncio import Future, BaseEventLoop, wait_for, sleep
from uuid import uuid4



subscribe_event = IntegrationEvent("test", "test", ["hello"])


@pytest.mark.asyncio_cooperative
async def test_subscribe(async_eventbus: AsyncEventbusRabbitMQ, loop: BaseEventLoop):
    future = Future(loop = loop)
    async def handle(body):
        if not future.done():
            future.set_result(body)

    exchange_name = str(uuid4())[:4]
    routing_key = str(uuid4())[:4]
    await async_eventbus.subscribe(exchange_name, routing_key, handle)
    await sleep(1)
    await async_eventbus.publish(exchange_name, routing_key, ["hi"])
    await wait_for(future, 50)
    assert future.done()
    assert future.result