from typing import Optional
from pika import URLParameters
from .options import Options
from .ssl_options import SSLOptions
from urllib.parse import urlencode


class Config:
    def __init__(
        self, options: Options, ssl_options: Optional[SSLOptions] = None
    ) -> None:
        self.url = None
        self.options = options
        self.ssl_options = ssl_options

    def build(self):
        opt = {
            **self.options.kwargs,
            "heartbeat": self.options.heartbeat,
        }
        if bool(self.ssl_options):
            opt["ssl_options"] = {
                "certfile": self.ssl_options.ca_certs_path,
                "keyfile": self.ssl_options.keyfile_path,
                "ca_certs": self.ssl_options.ca_certs_path,
            }
        protocol = "amqps" if bool(self.ssl_options) else "amqp"
        if self.options.uri:
            url = "{}?{} ".format(self.options.uri, urlencode(opt))
        else:
            url = "{}://{}:{}@{}:{}{}?{} ".format(
                protocol,
                self.options.login,
                self.options.passwd,
                self.options.domain,
                self.options.port,
                self.options.vhost,
                urlencode(opt),
            )
        self.url = URLParameters(url)
        return self
