import pytest
from amqp_client_python import AsyncEventbusRabbitMQ, ConnectionType
from amqp_client_python.signals import Event
from asyncio import Future, BaseEventLoop, wait_for


@pytest.mark.asyncio_cooperative
async def test_signal_connected(async_eventbus: AsyncEventbusRabbitMQ, loop: BaseEventLoop):
    future = Future(loop = loop)
    expected_result = "connected"
    async def handle(body):
        return "hello"
    @async_eventbus.on(Event.CONNECTED, ConnectionType.RPC_SERVER)
    async def connected():
        if not future.done():
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
        if not future.done():
            future.set_result(expected_result)
    await async_eventbus.provide_resource("prov.receive", handle, 50)
    result = await wait_for(future, 5)
    assert future.done()
    assert result == expected_result

@pytest.mark.asyncio_cooperative
async def test_two_signals_channel_openned(async_eventbus: AsyncEventbusRabbitMQ, loop: BaseEventLoop):
    future_1 = Future(loop = loop)
    future_2 = Future(loop = loop)
    expected_result = "openned"
    async def handle(body):
        return "hello"
    @async_eventbus.on(Event.CHANNEL_OPENNED, ConnectionType.RPC_SERVER)
    async def connected():
        if not future_1.done():
            future_1.set_result(expected_result)
    @async_eventbus.on(Event.CHANNEL_OPENNED, ConnectionType.RPC_SERVER)
    async def connected2():
        if not future_2.done():
            future_2.set_result(expected_result)
    await async_eventbus.provide_resource("prov.receive", handle, 50)
    result_1 = await wait_for(future_1, 5)
    assert future_1.done()
    assert result_1 == expected_result
    result_2 = await wait_for(future_2, 5)
    assert future_2.done()
    assert result_2 == expected_result
