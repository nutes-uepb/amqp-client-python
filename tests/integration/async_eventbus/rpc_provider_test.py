import pytest
from amqp_client_python import AsyncEventbusRabbitMQ
from amqp_client_python.event import IntegrationEvent
from asyncio import Future, BaseEventLoop, sleep


@pytest.mark.asyncio_cooperative
async def test_provider(async_eventbus: AsyncEventbusRabbitMQ, loop: BaseEventLoop):
    expected_result = "received message"
    future = Future(loop = loop)
    async def handle(body):
        future.set_result(expected_result)
        return "hello"
    await async_eventbus.provide_resource("prov.receive", handle, 50)
    result = await async_eventbus.rpc_client("example.rpc", "prov.receive", ["hi"])
    assert future.done()
    assert future.result() == expected_result
    assert result == b"hello"
    #await sleep(3)
    
