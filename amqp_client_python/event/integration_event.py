from typing import List, Any


class IntegrationEvent:
    def __init__(
        self, event_name: str, event_type: str, message: List[Any] = []
    ) -> None:
        self.event_name = event_name
        self.event_type = event_type
        self.message = message
