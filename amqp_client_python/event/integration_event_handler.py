from abc import ABC, abstractmethod


class IntegrationEventHandler(ABC):

    @abstractmethod
    def handle(self, body) -> None:
        raise NotImplementedError
