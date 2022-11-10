from dataclasses import dataclass
from pika import URLParameters

@dataclass
class Config:
    queue_name: str
    rpc_queue_name: str
    rpc_exchange_name: str
    url: URLParameters