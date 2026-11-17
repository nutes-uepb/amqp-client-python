import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from asyncio import get_event_loop
from amqp_client_python.domain.models import Options, Config
from amqp_client_python.rabbitmq import AsyncEventbusRabbitMQ, AsyncConnection, AsyncChannel
from tests.unit.eventbus.default import async_add_callback


def test_options_defaults_and_customization():
    """Verify Options default topology matches standard defaults and supports customization."""
    # Default behavior
    opt_default = Options("q", "rpc_q", "rpc_ex")
    assert opt_default.rpc_exchange_type == "topic"
    assert opt_default.rpc_queue_durable is True
    assert opt_default.rpc_queue_auto_delete is False
    assert opt_default.exchange_type == "topic"
    assert opt_default.queue_durable is True
    assert opt_default.queue_auto_delete is False

    # Custom behavior
    opt_custom = Options(
        "q", "rpc_q", "rpc_ex",
        rpc_exchange_type="direct",
        rpc_queue_durable=False,
        rpc_queue_auto_delete=True,
        exchange_type="direct",
        queue_durable=False,
        queue_auto_delete=True
    )
    assert opt_custom.rpc_exchange_type == "direct"
    assert opt_custom.rpc_queue_durable is False
    assert opt_custom.rpc_queue_auto_delete is True
    assert opt_custom.exchange_type == "direct"
    assert opt_custom.queue_durable is False
    assert opt_custom.queue_auto_delete is True


@pytest.mark.asyncio_cooperative
async def test_async_eventbus_provide_resource_forwards_custom_rpc_exchange_type():
    """Verify provide_resource forwards rpc_exchange_type from Options to connection."""
    options = Options("q", "rpc_q", "rpc_ex", rpc_exchange_type="direct", rpc_queue_durable=False)
    config = Config(options)
    eventbus = AsyncEventbusRabbitMQ(config)

    mock_connection = AsyncMock(AsyncConnection)
    mock_connection.add_callback = async_add_callback
    eventbus._rpc_server_connection = mock_connection

    async def handle(*body):
        return b"ok"

    await eventbus.provide_resource("test.route", handle)

    mock_connection.rpc_subscribe.assert_called_once_with(
        "rpc_q",
        "rpc_ex",
        "test.route",
        handle,
        None,
        exchange_type="direct",
        durable=False,
        auto_delete=False,
    )


@pytest.mark.asyncio_cooperative
async def test_async_eventbus_provide_resource_defaults_to_topic():
    """Verify provide_resource defaults rpc_exchange_type to topic."""
    options = Options("q", "rpc_q", "rpc_ex")
    config = Config(options)
    eventbus = AsyncEventbusRabbitMQ(config)

    mock_connection = AsyncMock(AsyncConnection)
    mock_connection.add_callback = async_add_callback
    eventbus._rpc_server_connection = mock_connection

    async def handle(*body):
        return b"ok"

    await eventbus.provide_resource("test.route", handle)

    mock_connection.rpc_subscribe.assert_called_once_with(
        "rpc_q",
        "rpc_ex",
        "test.route",
        handle,
        None,
        exchange_type="topic",
        durable=True,
        auto_delete=False,
    )


@pytest.mark.asyncio_cooperative
async def test_async_connection_backup_preserves_topology_on_recovery():
    """Verify AsyncConnection preserves exchange_type and durable across auto-recovery."""
    loop = get_event_loop()
    conn = AsyncConnection(ioloop=loop)

    mock_channel = AsyncMock(AsyncChannel)
    conn._channel = mock_channel

    mock_callback = AsyncMock()

    # Call rpc_subscribe with custom exchange_type
    await conn.rpc_subscribe(
        "rpc_q", "rpc_ex", "test_key", mock_callback, 10,
        exchange_type="direct", durable=True, auto_delete=False
    )

    # Verify backup contains the topology fields indexed by (queue_name, routing_key)
    assert ("rpc_q", "test_key") in conn.backup["rpc_subscribe"]
    backup_entry = conn.backup["rpc_subscribe"][("rpc_q", "test_key")]
    assert backup_entry["exchange_type"] == "direct"
    assert backup_entry["durable"] is True
    assert backup_entry["auto_delete"] is False

    # Simulate connection recovery
    conn.reconnecting = True
    mock_connection = MagicMock()
    mock_connection.ioloop = loop
    conn.connection_factory.create_connection = MagicMock(return_value=mock_connection)

    # When on_connection_open runs, mock channel.open to keep mock_channel as _channel
    with patch.object(AsyncChannel, "open"):
        conn.on_connection_open(mock_connection)
        assert len(conn.callbacks) == 1
        recovery_cb, _ = conn.callbacks[0]
        # Replace the newly created channel with our mock to verify rpc_subscribe call
        conn._channel = mock_channel
        await recovery_cb()

    # Verify mock_channel.rpc_subscribe was called during recovery with exchange_type="direct"
    last_call = mock_channel.rpc_subscribe.call_args
    assert last_call.kwargs["exchange_type"] == "direct"
    assert last_call.kwargs["durable"] is True
    assert last_call.kwargs["auto_delete"] is False


