class SSLOptions:
    def __init__(
        self, certfile_path: str, keyfile_path: str, ca_certs_path: str
    ) -> None:
        """
        Create an SslOptions object that hold the certs paths.

        Args:
            certfile_path: cert file path string
            keyfile_path: private key file path string
            ca_certs_path: ca file path string

        Returns:
            Um dicionário com as notas da escala e os graus.

        Raises:

        Examples:
            >>> SSLOptions("./.certs/cert.pem", "./.certs/privkey.pem", "./.certs/ca.pem")
        """
        self.certfile_path = certfile_path
        self.keyfile_path = keyfile_path
        self.ca_certs_path = ca_certs_path
