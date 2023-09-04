from enum import Enum


class Event(Enum):
    CONNECTED = "connected"
    CHANNEL_OPENNED = "channel_openned"


class Signal:
    def __init__(self):
        self.events = {}

    def on(
        self,
        event: str,
        condiction=None
    ):
        try:
            Event(event)

            def wrapper(callback: callable):
                if event in self.events:
                    if condiction in self.events[event]:
                        self.events[event][condiction].append(callback)
                    else:
                        self.events[event][condiction] = [callback]
                else:
                    self.events[event] = {condiction: [callback]}
            return wrapper
        except ValueError:
            raise Exception("event not listed in events")

    def emmit(self, event: str, condiction, loop=None):
        if event in self.events:
            if condiction in self.events[event]:
                if loop is None:
                    return [callback() for callback in self.events[event][condiction]]
                [loop.create_task(callback()) for callback in self.events[event][condiction]]

    def dispose(self):
        self.events = {}
