from typing import MutableMapping, Dict, List
import asyncio
import logging
import uvloop
import aio_pika
from aio_pika import Message
from aio_pika.abc import (
    AbstractRobustConnection,
    AbstractRobustChannel,
    AbstractIncomingMessage,
    AbstractRobustExchange,
)
from uuid import uuid4
from json import loads, dumps
from functools import partial
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
queue = "isso"
rpc_queue = "isso.rpc"
exchange = "pq.rpc"
routing_key="sw.find"
from amqp_client_python import EventbusRabbitMQ, Config, Options
config = Config(Options(queue, rpc_queue, exchange))
loop = uvloop.new_event_loop()
asyncio.set_event_loop(loop)
eventbus = EventbusRabbitMQ(config, loop)

async def handle(*body):
    print(body, "rpc_1")
    print("rpc_2: ", await eventbus.rpc_client(exchange, routing_key+"2", ["oiii"]))
    return b"result0000"
async def handle3(*body):
    print(body)
    return b"result1111"


async def handle2(*body):
    print("subscribe", body)

async def p_serve():
    try:
        await eventbus.provide_resource(exchange, routing_key+"1", handle)
        await eventbus.provide_resource(exchange, routing_key+"2", handle3)
        await eventbus.subscribe(exchange, routing_key, handle2)
        
    except Exception as err:
        print(err)
    while True:
        print("result:", await eventbus.rpc_client(exchange, routing_key+"1", ["oiii"]))
        print("result:", await eventbus.publish(exchange, routing_key, ["oiii"]))
        
#loop.create_task(s_serve())
loop.create_task(p_serve())
#loop.create_task(e_publish())

if __name__ == "__main__":
    loop.run_forever()