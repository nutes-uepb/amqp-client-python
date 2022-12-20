from typing import Optional
from .options import Options
from .ssl_options import SSLOptions
from urllib.parse import urlencode


class Config:
    def __init__(self,
        options: Options,
        ssl_options: Optional[SSLOptions] = SSLOptions()
    ) -> None:
        self.options = options
        self.ssl_options = ssl_options

    def build(self):
        return self


