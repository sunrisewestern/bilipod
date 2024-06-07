class DownloadError(Exception):
    """Custom exception for download errors."""

    def __init__(self, message, url, bytes_received, bytes_expected):
        super().__init__(message)
        self.url = url
        self.bytes_received = bytes_received
        self.bytes_expected = bytes_expected
        self.message = message

    def __str__(self):
        return (
            f"{self.message} (URL: {self.url}, "
            f"Received: {self.bytes_received} bytes, "
            f"Expected: {self.bytes_expected} bytes)"
        )

