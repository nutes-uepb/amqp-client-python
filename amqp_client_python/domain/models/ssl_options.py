from typing import Optional


class SSLOptions:
    def __init__(
        self,
        certfile_path: Optional[str] = None,
        keyfile_path: Optional[str] = None,
        ca_certs_path: Optional[str] = None
    ) -> None:
        self.certfile_path = certfile_path
        self.keyfile_path = keyfile_path
        self.ca_certs_path = ca_certs_path
