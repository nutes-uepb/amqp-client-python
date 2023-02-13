from pika import SelectConnection, URLParameters


class ConnectionFactoryRabbitMQ:
    """Create instance of Event Bus
    *
    * @param uri This specification defines an "amqp" URI scheme.
    * @param options {IEventBusOptions} Connection setup Options.
    * @return Promise<Connection>
    */
    """

    def __init__(self) -> None:
        self.connection = None

    def create_connection(
        self,
        uri: URLParameters,
        on_connection_open: callable,
        on_connection_open_error: callable,
        on_connection_closed: callable,
        custum_ioloop=None,
    ):
        if self.connection and self.connection.is_open:
            return self.connection
        self.connection = SelectConnection(
            uri,
            on_open_callback=on_connection_open,
            on_open_error_callback=on_connection_open_error,
            on_close_callback=on_connection_closed,
            custom_ioloop=custum_ioloop,
        )
        return self.connection
