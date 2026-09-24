import pytest
from amqp_client_python import AsyncEventbusRabbitMQ
from asyncio import Future, BaseEventLoop, sleep
from uuid import uuid4


@pytest.mark.asyncio_cooperative
async def test_rpc_provider_auto_recovery_on_connection_drop(async_eventbus: AsyncEventbusRabbitMQ, loop: BaseEventLoop):
    """
    Test that an RPC provider automatically recovers its consumers when the RabbitMQ connection is forcibly closed,
    allowing subsequent RPC calls to succeed without manual restarts.
    """
    expected_result = "response_after_recovery"
    future_count = 0

    async def handle(body):
        nonlocal future_count
        future_count += 1
        return expected_result

    routing_key = f"rk_recovery_{str(uuid4())[:8]}"
    
    # 1. Register RPC provider
    await async_eventbus.provide_resource(routing_key, handle, timeout=10)
    await sleep(1)

    # 2. First RPC request before disconnect
    res1 = await async_eventbus.rpc_client(
        async_eventbus.config.options.rpc_exchange_name,
        routing_key,
        ["request_1"],
        timeout=10,
    )
    assert res1 == expected_result.encode()
    assert future_count == 1

    # 3. Simulate sudden RabbitMQ connection drop by closing the underlying connection
    rpc_conn = async_eventbus._rpc_server_connection
    if rpc_conn._connection:
        rpc_conn._connection.close()

    # 4. Wait for auto-reconnection and consumer re-registration
    await sleep(3)

    # 5. Second RPC request after auto-recovery
    res2 = await async_eventbus.rpc_client(
        async_eventbus.config.options.rpc_exchange_name,
        routing_key,
        ["request_2"],
        timeout=10,
    )
    assert res2 == expected_result.encode()
    assert future_count == 2


@pytest.mark.asyncio_cooperative
async def test_subscribe_auto_recovery_on_connection_drop(async_eventbus: AsyncEventbusRabbitMQ, loop: BaseEventLoop):
    """
    Test that a pub/sub subscriber automatically recovers its consumers when the RabbitMQ connection is forcibly closed.
    """
    received_messages = []

    async def handle(body):
        received_messages.append(body)

    exchange_name = "ex_subscribe_recovery"
    routing_key = f"rk_sub_{str(uuid4())[:8]}"

    # 1. Register subscriber
    await async_eventbus.subscribe(exchange_name, routing_key, handle, timeout=10)
    await sleep(1)

    # 2. Publish message 1
    await async_eventbus.publish(exchange_name, routing_key, ["msg_1"])
    await sleep(1)
    assert len(received_messages) == 1

    # 3. Force connection drop on sub_connection
    sub_conn = async_eventbus._sub_connection
    if sub_conn._connection:
        sub_conn._connection.close()

    # 4. Wait for auto-reconnection
    await sleep(3)

    # 5. Publish message 2 after auto-recovery
    await async_eventbus.publish(exchange_name, routing_key, ["msg_2"])
    await sleep(1)
    assert len(received_messages) == 2
    assert received_messages == [["msg_1"], ["msg_2"]]


@pytest.mark.asyncio_cooperative
async def test_multiple_consecutive_drops_auto_recovery(async_eventbus: AsyncEventbusRabbitMQ, loop: BaseEventLoop):
    """
    Edge Case Test: Verify auto-recovery works reliably over multiple consecutive connection drops (network flapping).
    """
    call_count = 0

    async def handle(body):
        nonlocal call_count
        call_count += 1
        return f"resp_{call_count}"

    routing_key = f"rk_flapping_{str(uuid4())[:8]}"
    await async_eventbus.provide_resource(routing_key, handle, timeout=10)
    await sleep(1)

    # Perform 3 consecutive drops and verify recovery after each
    for i in range(1, 4):
        # Force close connection
        rpc_conn = async_eventbus._rpc_server_connection
        if rpc_conn._connection:
            rpc_conn._connection.close()

        # Wait for auto-recovery
        await sleep(3)

        # Make RPC call after recovery
        res = await async_eventbus.rpc_client(
            async_eventbus.config.options.rpc_exchange_name,
            routing_key,
            [f"req_{i}"],
            timeout=10,
        )
        assert res == f"resp_{i}".encode()

    assert call_count == 3


@pytest.mark.asyncio_cooperative
async def test_multiple_handlers_simultaneous_recovery(async_eventbus: AsyncEventbusRabbitMQ, loop: BaseEventLoop):
    """
    Edge Case Test: Verify that multiple RPC handlers registered on the same connection all recover concurrently without channel collision.
    """
    keys = [f"rk_multi_{i}_{str(uuid4())[:6]}" for i in range(3)]
    counts = {k: 0 for k in keys}

    def make_handler(k):
        async def handler(body):
            counts[k] += 1
            return f"ok_{k}"
        return handler

    # Register 3 handlers concurrently
    for k in keys:
        await async_eventbus.provide_resource(k, make_handler(k), timeout=10)
    await sleep(1)

    # Force connection drop
    rpc_conn = async_eventbus._rpc_server_connection
    if rpc_conn._connection:
        rpc_conn._connection.close()

    # Wait for auto-recovery
    await sleep(3)

    # Verify all 3 handlers recovered and respond correctly
    for k in keys:
        res = await async_eventbus.rpc_client(
            async_eventbus.config.options.rpc_exchange_name,
            k,
            ["payload"],
            timeout=10,
        )
        assert res == f"ok_{k}".encode()
        assert counts[k] == 1
