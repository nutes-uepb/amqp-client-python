Learn how to use all AmqpClientPython features:

# 1. Basic Configuration

To set up the configuration for your connection, create a `Config` object. This object holds and manages the connection information.

## Example
```python
from amqp_client_python.domain.models import Config, Options, SSLOptions
```

## Configure without SSL
```python
config = Config(
    Options("example", "example.rpc", "example.rpc", "amqp://admin:admin@localhost:5672/")
)
```

## Configure with SSL
```python
ssl_options = SSLOptions("./.certs/cert.pem", "./.certs/privkey.pem", "./.certs/ca.pem")
config = Config(
    Options("example", "example.rpc", "example.rpc"),
    ssl_options=ssl_options
)
```

# 2. Publishing Messages
To publish messages, use the `publish` method of the `AsyncEventbusRabbitMQ` class.
## Example
```python
async_eventbus = AsyncEventbusRabbitMQ(config)

exchange_name = "example.rpc"
routing_key = "user.find3"
await async_eventbus.publish(exchange_name, routing_key, ["content_message"])
```

# 3. Subscribing to Queues
You can register a provider to listen on a queue using the `subscribe` method.
## Example
```python
async def handle(body) -> None:
    print(f"received message: {body}")
exchange_name = "example"
routing_key = "user.find3"
process_timeout = 20
await async_eventbus.subscribe(exchange_name, routing_key, handle, process_timeout)
```

# 4. Implementing RPC
Use the methods `rpc_client` and `provide_resource` for RPC communication.
## RPC Client Example
```python
exchange_name = "example.rpc"
routing_key = "example.find"
body = {"name": "example"}
content_type = "application/json"
response = await async_eventbus.rpc_client(
    exchange_name, routing_key, body, content_type
)
```

## RPC Provider Example
```python
async def rpc_provider_handler(body) -> Union[str, bytes]:
    print(f"do something with: {body}")
    return b"response" # json.dumps({"name": "example"})

routing_key = "example.find"
await async_eventbus.provide_resource(routing_key, rpc_provider_handler)
```
