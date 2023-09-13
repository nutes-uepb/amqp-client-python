# DEPRECATED EVENTBUS
from amqp_client_python import (
    EventbusRabbitMQ,
    Config, Options,
    SSLOptions
)
from examples.default import (queue, rpc_queue, rpc_exchange, rpc_routing_key,
    certfile_path, keyfile_path, ca_certs_path
)
from dependency_injector import containers, providers
from multiprocessing import Process


class EventBusContainer(containers.DeclarativeContainer):

    eventbus_ssl_options = providers.Singleton(
        SSLOptions,
        certfile_path=certfile_path,
        keyfile_path=keyfile_path,
        ca_certs_path=ca_certs_path,
    )

    eventbus_options = providers.Singleton(
        Options,
        queue_name=queue,
        rpc_queue_name=rpc_queue,
        rpc_exchange_name=rpc_exchange
    )

    eventbus_config = providers.Singleton(
        Config,
        options=eventbus_options,
        # ssl_options=eventbus_ssl_options
    )
    eventbus = providers.Singleton(
        EventbusRabbitMQ,
        config=eventbus_config
    )

eventbus = EventBusContainer.eventbus
class Manager:
    def __init__(self, eventbus: EventbusRabbitMQ):
        self.eventbus = eventbus

    def handle(self, body):
        print(body)
        return "result"

    def start(self):
        self.eventbus.provide_resource(rpc_routing_key, self.handle)

class ManagerContainer(containers.DeclarativeContainer):
    eventbus = providers.Container(EventBusContainer)

    manager = providers.Singleton(
        Manager,
        eventbus.eventbus
    )

class Application(containers.DeclarativeContainer):
    config = providers.Configuration()

    manager = providers.Container(ManagerContainer)


app = Application()

def start():
    print(f"-------------- Starting [ manager ] Process -------")
    app.manager.manager().start()

p = Process(target=start)
p.start()