from typing import List, Any
from abc import ABC, abstractmethod


class SubscriberHandler(ABC):

    @abstractmethod
    def handle(self, body: List[Any]) -> None:
        raise NotImplementedError
