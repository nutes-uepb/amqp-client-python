from typing import Optional, Dict, Any


class Options:
    def __init__(
        self,
        queue_name: str,
        rpc_queue_name: str,
        rpc_exchange_name: str,
        uri: Optional[str] = None,
        login: str = "guest",
        passwd: str = "guest",
        domain: str = "localhost",
        port: Optional[int] = None,
        vhost: str = "/",
        heartbeat: Optional[int] = 60,
        publisher_confirms: bool = False,
        **kwargs: Dict[str, Any]
    ) -> None:
        """
        Create an Options object that hold the credentials and configs options.

        Args:
            queue_name: name of queue that will be used for subscriptions
            rpc_queue_name: name of queue that will be used for provide resources
            rpc_exchange_name: name of exchange that will be used for provide resources
            uri: uri for connection
            login: username
            passwd: password
            domain: domain
            port: port information
            vhost: vhost information
            heartbeat: interval between heartbeat
            publisher_confirms: wait for publisher confirmations
            **kwargs: pika options

        Returns:

        Raises:

        Examples:
            >>> Options("example", "example.rpc", "example.rpc", "amqp://admin:admin@localhost:5672/")

            >>> Options("example", "example.rpc", "example.rpc", "amqps://admin:admin@localhost:5671/")

            >>> Options("example", "example.rpc", "example.rpc", login="admin", passwd="admin",
                    domain="localhost", port=5672)

            >>> Options("example", "example.rpc", "example.rpc", login="admin", passwd="admin",
                    domain="localhost", port=5671)
        """
        self.queue_name = queue_name
        self.rpc_queue_name = rpc_queue_name
        self.rpc_exchange_name = rpc_exchange_name
        self.uri = uri
        self.login = login
        self.passwd = passwd
        self.domain = domain
        self.port = port
        self.vhost = vhost
        self.heartbeat = heartbeat
        self.publisher_confirms = publisher_confirms
        self.kwargs = kwargs
