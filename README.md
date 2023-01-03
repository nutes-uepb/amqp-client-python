# AMQP Client Python

[![License][license-image]][license-url]
<a href="https://pypi.org/project/amqp-client-python" target="_blank">
    <img src="https://img.shields.io/pypi/v/amqp-client-python?color=%2334D058&label=pypi%20package" alt="Package version">
</a><a href="https://pypi.org/project/amqp-client-python" target="_blank">
    <img src="https://img.shields.io/pypi/pyversions/amqp-client-python.svg?color=%2334D058" alt="Supported Python versions">
</a>
[![Vulnerabilities][known-vulnerabilities-image]][known-vulnerabilities-url]  [![Releases][releases-image]][releases-url] 




--------
Client with high level of abstraction for manipulation of messages in the event bus RabbitMQ.

### Features:
- Automatic creation and management of queues, exchanges and channels;
- Support for **direct**, **topic** and **fanout** exchanges;
- Publish;
- Subscribe;
- Support for a Remote procedure call _(RPC)_.


[//]: # (These are reference links used in the body of this note.)
[license-image]: https://img.shields.io/badge/license-Apache%202-blue.svg
[license-url]: https://github.com/nutes-uepb/amqp-client-python/blob/master/LICENSE
[npm-image]: https://img.shields.io/npm/v/amqp-client-python.svg?color=red&logo=npm
[npm-url]: https://npmjs.org/package/amqp-client-python
[downloads-image]: https://img.shields.io/npm/dt/amqp-client-python.svg?logo=npm
[travis-url]: https://travis-ci.org/nutes-uepb/amqp-client-python
[coverage-image]: https://coveralls.io/repos/github/nutes-uepb/amqp-client-python/badge.svg
[coverage-url]: https://coveralls.io/github/nutes-uepb/amqp-client-python?branch=master
[known-vulnerabilities-image]: https://snyk.io/test/github/nutes-uepb/amqp-client-python/badge.svg?targetFile=package.json
[known-vulnerabilities-url]: https://snyk.io/test/github/nutes-uepb/amqp-client-python?targetFile=package.json
[releases-image]: https://img.shields.io/github/release-date/nutes-uepb/amqp-client-python.svg
[releases-url]: https://github.com/nutes-uepb/amqp-client-python/releases

### Examples:
    ```Python
    # basic configuration
    from amqp_client_python import (
        AsyncEventbusRabbitMQ,
        Config, Options
    )
    from amqp_client_python.event import IntegrationEvent, IntegrationEventHandler
    
    config = Config(Options("queue", "rpc_queue", "rpc_exchange"))
    eventbus = AsyncEventbusRabbitMQ(config)
    # publish
    class ExampleEvent(IntegrationEvent):
        EVENT_NAME: str = "ExampleEvent"
        def __init__(self, event_type: str, message = []) -> None:
            super().__init__(self.EVENT_NAME, event_type)
            self.message = message

    publish_event = ExampleEvent(rpc_exchange, ["message"])
    eventbus.publish(publish_event, rpc_routing_key, "direct")
    # subscribe
    class ExampleEventHandler(IntegrationEventHandler):
        def handle(self, body) -> None:
            print(body) # handle messages
    await eventbus.subscribe(subscribe_event, subscribe_event_handle, rpc_routing_key)
    # rpc_publish
    response = await eventbus.rpc_client(rpc_exchange, "user.find", ["content_message"])
    # provider
    async def handle2(*body) -> bytes:
        print(f"body: {body}")
        return b"content"
    await eventbus.provide_resource("user.find", handle)
    ```