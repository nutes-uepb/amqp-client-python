# AMQP Client Python

Client with high level of abstraction for manipulation of messages in the event bus RabbitMQ.

--------

[![License][license-image]][license-url]
<a href="https://pypi.org/project/amqp-client-python" target="_blank">
    <img src="https://img.shields.io/pypi/v/amqp-client-python?color=%2334D058&label=pypi%20package" alt="Package version">
</a><a href="https://pypi.org/project/amqp-client-python" target="_blank">
    <img src="https://img.shields.io/pypi/pyversions/amqp-client-python.svg?color=%2334D058" alt="Supported Python versions">
</a>
[![Downloads](https://static.pepy.tech/personalized-badge/amqp-client-python?period=month&units=international_system&left_color=black&right_color=orange&left_text=PyPI%20downloads%20per%20month)](https://pepy.tech/project/amqp-client-python)
[![Vulnerabilities][known-vulnerabilities-image]][known-vulnerabilities-url]  [![Releases][releases-image]][releases-url] 



---

**Documentation**: <a href="https://nutes-uepb.github.io/amqp-client-python" target="_blank">https://nutes-uepb.github.io/amqp-client-python</a>

**Source Code**: <a href="https://github.com/nutes-uepb/amqp-client-python" target="_blank">https://github.com/nutes-uepb/amqp-client-python</a>

**Discord Server**: <a href="https://discord.gg/RkXNeZpNZk" target="_blank">https://discord.gg/RkXNeZpNZk</a>

---
### Features:
- Automatic creation and management of queues, exchanges and channels;
- Connection persistence and auto reconnect;
- Support for **direct**, **topic** and **fanout** exchanges;
- Publish;
- Subscribe;
- Support for a Remote procedure call _(RPC)_.


### Table of Compatibility
| version  | compatible with |
| ---- | ---- |
| 0.2.0 | 0.2.0 |
| 0.1.14 | ~0.1.12 |

### Examples:
#### you can use [sync](https://github.com/nutes-uepb/amqp-client-python/blob/develop/amqp_client_python/rabbitmq/eventbus_rabbitmq.py) , [async eventbus](https://github.com/nutes-uepb/amqp-client-python/blob/develop/amqp_client_python/rabbitmq/async_eventbus_rabbitmq.py) and [sync wrapper](https://github.com/nutes-uepb/amqp-client-python/blob/develop/amqp_client_python/rabbitmq/eventbus_wrapper_rabbitmq.py) of async eventbus
<details><summary>async usage </summary>

<br>

```Python
# basic configuration
from amqp_client_python import (
    AsyncEventbusRabbitMQ,
    Config, Options
)
config = Config(Options("queue", "rpc_queue", "rpc_exchange"))
eventbus = AsyncEventbusRabbitMQ(config)
# publish

eventbus.publish("rpc_exchange", "routing.key", "message_content")
# subscribe
async def subscribe_handler(body) -> None:
    print(body, type(body), flush=True) # handle messages
await eventbus.subscribe("rpc_exchange", "routing.key", subscribe_handler)
# rpc_publish
response = await eventbus.rpc_client("rpc_exchange", "user.find", "message_content")
# provider
async def rpc_provider_handler(body) -> bytes:
    print(f"body: {body}")
    return b"content"
await eventbus.provide_resource("user.find", rpc_provider_handler)
```
</details>

<details><summary>sync usage(deprecated)</summary>

```Python
from amqp_client_python import (
    EventbusRabbitMQ,
    Config, Options
)
from amqp_client_python.event import IntegrationEvent, IntegrationEventHandler
from examples.default import queue, rpc_queue, rpc_exchange, rpc_routing_key


class ExampleEvent(IntegrationEvent):
    EVENT_NAME: str = "ExampleEvent"
    ROUTING_KEY: str = rpc_routing_key

    def __init__(self, event_type: str, message = []) -> None:
        super().__init__(self.EVENT_NAME, event_type)
        self.message = message
        self.routing_key = self.ROUTING_KEY


class ExampleEventHandler(IntegrationEventHandler):
    def handle(self, body) -> None:
        print(body,"subscribe")


config = Config(Options(queue, rpc_queue, rpc_exchange))
eventbus = EventbusRabbitMQ(config=config)

class ExampleEvent(IntegrationEvent):
    EVENT_NAME: str = "ExampleEvent"
    def __init__(self, event_type: str, message = []) -> None:
        super().__init__(self.EVENT_NAME, event_type)
        self.message = message

from time import sleep
from random import randint
def handle(*body):
    print(body[0], "rpc_provider")
    return f"{body[0]}".encode("utf-8")

subscribe_event = ExampleEvent(rpc_exchange)
publish_event = ExampleEvent(rpc_exchange, ["message"])
subscribe_event_handle = ExampleEventHandler()
eventbus.subscribe(subscribe_event, subscribe_event_handle, rpc_routing_key)
eventbus.provide_resource(rpc_routing_key+"2", handle)
count = 0
running = True
from concurrent.futures import TimeoutError
while running:
    try:
        count += 1
        if str(count) != eventbus.rpc_client(rpc_exchange, rpc_routing_key+"2", [f"{count}"]).decode("utf-8"):
            running = False
        #eventbus.publish(publish_event, rpc_routing_key, "message_content")
        #running = False
    except TimeoutError as err:
        print("timeout!!!: ", str(err))
    except KeyboardInterrupt:
        running=False
    except BaseException as err:
        print("Err:", err)
```
</details>

<details><summary>sync wrapper usage</summary>

```Python
from amqp_client_python import EventbusWrapperRabbitMQ, Config, Options

config = Config(Options("queue", "rpc_queue", "rpc_exchange"))
eventbus = EventbusWrapperRabbitMQ(config=config)

async def subscribe_handler(body) -> None:
    print(f"{body}", type(body), flush=True)

async def rpc_provider_handler(body) -> bytes:
    print(f"handle - {body}", type(body), flush=True)
    return f"{body}".encode("utf-8")

# rpc_provider
eventbus.provide_resource("user.find", rpc_provider_handler).result()
# subscribe
eventbus.subscribe("rpc_exchange", "routing.key", subscribe_handler).result()
count = 0
running = True
while running:
    try:
        count += 1
        # rpc_client call
        eventbus.rpc_client("rpc_exchange", "user.find", count).result().decode("utf-8")
        # publish
        eventbus.publish("rpc_exchange", "routing.key", "message_content").result()
        #running = False
    except KeyboardInterrupt:
        running=False
    except BaseException as err:
        print("Err:", err)
```
</details>
<br />


## Sponsors
The library is provided by NUTES-UEPB.
<br/>
<a href="https://nutes.uepb.edu.br/" target="_blank"><img width="250px" src="https://nutes.uepb.edu.br/wp-content/uploads/2018/11/cropped-logo-Nutes-Final.jpg"></a>

### Know Limitations:
#### basic eventbus
<medium><pre>
When using [**EventbusRabbitMQ**](https://github.com/nutes-uepb/amqp-client-python/blob/master/amqp_client_python/rabbitmq/eventbus_rabbitmq.py#L12) Should not use rpc call inside of rpc provider or subscribe handlers, it may block the ioloop
#/obs: fixed on other kinds of eventbus, will be removed on nexts releases
</pre></medium>



[//]: # (These are reference links used in the body of this note.)
[license-image]: https://img.shields.io/badge/license-Apache%202-blue.svg
[license-url]: https://github.com/nutes-uepb/amqp-client-python/blob/master/LICENSE
[npm-image]: https://img.shields.io/npm/v/amqp-client-python.svg?color=red&logo=npm
[npm-url]: https://npmjs.org/package/amqp-client-python
[downloads-image]: https://img.shields.io/npm/dt/amqp-client-python.svg?logo=npm
[travis-url]: https://travis-ci.org/nutes-uepb/amqp-client-python
[coverage-image]: https://coveralls.io/repos/github/nutes-uepb/amqp-client-python/badge.svg
[coverage-url]: https://coveralls.io/github/nutes-uepb/amqp-client-python?branch=master
[known-vulnerabilities-image]: https://snyk.io/test/github/nutes-uepb/amqp-client-python/badge.svg?targetFile=requirements.txt
[known-vulnerabilities-url]: https://snyk.io/test/github/nutes-uepb/amqp-client-python?targetFile=requirements.txt
[releases-image]: https://img.shields.io/github/release-date/nutes-uepb/amqp-client-python.svg
[releases-url]: https://github.com/nutes-uepb/amqp-client-python/releases