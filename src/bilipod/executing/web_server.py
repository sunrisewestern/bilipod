import http.server
import socketserver
import ssl
from pathlib import Path
from socketserver import ThreadingMixIn

from ..utils.bp_log import Logger

logger = Logger().get_logger()


class ThreadedHTTPServer(ThreadingMixIn, socketserver.TCPServer):
    """Handle requests in a separate thread."""


def run_web_server(server_config, data_dir: Path):
    web_dir = Path(__file__).parent.parent / "web"
    assets_dir = Path(__file__).parent.parent.parent / "assets"

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(web_dir), **kwargs)

        def translate_path(self, path):
            if path.startswith("/assets/"):
                path = path[len("/assets/") :]
                return str(assets_dir / path)
            return super().translate_path(path)

        def log_message(self, format, *args):
            logger.debug(f"[Web Server] {format % args}")

    server_address = (server_config.bind_address, server_config.port)

    if server_config.tls:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(
            certfile=server_config.certificate_path, keyfile=server_config.key_file
        )
        httpd = ThreadedHTTPServer(server_address, Handler)
        httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
    else:
        httpd = ThreadedHTTPServer(server_address, Handler)

    # Construct the base URL based on configuration
    if server_config.hostname is not None:
        base_url = f"{server_config.hostname}/{server_config.path}"
    else:
        base_url = f"{'https' if server_config.tls else 'http'}://{server_address[0]}:{server_address[1]}"

    logger.info(f"Web server running at: {base_url}")
    httpd.serve_forever()
