from typing import TypedDict, Optional, Callable


class HandlerType(TypedDict):
    response_timeout: Optional[int]
    handle: Callable
    content_type: str
