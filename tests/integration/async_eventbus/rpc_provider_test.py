import pytest
from amqp_client_python import AsyncEventbusRabbitMQ
from amqp_client_python.exceptions import AutoReconnectException, ResponseTimeoutException
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
    


@pytest.mark.asyncio_cooperative
async def test_provider_after_dispose(async_eventbus: AsyncEventbusRabbitMQ, loop: BaseEventLoop):
    expected_result = "received message"
    future = Future(loop = loop)
    async def handle(body):
        future.set_result(expected_result)
        return "hello"
    routing_key = str(uuid4())[:4]
    await async_eventbus.provide_resource(routing_key, handle, 50, connection_timeout=5)
    await async_eventbus.dispose(False)
    with pytest.raises((AutoReconnectException, ResponseTimeoutException)):
        await async_eventbus.rpc_client(async_eventbus.config.options.rpc_exchange_name, routing_key, ["hi"], timeout=5, connection_timeout=5)
    assert not future.done()

@pytest.mark.asyncio_cooperative
async def test_provider_after_dispose_and_restore(async_eventbus: AsyncEventbusRabbitMQ, loop: BaseEventLoop):
    expected_result = "received message"
    future = Future(loop = loop)
    async def handle(body):
        future.set_result(expected_result)
        return "hello"
    routing_key = str(uuid4())[:4]
    await async_eventbus.provide_resource(routing_key, handle, 50)
    await sleep(1)
    await async_eventbus.dispose(False)
    await async_eventbus.restore()
    result = await async_eventbus.rpc_client(async_eventbus.config.options.rpc_exchange_name, routing_key, ["hi"], timeout=20)
    assert future.done()
    assert future.result() == expected_result
    assert result == b"hello"