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
        rpc_exchange_type: str = "direct",
        rpc_queue_durable: bool = True,
        rpc_queue_auto_delete: bool = False,
        exchange_type: str = "topic",
        queue_durable: bool = True,
        queue_auto_delete: bool = False,
        **kwargs: Dict[str, Any]
    ) -> None:
        """
        Create an Options object that holds the credentials and configuration options.

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
            rpc_exchange_type: exchange type for RPC server (default 'direct')
            rpc_queue_durable: durability for RPC server queue (default True)
            rpc_queue_auto_delete: auto_delete for RPC server queue (default False)
            exchange_type: exchange type for pub/sub subscriptions (default 'topic')
            queue_durable: durability for pub/sub subscriptions queue (default True)
            queue_auto_delete: auto_delete for pub/sub subscriptions queue (default False)
            **kwargs: pika options

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
        self.rpc_exchange_type = kwargs.pop("rpc_exchange_type", rpc_exchange_type)
        self.rpc_queue_durable = kwargs.pop("rpc_queue_durable", rpc_queue_durable)
        self.rpc_queue_auto_delete = kwargs.pop("rpc_queue_auto_delete", rpc_queue_auto_delete)
        self.exchange_type = kwargs.pop("exchange_type", exchange_type)
        self.queue_durable = kwargs.pop("queue_durable", queue_durable)
        self.queue_auto_delete = kwargs.pop("queue_auto_delete", queue_auto_delete)
        self.kwargs = kwargs
