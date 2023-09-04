from enum import Enum


class ConnectionType(Enum):
    PUBLISH = "publish"
    SUBSCRIBE = "subscribe"
    RPC_CLIENT = "rpc_client"
    RPC_SERVER = "rpc_server"
