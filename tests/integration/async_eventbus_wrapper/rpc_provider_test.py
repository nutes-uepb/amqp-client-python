import pytest
from amqp_client_python import EventbusWrapperRabbitMQ
from asyncio import Future, BaseEventLoop, sleep
from uuid import uuid4


@pytest.mark.asyncio_cooperative
async def test_provider(eventbus_wrapper: EventbusWrapperRabbitMQ, loop: BaseEventLoop):
    expected_result = "received message"
    future = Future(loop = loop)
    async def handle(body):
        if not future.done():
            future.set_result(expected_result)
        return "hello"
    routing_key = str(uuid4())[:4]
    eventbus_wrapper.provide_resource(routing_key, handle, 50).result()
    await sleep(1)
    result = eventbus_wrapper.rpc_client(eventbus_wrapper._async_eventbus.config.options.rpc_exchange_name, routing_key, ["hi"]).result()
    assert future.done()
    assert future.result() == expected_result
    assert result == b"hello"
