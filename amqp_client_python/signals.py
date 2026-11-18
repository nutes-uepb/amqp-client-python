import inspect
from typing import Callable, Union, Any, Dict, List
from enum import Enum


class Event(str, Enum):
    CONNECTED = "connected"
    CHANNEL_OPENNED = "channel_openned"


class Signal:
    def __init__(self):
        self.events: Dict[str, Dict[Any, List[Callable]]] = {}

    def on(self, event: Union[Event, str], condiction=None):
        try:
            event_obj = Event(event)
            event_key = event_obj.value

            def wrapper(callback: Callable):
                cond_key = getattr(condiction, "value", condiction)
                if event_key not in self.events:
                    self.events[event_key] = {}
                if cond_key not in self.events[event_key]:
                    self.events[event_key][cond_key] = []
                self.events[event_key][cond_key].append(callback)
                return callback

            return wrapper
        except ValueError:
            raise Exception("event not listed in events")

    def emmit(self, event: Union[Event, str], condiction=None, loop=None):
        event_key = getattr(event, "value", str(event))
        cond_key = getattr(condiction, "value", condiction)

        if event_key in self.events:
            callbacks = self.events[event_key].get(cond_key, [])
            results = []
            for callback in callbacks:
                if loop is not None:
                    if inspect.iscoroutinefunction(callback):
                        results.append(loop.create_task(callback()))
                    else:
                        res = callback()
                        if inspect.iscoroutine(res):
                            results.append(loop.create_task(res))
                        else:
                            results.append(res)
                else:
                    results.append(callback())
            return results

    def dispose(self):
        self.events = {}
