from enum import Enum


class Event(Enum):
    CONNECTED = "connected"
    CHANNEL_OPENNED = "channel_openned"


class Signal:
    events = {}

    @classmethod
    def on(
        cls,
        event: str,
        condiction=None
    ):
        try:
            Event(event)

            def wrapper(callback: callable):
                cls.events[event] = (callback, condiction)
            return wrapper
        except ValueError:
            raise Exception("event not listed in events")

    @classmethod
    def emmit(cls, event: str, condiction, loop):
        if event in cls.events:
            if cls.events[event][1] == condiction:
                loop.create_task(cls.events[event][0]())
