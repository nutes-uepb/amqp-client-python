import pytest
from amqp_client_python import AsyncEventbusRabbitMQ, ConnectionType
from amqp_client_python.signals import Event
from amqp_client_python.event import IntegrationEvent
from asyncio import Future, BaseEventLoop, wait_for


@pytest.mark.asyncio_cooperative
async def test_signal_connected(async_eventbus: AsyncEventbusRabbitMQ, loop: BaseEventLoop):
    future = Future(loop = loop)
    expected_result = "connected"
    async def handle(body):
        return "hello"
    @async_eventbus.on(Event.CONNECTED, ConnectionType.RPC_SERVER)
    async def connected():
        future.set_result(expected_result)
    await async_eventbus.provide_resource("prov.receive", handle, 50)
    result = await wait_for(future, 5)
    assert future.done()
    assert result == expected_result

@pytest.mark.asyncio_cooperative
async def test_signal_channel_openned(async_eventbus: AsyncEventbusRabbitMQ, loop: BaseEventLoop):
    future = Future(loop = loop)
    expected_result = "openned"
    async def handle(body):
        return "hello"
    @async_eventbus.on(Event.CHANNEL_OPENNED, ConnectionType.RPC_SERVER)
    async def connected():
        future.set_result(expected_result)
    await async_eventbus.provide_resource("prov.receive", handle, 50)
    result = await wait_for(future, 5)
    assert future.done()
    assert result == expected_result
    