def test_async_channel_setup_exchange_caches_redundant_declarations():
    """Verify setup_exchange avoids duplicate declarations, ignores empty names, and clears on close."""
    channel = AsyncChannel()
    mock_pika_channel = MagicMock()
    channel._channel = mock_pika_channel

    # Empty exchange name should be ignored (RabbitMQ default exchange cannot be declared)
    channel.setup_exchange("", "direct", durable=True)
    assert mock_pika_channel.exchange_declare.call_count == 0

    # First declaration of test_ex
    channel.setup_exchange("test_ex", "direct", durable=True)
    assert mock_pika_channel.exchange_declare.call_count == 1

    # Second call with identical settings should be a no-op (cached)
    channel.setup_exchange("test_ex", "direct", durable=True)
    assert mock_pika_channel.exchange_declare.call_count == 1

    # Call with different exchange should declare
    channel.setup_exchange("other_ex", "topic", durable=True)
    assert mock_pika_channel.exchange_declare.call_count == 2

    # Call with different settings for existing exchange should warn and re-declare
    channel.setup_exchange("test_ex", "topic", durable=False)
    assert mock_pika_channel.exchange_declare.call_count == 3
    assert channel._declared_exchanges["test_ex"] == ("topic", False)

    # When channel closes, declared exchanges cache is cleared
    channel._connection = MagicMock()
    channel._connection.is_closing = True
    channel.on_channel_closed(mock_pika_channel, "simulated error")
    assert len(channel._declared_exchanges) == 0

    # After close, declaring test_ex again executes exchange_declare
    channel.setup_exchange("test_ex", "topic", durable=False)
    assert mock_pika_channel.exchange_declare.call_count == 4


@pytest.mark.asyncio_cooperative
async def test_async_connection_backup_supports_multiple_queues_same_routing_key():
    """Verify subscribing to the same routing_key across different queues retains all in backup."""
    loop = get_event_loop()
    conn = AsyncConnection(ioloop=loop)
    conn._channel = AsyncMock(AsyncChannel)

    mock_cb1 = AsyncMock()
    mock_cb2 = AsyncMock()

    await conn.subscribe("queue_alpha", "ex_test", "shared.key", mock_cb1, 10)
    await conn.subscribe("queue_beta", "ex_test", "shared.key", mock_cb2, 10)

    # Both subscriptions must exist in backup without overwriting each other
    assert ("queue_alpha", "shared.key") in conn.backup["subscribe"]
    assert ("queue_beta", "shared.key") in conn.backup["subscribe"]
    assert len(conn.backup["subscribe"]) == 2


@pytest.mark.asyncio_cooperative
async def test_async_channel_direct_exchange_bypasses_regex_matching():
    """Verify that queues on a direct exchange completely bypass regex matching on unrouted messages."""
    import asyncio
    loop = get_event_loop()
    channel = AsyncChannel(auto_ack=False)
    channel.ioloop = loop
    mock_pika_channel = MagicMock()
    mock_pika_channel.is_open = True
    channel._channel = mock_pika_channel

    channel.register_queue("ex_direct", "q_direct", exchange_type="direct")
    channel.register_handler("q_direct", "exact.key", AsyncMock(), "application/json", 5)

    # Manually add a pattern that would match in re_subscribes
    channel.re_subscribes.append("unmatched.*")

    deliver = MagicMock(routing_key="unmatched.item", delivery_tag=1)
    props = MagicMock(reply_to=None, correlation_id="c1")

    with patch("amqp_client_python.rabbitmq.async_channel.re.match") as mock_re_match:
        channel.on_message("q_direct", mock_pika_channel, deliver, props, b"{}")
        # Yield to let the created task run in loop
        await asyncio.sleep(0.01)

        # On direct exchange, regex matching must be completely bypassed
        mock_re_match.assert_not_called()
        mock_pika_channel.basic_nack.assert_called_once_with(1, requeue=False)


