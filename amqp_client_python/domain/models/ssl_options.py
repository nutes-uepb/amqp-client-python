class SSLOptions:
    def __init__(
        self, certfile_path: str, keyfile_path: str, ca_certs_path: str
    ) -> None:
        self.certfile_path = certfile_path
        self.keyfile_path = keyfile_path
        self.ca_certs_path = ca_certs_path
