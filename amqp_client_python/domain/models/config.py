from typing import Optional
from pika import URLParameters
from .options import Options
from .ssl_options import SSLOptions
from urllib.parse import urlencode


class Config:
    def __init__(self,
        options: Options,
        ssl_options: Optional[SSLOptions] = None
    ) -> None:
        self.options = options
        self.ssl_options = ssl_options

    def build(self):
        opt = {
            **self.options.kwargs,
            "heartbeat": self.options.heartbeat,
            "ssl_options": None if not self.ssl_options else {
            'certfile': self.ssl_options.ca_certs_path,
            'keyfile': self.ssl_options.keyfile_path,
                'ca_certs': self.ssl_options.ca_certs_path
            }
        }
        protocol = "amqps" if bool(self.ssl_options) else "amqp"
        self.url = URLParameters(f"{protocol}://{self.options.domain}:{self.options.port}/%2F?{urlencode(opt)}")
        return self


