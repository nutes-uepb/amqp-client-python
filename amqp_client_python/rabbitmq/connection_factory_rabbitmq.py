from amqp_client_python.domain.models import Options, SSLOptions
from aio_pika import connect_robust
from aio_pika.abc import AbstractRobustConnection, SSLOptions as SSLOpt
import ssl

class ConnectionFactoryRabbitMQ:

    def __init__(self):
        self.connection = None
        self.queue = {}

    async def create_connection(self, options: Options, ssl_options: SSLOptions, loop=None) -> AbstractRobustConnection:
        if self.connection and self.connection.is_open:
            return self.connection
        self.connection = await connect_robust(
            host=options.domain, port=options.port, login=options.login, password=options.passwd,
            virtualhost=options.vhost, ssl=ssl_options.ssl, ssl_options=ssl_options.ssl and SSLOpt(
                cafile=ssl_options.ca_certs_path,
                certfile=ssl_options.certfile_path,
                keyfile=ssl_options.keyfile_path,
                no_verify_ssl=ssl.CERT_REQUIRED,
            ),
            loop=loop, timeout=options.timeout
        )
        return self.connection