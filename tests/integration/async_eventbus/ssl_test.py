import pytest
from amqp_client_python import AsyncEventbusRabbitMQ, ConnectionType
from amqp_client_python.signals import Event
from asyncio import Future, BaseEventLoop, sleep


@pytest.mark.asyncio_cooperative
async def test_ssl(async_eventbus_ssl: AsyncEventbusRabbitMQ, loop: BaseEventLoop):
    future = Future(loop = loop)
    expected_result = "result"
    async def handle(body):
        return "hello"
    @async_eventbus_ssl.on(Event.CONNECTED, ConnectionType.RPC_SERVER)
    async def connected():
        if not future.done():
            future.set_result(expected_result)
    await async_eventbus_ssl.provide_resource("prov.receive", handle, 50)
    assert future.done()
    assert future.result() == expected_result
    await sleep(1)
    
    
