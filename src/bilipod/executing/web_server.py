import http.server
import json
import mimetypes
import socketserver
import ssl
from pathlib import Path
from socketserver import ThreadingMixIn
from urllib.parse import urlparse

import jinja2

from ..utils.auth_status import get_auth_status
from ..utils.bp_log import Logger
from ..utils.url import join_url, sanitize_url

logger = Logger().get_logger()


class ThreadedHTTPServer(ThreadingMixIn, socketserver.TCPServer):
    """Handle requests in a separate thread."""


def _build_base_url(server_config, server_address=None) -> str:
    if server_config.hostname is not None:
        return join_url(server_config.hostname, server_config.path)

    if server_address is None:
        bind_address = server_config.bind_address
        port = server_config.port
        scheme = "https" if server_config.tls else "http"
    else:
        bind_address, port = server_address
        scheme = "https" if server_config.tls else "http"

    host = "localhost" if bind_address == "0.0.0.0" else bind_address
    return sanitize_url(f"{scheme}://{host}:{port}")


def run_web_server(server_config, data_dir: Path):
    # Set up the Jinja2 environment to load templates from the 'web' folder
    # Assuming index.html is directly in the 'web' folder,
    # and 'static' subfolder is for other assets.
    template_loader = jinja2.FileSystemLoader(
        Path(__file__).parent.parent.resolve() / "web" / "static"
    )
    jinja_env = jinja2.Environment(loader=template_loader)

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            # The directory is set to data_dir to serve assets and listed files
            super().__init__(*args, directory=str(data_dir), **kwargs)

        def do_GET(self):
            request_path = urlparse(self.path).path
            if request_path == "/" or request_path == "/index.html":
                try:
                    template = jinja_env.get_template("index.html")
                    base_url = _build_base_url(server_config)

                    output = template.render(base_url=base_url)

                    self.send_response(200)
                    self.send_header("Content-type", "text/html; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(output.encode("utf-8"))
                except Exception as e:
                    logger.error(f"Error serving index.html: {e}")
                    self.send_error(500, "Error serving index.html")
            elif request_path == "/auth/status":
                body = json.dumps(get_auth_status()).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif request_path == "/podcast.opml":
                opml_path = data_dir / "podcast.opml"
                logger.info(f"Serving OPML file: {opml_path}")
                if opml_path.is_file():
                    try:
                        with open(opml_path, "rb") as f:
                            self.send_response(200)
                            self.send_header(
                                "Content-type", "application/xml; charset=utf-8"
                            )
                            self.send_header("Cache-Control", "no-store")
                            self.end_headers()
                            self.wfile.write(f.read())
                    except Exception as e:
                        logger.error(f"Error serving podcast.opml: {e}")
                        self.send_error(500, "Error serving opml.xml")
                else:
                    self.send_error(404, "podcast.opml not found")
            elif request_path.endswith(".xml"):
                # Serve other XML files directly from the data directory
                xml_file_name = request_path.lstrip("/")
                xml_path = Path(data_dir) / xml_file_name
                if xml_path.is_file():
                    try:
                        with open(xml_path, "rb") as f:
                            self.send_response(200)
                            self.send_header(
                                "Content-type", "application/xml; charset=utf-8"
                            )
                            self.send_header("Cache-Control", "no-store")
                            self.end_headers()
                            self.wfile.write(f.read())
                    except Exception as e:
                        logger.error(f"Error serving {xml_file_name}: {e}")
                        self.send_error(500, f"Error serving {xml_file_name}")
                else:
                    logger.warning(f"XML file not found: {xml_path}")
                    self.send_error(404, f"{xml_file_name} not found")
            elif request_path.startswith("/static"):
                static_file_path = (
                    Path(__file__).parent.parent.resolve()
                    / "web"
                    / request_path.lstrip("/")
                )
                if static_file_path.is_file():
                    self.send_response(200)
                    mimetype, _ = mimetypes.guess_type(static_file_path)
                    self.send_header(
                        "Content-type", mimetype or "application/octet-stream"
                    )
                    self.end_headers()
                    with open(static_file_path, "rb") as f:
                        self.wfile.write(f.read())
                else:
                    logger.warning(f"Static asset not found: {static_file_path}")
                    self.send_error(404, "Static asset not found")
            else:
                # For all other paths, fall back to serving files from data_dir
                super().do_GET()

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

    base_url = _build_base_url(server_config, server_address)

    logger.info(f"Web server running at: {base_url}")
    httpd.serve_forever()
