from typing import Union, List, Any
from abc import ABC, abstractmethod


class AsyncProviderHandler(ABC):

    @abstractmethod
    async def handle(self, body: List[Any]) -> Union[bytes, str]:
        raise NotImplementedError
