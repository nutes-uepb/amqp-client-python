from amqp_client_python import Config, Options, SSLOptions
from pika import URLParameters


def test_url():
    user, passwd, host, port = "user", "passwd", "ipdomain", 1234
    config = Config(
        Options(
            "example",
            "rpc_queue",
            "rpc_exchange",
            f"amqp://{user}:{passwd}@{host}:{port}/",
        )
    )
    assert config.url is None
    config.build()
    config.url: URLParameters
    assert config.url is not None
    assert isinstance(config.url, URLParameters)
    assert config.url.host == host
    assert config.url.port == port
    assert config.url.credentials.username == user
    assert config.url.credentials.password == passwd


def test_ssl():
    config = Config(
        Options("example", "rpc_queue", "rpc_exchange"),
        SSLOptions(
            "./tests/unit/utils/rabbitmq_cert.pem",
            "./tests/unit/utils/rabbitmq_key.pem",
            "./tests/unit/utils/ca.pem",
        ),
    )
    assert config.ssl_options is not None
    config.build()
    assert config.url.ssl_options is not None