@pytest.mark.asyncio_cooperative
async def test_async_channel_topic_exchange_uses_compiled_patterns():
    """Verify that topic exchanges match both * and # wildcards via compiled patterns."""
    from asyncio import Future
    loop = get_event_loop()
    channel = AsyncChannel()
    channel.ioloop = loop
    mock_pika_channel = MagicMock()
    mock_pika_channel.is_open = True
    channel._channel = mock_pika_channel

    channel.register_queue("ex_topic", "q_topic", exchange_type="topic")

    fut_user = Future()
    fut_metric = Future()

    async def handle_user(body):
        fut_user.set_result(body)

    async def handle_metric(body):
        fut_metric.set_result(body)

    channel.register_handler("q_topic", "user.*", handle_user, "application/json", 5)
    channel.register_handler("q_topic", "metric.#", handle_metric, "application/json", 5)

    # Verify compiled patterns exist
    assert "q_topic" in channel._compiled_patterns
    patterns = [p[0] for p in channel._compiled_patterns["q_topic"]]
    assert "user.*" in patterns
    assert "metric.#" in patterns

    # Deliver message matching *
    deliver1 = MagicMock(routing_key="user.created", delivery_tag=1)
    props1 = MagicMock(reply_to=None, correlation_id="c1")
    channel.on_message("q_topic", mock_pika_channel, deliver1, props1, b'{"user": 1}')
    res1 = await fut_user
    assert res1 == {"user": 1}

    # Deliver message matching #
    deliver2 = MagicMock(routing_key="metric.cpu.usage.percent", delivery_tag=2)
    props2 = MagicMock(reply_to=None, correlation_id="c2")
    channel.on_message("q_topic", mock_pika_channel, deliver2, props2, b'{"cpu": 95}')
    res2 = await fut_metric
    assert res2 == {"cpu": 95}


@pytest.mark.asyncio_cooperative
async def test_async_channel_multi_queue_pattern_isolation():
    """Verify that a wildcard on Queue A does not trigger a KeyError or match on Queue B."""
    import asyncio
    loop = get_event_loop()
    channel = AsyncChannel(auto_ack=False)
    channel.ioloop = loop
    mock_pika_channel = MagicMock()
    mock_pika_channel.is_open = True
    channel._channel = mock_pika_channel

    channel.register_queue("ex", "q_alpha", exchange_type="topic")
    channel.register_queue("ex", "q_beta", exchange_type="topic")

    channel.register_handler("q_alpha", "orders.*", AsyncMock(), "application/json", 5)
    channel.register_handler("q_beta", "products.view", AsyncMock(), "application/json", 5)

    # Message matching Queue A's pattern is delivered to Queue B
    deliver = MagicMock(routing_key="orders.created", delivery_tag=42)
    props = MagicMock(reply_to=None, correlation_id="c3")

    channel.on_message("q_beta", mock_pika_channel, deliver, props, b"{}")
    # Let task execute
    await asyncio.sleep(0.01)

    # Queue B must safely NACK without crashing
    mock_pika_channel.basic_nack.assert_called_once_with(42, requeue=False)


def test_async_channel_register_queue_defaults_to_topic():
    """Verify AsyncChannel register_queue defaults to topic."""
    channel = AsyncChannel()
    channel.setup_exchange = MagicMock()
    channel.queue_declare = MagicMock()

    channel.register_queue("default_ex", "default_q")
    assert channel._queue_exchange_type["default_q"] == "topic"
    channel.setup_exchange.assert_called_once_with("default_ex", "topic", durable=True)
