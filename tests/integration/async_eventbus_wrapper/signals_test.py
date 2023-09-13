import pytest
from amqp_client_python import EventbusWrapperRabbitMQ, ConnectionType
from amqp_client_python.signals import Event
from asyncio import Future, BaseEventLoop, wait_for, get_running_loop


@pytest.mark.asyncio_cooperative
async def test_signal_connected(eventbus_wrapper: EventbusWrapperRabbitMQ):
    loop = get_running_loop()
    future = Future(loop = loop)
    expected_result = "connected"
    async def handle(body):
        return "hello"
    @eventbus_wrapper.on(Event.CONNECTED, ConnectionType.RPC_SERVER)
    async def connected():
        if not future.done():
            future.set_result(expected_result)
    eventbus_wrapper.provide_resource("prov.receive", handle, 50).result()
    result = await wait_for(future, 5)
    assert future.done()
    assert result == expected_result

@pytest.mark.asyncio_cooperative
async def test_signal_channel_openned(eventbus_wrapper: EventbusWrapperRabbitMQ):
    loop = get_running_loop()
    future = Future(loop = loop)
    expected_result = "openned"
    async def handle(body):
        return "hello"
    @eventbus_wrapper.on(Event.CHANNEL_OPENNED, ConnectionType.RPC_SERVER)
    async def connected():
        if not future.done():
            future.set_result(expected_result)
    eventbus_wrapper.provide_resource("prov.receive", handle, 50).result()
    result = await wait_for(future, 5)
    assert future.done()
    assert result == expected_result

@pytest.mark.asyncio_cooperative
async def test_two_signals_channel_openned(eventbus_wrapper: EventbusWrapperRabbitMQ):
    loop = get_running_loop()
    future_1 = Future(loop = loop)
    future_2 = Future(loop = loop)
    expected_result = "openned"
    async def handle(body):
        return "hello"
    @eventbus_wrapper.on(Event.CHANNEL_OPENNED, ConnectionType.RPC_SERVER)
    async def connected():
        if not future_1.done():
            future_1.set_result(expected_result)
    @eventbus_wrapper.on(Event.CHANNEL_OPENNED, ConnectionType.RPC_SERVER)
    async def connected2():
        if not future_2.done():
            future_2.set_result(expected_result)
    eventbus_wrapper.provide_resource("prov.receive", handle, 50).result()
    result_1 = await wait_for(future_1, 5)
    assert future_1.done()
    assert result_1 == expected_result
    result_2 = await wait_for(future_2, 5)
    assert future_2.done()
    assert result_2 == expected_result
