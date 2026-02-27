from amqp_client_python import EventbusWrapperRabbitMQ, Config, Options
from examples.default import queue, rpc_queue, rpc_exchange, rpc_routing_key


config = Config(Options(queue, rpc_queue, rpc_exchange))
eventbus = EventbusWrapperRabbitMQ(config=config)


print(eventbus.publish(rpc_exchange, rpc_routing_key, "direct").result())
# run this example with subscribe.py to see the complete cicle of sending and receiving messages.
