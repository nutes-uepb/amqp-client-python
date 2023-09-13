import pytest
from amqp_client_python import EventbusWrapperRabbitMQ, ConnectionType
from amqp_client_python.signals import Event
from asyncio import Future, BaseEventLoop, sleep


@pytest.mark.asyncio_cooperative
async def test_ssl(eventbus_wrapper_ssl: EventbusWrapperRabbitMQ, loop: BaseEventLoop):
    future = Future(loop = loop)
    expected_result = "result"
    async def handle(body):
        return "hello"
    @eventbus_wrapper_ssl.on(Event.CONNECTED, ConnectionType.RPC_SERVER)
    async def connected():
        if not future.done():
            future.set_result(expected_result)
    eventbus_wrapper_ssl.provide_resource("prov.receive", handle, 50).result()
    assert future.done()
    assert future.result() == expected_result
    await sleep(1)
    
    
