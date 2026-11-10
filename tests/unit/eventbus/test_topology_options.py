import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from asyncio import get_event_loop
from amqp_client_python.domain.models import Options, Config
from amqp_client_python.rabbitmq import AsyncEventbusRabbitMQ, AsyncConnection, AsyncChannel
from tests.unit.eventbus.default import async_add_callback


def test_options_defaults_and_customization():
    """Verify Options default topology matches SSM standards and supports customization."""
    # Default behavior
    opt_default = Options("q", "rpc_q", "rpc_ex")
    assert opt_default.rpc_exchange_type == "direct"
    assert opt_default.rpc_queue_durable is True
    assert opt_default.rpc_queue_auto_delete is False
    assert opt_default.exchange_type == "topic"
    assert opt_default.queue_durable is True
    assert opt_default.queue_auto_delete is False

    # Custom behavior
    opt_custom = Options(
        "q", "rpc_q", "rpc_ex",
        rpc_exchange_type="topic",
        rpc_queue_durable=False,
        rpc_queue_auto_delete=True,
        exchange_type="direct",
        queue_durable=False,
        queue_auto_delete=True
    )
    assert opt_custom.rpc_exchange_type == "topic"
    assert opt_custom.rpc_queue_durable is False
    assert opt_custom.rpc_queue_auto_delete is True
    assert opt_custom.exchange_type == "direct"
    assert opt_custom.queue_durable is False
    assert opt_custom.queue_auto_delete is True


@pytest.mark.asyncio_cooperative
async def test_async_eventbus_provide_resource_forwards_custom_rpc_exchange_type():
    """Verify provide_resource forwards rpc_exchange_type from Options to connection."""
    options = Options("q", "rpc_q", "rpc_ex", rpc_exchange_type="topic", rpc_queue_durable=False)
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
        durable=False,
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

    # Verify backup contains the topology fields
    assert "test_key" in conn.backup["rpc_subscribe"]
    backup_entry = conn.backup["rpc_subscribe"]["test_key"]
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
