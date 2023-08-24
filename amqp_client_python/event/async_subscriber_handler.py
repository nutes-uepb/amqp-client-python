from typing import List, Any
from abc import ABC, abstractmethod


class AsyncSubscriberHandler(ABC):

    @abstractmethod
    async def handle(self, body: List[Any]) -> None:
        raise NotImplementedError
