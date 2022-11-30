from typing import Optional, Dict, Any


class Options:
    def __init__(
        self,
        queue_name: str,
        rpc_queue_name: str,
        rpc_exchange_name: str,
        login: str = "guest",
        passwd: str = "guest",
        domain: str = "localhost",
        port: int = 5672,
        vhost: str = "/",
        heartbeat: Optional[int] = 0,
        **kwargs: Dict[str, Any]
    ) -> None:
        self.queue_name = queue_name
        self.rpc_queue_name = rpc_queue_name
        self.rpc_exchange_name = rpc_exchange_name
        self.login = login
        self.passwd = passwd
        self.domain = domain
        self.port = port
        self.vhost = vhost
        self.heartbeat = heartbeat
        self.kwargs = kwargs
