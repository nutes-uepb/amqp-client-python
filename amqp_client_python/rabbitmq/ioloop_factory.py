from pika.adapters.select_connection import IOLoop
from time import time


class IOLoopFactory:
    ioloop = IOLoop()
    last_creation = time()
    running = False
    _reconnection_list = []

    @classmethod
    def get_ioloop(cls):
        return cls.ioloop

    @classmethod
    def reset(cls):
        cls.last_creation = time()
        cls.running = False
        cls.ioloop.stop()
        cls.ioloop = IOLoop()
        cls._reconnect()
        cls.start()

    @classmethod
    def start(cls):
        if not cls.running:
            cls.running = True
            cls.ioloop.start()

    @classmethod
    def add_reconnection(cls, call):
        cls._reconnection_list.append(call)

    @classmethod
    def _reconnect(cls):
        [reconnect() for reconnect in cls._reconnection_list]
