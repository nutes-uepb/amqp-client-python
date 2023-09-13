from typing import Union, List, Any
from abc import ABC, abstractmethod


class ProviderHandler(ABC):

    @abstractmethod
    def handle(self, body: List[Any]) -> Union[bytes, str]:
        raise NotImplementedError
