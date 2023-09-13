import pytest
from amqp_client_python import EventbusWrapperRabbitMQ
from asyncio import Future, BaseEventLoop, sleep


@pytest.mark.asyncio_cooperative
async def test_provider(eventbus_wrapper: EventbusWrapperRabbitMQ, loop: BaseEventLoop):
    expected_result = "received message"
    future = Future(loop = loop)
    async def handle(body):
        if not future.done():
            future.set_result(expected_result)
        return "hello"
    eventbus_wrapper.provide_resource("prov.receive", handle, 50).result()
    result = eventbus_wrapper.rpc_client("example.rpc", "prov.receive", ["hi"]).result()
    assert future.done()
    assert future.result() == expected_result
    assert result == b"hello"
    await sleep(1)
