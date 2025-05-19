import pytest
from amqp_client_python import AsyncEventbusRabbitMQ
from asyncio import Future, BaseEventLoop, sleep
from uuid import uuid4


@pytest.mark.asyncio_cooperative
async def test_provider(async_eventbus: AsyncEventbusRabbitMQ, loop: BaseEventLoop):
    expected_result = "received message"
    future = Future(loop = loop)
    async def handle(body):
        future.set_result(expected_result)
        return "hello"
    routing_key = str(uuid4())[:4]
    await async_eventbus.provide_resource(routing_key, handle, 50)
    await sleep(1)
    result = await async_eventbus.rpc_client(async_eventbus.config.options.rpc_exchange_name, routing_key, ["hi"])
    assert future.done()
    assert future.result() == expected_result
    assert result == b"hello"
    
