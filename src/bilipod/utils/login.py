import asyncio
import http.server
import sys
import threading
import time
from getpass import getpass
from html import escape
from pathlib import Path
from typing import Callable, Literal, Optional
from urllib.parse import parse_qs, urlparse

from bilibili_api import Credential, Geetest, GeetestType, login_v2, user
from bilibili_api.exceptions import GeetestException
from bilibili_api.utils.geetest import ServerThread

from .auth_status import set_auth_status
from .bp_log import Logger
from .config_parser import BiliPodConfig, LoginConfig

logger = Logger().get_logger()

QRCODE_LOGIN_TEMPLATE_PATH = (
    Path(__file__).parent.parent / "web" / "static" / "qrcode_login.html"
)
SMS_CODE_TEMPLATE_PATH = (
    Path(__file__).parent.parent / "web" / "static" / "sms_code.html"
)
SMS_STATUS_DISPLAY_SECONDS = 60

LoginMethod = Literal["pwd", "sms", "qrcode"]


class FixedPortGeetest(Geetest):
    def __init__(
        self, port: int = 0, host: str = "0.0.0.0", path_prefix: str = ""
    ):
        super().__init__()
        self._host = host
        self._port = port
        self._path_prefix = path_prefix

    def start_geetest_server(self) -> None:
        """
        Start the local Geetest challenge server on a deterministic host and port.
        """
        if self.thread is not None:
            raise GeetestException("Captcha server already exists.")

        self.thread = ServerThread(self._geetest_urlhandler, self._host, self._port)
        self.thread.start()
        while not self.thread.error and not self.thread.serving:
            time.sleep(0.05)

        if self.thread.error:
            error = self.thread.error
            self.thread = None
            raise GeetestException(
                f"Failed to start Geetest server on {self._host}:{self._port}: {error}"
            )

    def _geetest_urlhandler(self, url: str, content_type: str) -> str:
        return super()._geetest_urlhandler(
            _strip_path_prefix(url, self._path_prefix), content_type
        )


class _ReusableThreadingHTTPServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = True


class QRCodeLoginServer:
    def __init__(
        self,
        image_bytes: bytes,
        bind_address: str,
        port: int,
        status_getter: Callable[[], str],
        path_prefix: str = "",
    ):
        self._image_bytes = image_bytes
        self._bind_address = bind_address
        self._port = port
        self._status_getter = status_getter
        self._path_prefix = path_prefix
        self._server: Optional[_ReusableThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        image_bytes = self._image_bytes
        status_getter = self._status_getter
        path_prefix = self._path_prefix
        image_path = f"{path_prefix}/qrcode.png" if path_prefix else "/qrcode.png"
        health_path = f"{path_prefix}/health" if path_prefix else "/health"
        template_source = _load_qrcode_login_template()

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                request_path = _strip_path_prefix(self.path, path_prefix)
                if request_path in ("/", "/index.html"):
                    body = _render_qrcode_login_page(
                        template_source=template_source,
                        qrcode_src=image_path,
                        health_src=health_path,
                        status=status_getter(),
                    )
                    body_bytes = body.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body_bytes)))
                    self.end_headers()
                    self.wfile.write(body_bytes)
                elif request_path == "/qrcode.png":
                    self.send_response(200)
                    self.send_header("Content-Type", "image/png")
                    self.send_header("Content-Length", str(len(image_bytes)))
                    self.end_headers()
                    self.wfile.write(image_bytes)
                elif request_path == "/health":
                    status = status_getter().encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Content-Length", str(len(status)))
                    self.end_headers()
                    self.wfile.write(status)
                else:
                    self.send_error(404)

            def log_message(self, format, *args):
                logger.debug(f"[QR Login Server] {format % args}")

        self._server = _ReusableThreadingHTTPServer(
            (self._bind_address, self._port), Handler
        )
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    @property
    def port(self) -> int:
        if self._server is not None:
            return self._server.server_port
        return self._port


class SMSCodeServer:
    def __init__(
        self,
        bind_address: str,
        port: int,
        path_prefix: str = "",
        title: str = "BiliPod SMS Verification",
        message: str = "Enter the SMS code sent by Bilibili.",
    ):
        self._bind_address = bind_address
        self._port = port
        self._path_prefix = path_prefix
        self._title = title
        self._message = message
        self._submitted = False
        self._lock = threading.Lock()
        self._server: Optional[_ReusableThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._code: Optional[str] = None
        self._code_ready = threading.Event()

    def start(self) -> None:
        path_prefix = self._path_prefix
        form_action = f"{path_prefix}/" if path_prefix else "/"
        health_path = f"{path_prefix}/health" if path_prefix else "/health"
        template_source = _load_sms_code_template()
        sms_server = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                request_path = _strip_path_prefix(self.path, path_prefix)
                if request_path in ("/", "/index.html"):
                    message, submitted = sms_server.get_status()
                    self._send_html(
                        _render_sms_code_page(
                            template_source=template_source,
                            title=sms_server._title,
                            message=message,
                            form_action=form_action,
                            health_src=health_path,
                            submitted=submitted,
                        )
                    )
                elif request_path == "/health":
                    message, _ = sms_server.get_status()
                    self._send_text(message)
                else:
                    self.send_error(404)

            def do_POST(self):
                request_path = _strip_path_prefix(self.path, path_prefix)
                if request_path not in ("/", "/index.html"):
                    self.send_error(404)
                    return

                content_length = int(self.headers.get("Content-Length", "0"))
                raw_body = self.rfile.read(content_length).decode("utf-8")
                code = parse_qs(raw_body).get("code", [""])[0].strip()
                if not code:
                    self._send_html(
                        _render_sms_code_page(
                            template_source=template_source,
                            title=sms_server._title,
                            message="Please enter the SMS code.",
                            form_action=form_action,
                            health_src=health_path,
                        ),
                        status=400,
                    )
                    return

                sms_server._code = code
                sms_server.set_status(
                    "SMS code received. Verifying with Bilibili.", submitted=True
                )
                sms_server._code_ready.set()
                self._send_html(
                    _render_sms_code_page(
                        template_source=template_source,
                        title=sms_server._title,
                        message=sms_server.get_status()[0],
                        form_action=form_action,
                        health_src=health_path,
                        submitted=True,
                    )
                )

            def _send_html(self, body: str, status: int = 200):
                body_bytes = body.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body_bytes)))
                self.end_headers()
                self.wfile.write(body_bytes)

            def _send_text(self, body: str):
                body_bytes = body.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body_bytes)))
                self.end_headers()
                self.wfile.write(body_bytes)

            def log_message(self, format, *args):
                logger.debug(f"[SMS Code Server] {format % args}")

        self._server = _ReusableThreadingHTTPServer(
            (self._bind_address, self._port), Handler
        )
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def get_status(self) -> tuple[str, bool]:
        with self._lock:
            return self._message, self._submitted

    def set_status(self, message: str, submitted: Optional[bool] = None) -> None:
        with self._lock:
            self._message = message
            if submitted is not None:
                self._submitted = submitted

    async def wait_for_code(self) -> str:
        while not self._code_ready.is_set():
            await asyncio.sleep(0.5)
        if self._code is None:
            raise RuntimeError("SMS code was not captured.")
        return self._code

    @property
    def has_code(self) -> bool:
        return self._code_ready.is_set()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    @property
    def port(self) -> int:
        if self._server is not None:
            return self._server.server_port
        return self._port


async def password_login(
    choice: Literal["pwd", "sms"],
    username=None,
    password=None,
    phone_number=None,
    country_code="+86",
    login_config: Optional[LoginConfig] = None,
) -> Credential:
    login_config = login_config or LoginConfig()
    gee = await _complete_geetest_challenge(
        type_=GeetestType.LOGIN,
        bind_address=login_config.geetest_bind_address,
        port=login_config.geetest_login_port,
        public_url=login_config.geetest_login_url,
        label="login",
    )

    if choice == "pwd":
        username = username or input("Username: ")
        password = password if password is not None else getpass("Password: ")
        cred = await login_v2.login_with_password(
            username=username, password=password, geetest=gee
        )
    elif choice == "sms":
        phone_number = phone_number or input("Phone number: ")
        country_code = country_code or input("Country code (default +86): ") or "+86"
        phone = login_v2.PhoneNumber(phone_number, country_code)
        captcha_id = await login_v2.send_sms(phonenumber=phone, geetest=gee)
        logger.info("SMS code sent.")
        sms_server = _start_sms_code_prompt(
            bind_address=login_config.geetest_bind_address,
            port=login_config.geetest_login_port,
            public_url=login_config.geetest_login_url,
            label="SMS login",
        )
        keep_sms_server = False
        try:
            code = await sms_server.wait_for_code()
            logger.info("SMS login code received from web page.")
            sms_server.set_status("Verifying SMS code with Bilibili.", submitted=True)
            set_auth_status("working", "Verifying SMS code with Bilibili.")
            cred = await login_v2.login_with_sms(
                phonenumber=phone, code=code, captcha_id=captcha_id
            )
            _finish_sms_code_prompt(
                sms_server, "SMS login successful. You can close this page."
            )
            keep_sms_server = True
        except Exception:
            if sms_server.has_code:
                _finish_sms_code_prompt(
                    sms_server,
                    "SMS login failed. Check Bilipod logs for details.",
                    state="error",
                )
                keep_sms_server = True
            raise
        finally:
            if not keep_sms_server:
                sms_server.stop()
    else:
        raise ValueError("Invalid login method. Use 'pwd' or 'sms'.")

    if isinstance(cred, login_v2.LoginCheck):
        verify_gee = await _complete_geetest_challenge(
            type_=GeetestType.VERIFY,
            bind_address=login_config.geetest_bind_address,
            port=login_config.geetest_verify_port,
            public_url=login_config.geetest_verify_url,
            label="security verification",
        )
        await cred.send_sms(verify_gee)
        logger.info("Security verification SMS code sent.")
        sms_server = _start_sms_code_prompt(
            bind_address=login_config.geetest_bind_address,
            port=login_config.geetest_verify_port,
            public_url=login_config.geetest_verify_url,
            label="security verification",
        )
        keep_sms_server = False
        try:
            code = await sms_server.wait_for_code()
            logger.info("Security verification SMS code received from web page.")
            sms_server.set_status("Verifying SMS code with Bilibili.", submitted=True)
            set_auth_status("working", "Verifying SMS code with Bilibili.")
            cred = await cred.complete_check(code)
            _finish_sms_code_prompt(
                sms_server,
                "Security verification successful. You can close this page.",
            )
            keep_sms_server = True
        except Exception:
            if sms_server.has_code:
                _finish_sms_code_prompt(
                    sms_server,
                    "Security verification failed. Check Bilipod logs for details.",
                    state="error",
                )
                keep_sms_server = True
            raise
        finally:
            if not keep_sms_server:
                sms_server.stop()

    return cred


async def qrcode_login(login_config: Optional[LoginConfig] = None) -> Credential:
    login_config = login_config or LoginConfig()
    qr_login = login_v2.QrCodeLogin()
    await qr_login.generate_qrcode()

    status = {"message": "Scan this QR code with the Bilibili app."}
    qr_server = QRCodeLoginServer(
        image_bytes=qr_login.get_qrcode_picture().content,
        bind_address=login_config.qrcode_bind_address,
        port=login_config.qrcode_port,
        status_getter=lambda: status["message"],
        path_prefix=_path_prefix_from_url(login_config.qrcode_url),
    )

    try:
        qr_server.start()
        public_url = _format_public_url(
            login_config.qrcode_url,
            login_config.qrcode_bind_address,
            qr_server.port,
        )
        _announce_auth_page("QR code login", public_url)
        print(qr_login.get_qrcode_terminal())

        last_event = None
        while True:
            event = await qr_login.check_state()
            status["message"] = _qrcode_status_text(event)
            if event != last_event:
                logger.info(status["message"])
                set_auth_status(
                    state="action_required",
                    message=status["message"],
                    action_label="Open QR code login",
                    action_url=public_url,
                )
                last_event = event

            if event == login_v2.QrCodeLoginEvents.DONE:
                set_auth_status("complete", "QR code login complete.")
                return qr_login.get_credential()
            if event == login_v2.QrCodeLoginEvents.TIMEOUT:
                set_auth_status(
                    "error",
                    "QR code expired. Restart Bilipod to generate a new code.",
                )
                raise RuntimeError(
                    "QR code login timed out. Restart Bilipod to generate a new code."
                )

            await asyncio.sleep(3)
    finally:
        qr_server.stop()


async def get_credential(config: BiliPodConfig) -> Credential:
    if config.token:
        if not config.token.ac_time_value:
            logger.warning("ac_time_value is not set. It may cause some issues.")

        credential = Credential(
            bili_jct=config.token.bili_jct,
            buvid3=config.token.buvid3,
            # buvid4=config.token.buvid4,
            dedeuserid=config.token.dedeuserid,
            sessdata=config.token.sessdata,
            ac_time_value=config.token.ac_time_value,
        )
        validation = await credential.check_valid()
        if not validation:
            logger.error(
                "Login failed. Credential is not valid. Please check your token."
            )
            sys.exit()
    else:
        try:
            method = _resolve_login_method(config.login)
        except ValueError as e:
            logger.error(str(e))
            sys.exit()

        if method == "pwd":
            credential = await password_login(
                choice="pwd",
                username=config.login.username,
                password=config.login.password,
                login_config=config.login,
            )
        elif method == "sms":
            credential = await password_login(
                choice="sms",
                phone_number=config.login.phone_number,
                country_code=config.login.country_code,
                login_config=config.login,
            )
        elif method == "qrcode":
            credential = await qrcode_login(login_config=config.login)
        else:
            logger.error("Invalid login method. Please choose pwd, sms, or qrcode.")
            sys.exit()

        logger.debug(
            f"""
                bili_jct: {credential.bili_jct}
                buvid3: {credential.buvid3}
                dedeuserid: {credential.dedeuserid}
                sessdata: {credential.sessdata}
                ac_time_value: {credential.ac_time_value}
            """
        )

    user_info = await user.get_self_info(credential)
    logger.info(f"Welcome, {user_info['name']}!")
    set_auth_status("complete", "Login complete.")

    return credential


async def update_credential(credential: Credential):
    validation = await credential.check_valid()
    if not validation:
        logger.error("Credential is outdated. Please check your token.")
        sys.exit()

    update_status = await credential.check_refresh()
    if update_status:
        logger.debug("Updating token...")
        try:
            await credential.refresh()
        except Exception as e:
            logger.error(f"Failed to update token: {e}")
            sys.exit()

    else:
        logger.debug("No need to update token")


async def _complete_geetest_challenge(
    type_: GeetestType,
    bind_address: str,
    port: int,
    public_url: Optional[str],
    label: str,
) -> Geetest:
    gee = FixedPortGeetest(
        port=port, host=bind_address, path_prefix=_path_prefix_from_url(public_url)
    )
    await gee.generate_test(type_=type_)
    try:
        gee.start_geetest_server()
        actual_port = gee.thread.port if gee.thread is not None else port
        display_url = _format_public_url(public_url, bind_address, actual_port)
        _announce_auth_page(f"Geetest {label}", display_url)
        while not gee.has_done():
            await asyncio.sleep(1)
        logger.debug(f"Geetest {label} result: {gee.get_result()}")
        set_auth_status(
            "working",
            f"Geetest {label} complete. Continuing login.",
        )
    except Exception:
        set_auth_status(
            "error",
            f"Geetest {label} failed. Check Bilipod logs for details.",
        )
        raise
    finally:
        if gee.thread is not None:
            gee.close_geetest_server()

    return gee


def _start_sms_code_prompt(
    bind_address: str,
    port: int,
    public_url: Optional[str],
    label: str,
) -> SMSCodeServer:
    sms_server = SMSCodeServer(
        bind_address=bind_address,
        port=port,
        path_prefix=_path_prefix_from_url(public_url),
        title=f"BiliPod {label.title()}",
    )
    sms_server.start()
    actual_port = sms_server.port
    display_url = _format_public_url(public_url, bind_address, actual_port)
    _announce_auth_page(f"{label.title()} SMS code", display_url)
    return sms_server


def _finish_sms_code_prompt(
    sms_server: SMSCodeServer, message: str, state: str = "complete"
) -> None:
    sms_server.set_status(message, submitted=True)
    set_auth_status(state, message)
    stop_timer = threading.Timer(SMS_STATUS_DISPLAY_SECONDS, sms_server.stop)
    stop_timer.daemon = True
    stop_timer.start()


def _resolve_login_method(login_config: LoginConfig) -> LoginMethod:
    configured_method = _normalize_login_method(login_config.method)
    if configured_method:
        return configured_method
    if login_config.username and login_config.password:
        return "pwd"
    if login_config.phone_number:
        return "sms"

    choice = input("Please choose login method (pwd/sms/qrcode): ")
    return _normalize_login_method(choice) or "qrcode"


def _normalize_login_method(method: Optional[str]) -> Optional[LoginMethod]:
    if method is None:
        return None

    normalized = method.strip().lower()
    if not normalized:
        return None

    if normalized in ("pwd", "password", "username_password"):
        return "pwd"
    if normalized in ("sms", "phone", "phone_number"):
        return "sms"
    if normalized in ("qr", "qrcode", "qr_code"):
        return "qrcode"

    raise ValueError("Invalid login method. Use pwd, sms, or qrcode.")


def _format_public_url(
    configured_url: Optional[str], bind_address: str, port: int
) -> str:
    if configured_url:
        return _ensure_trailing_slash(configured_url)

    return f"http://{_public_host(bind_address)}:{port}/"


def _ensure_trailing_slash(url: str) -> str:
    return url if url.endswith("/") else f"{url}/"


def _announce_auth_page(label: str, url: str) -> None:
    logger.info(f"{label} page: {url}")
    logger.info("Open the page in a browser and finish the login challenge there.")
    set_auth_status(
        state="action_required",
        message=f"{label} required.",
        action_label=f"Open {label}",
        action_url=url,
    )


def _qrcode_status_text(event) -> str:
    if event == login_v2.QrCodeLoginEvents.SCAN:
        return "Waiting for scan in the Bilibili app."
    if event == login_v2.QrCodeLoginEvents.CONF:
        return "QR code scanned. Confirm login in the Bilibili app."
    if event == login_v2.QrCodeLoginEvents.TIMEOUT:
        return "QR code expired. Restart Bilipod to generate a new code."
    if event == login_v2.QrCodeLoginEvents.DONE:
        return "QR code login complete."
    return f"QR code login status: {event}"


def _public_host(host: str) -> str:
    if host in ("0.0.0.0", "::"):
        return "127.0.0.1"
    if ":" in host and not host.startswith("["):
        return f"[{host}]"
    return host


def _load_qrcode_login_template() -> str:
    return QRCODE_LOGIN_TEMPLATE_PATH.read_text(encoding="utf-8")


def _load_sms_code_template() -> str:
    return SMS_CODE_TEMPLATE_PATH.read_text(encoding="utf-8")


def _render_qrcode_login_page(
    template_source: str, qrcode_src: str, status: str, health_src: str = "/health"
) -> str:
    return (
        template_source.replace("{{ qrcode_src }}", escape(qrcode_src, quote=True))
        .replace("{{ health_src }}", escape(health_src, quote=True))
        .replace("{{ status }}", escape(status))
    )


def _render_sms_code_page(
    template_source: str,
    title: str,
    message: str,
    form_action: str,
    health_src: str = "/health",
    submitted: bool = False,
) -> str:
    submit_button_attr = "disabled" if submitted else ""
    return (
        template_source.replace("{{ title }}", escape(title))
        .replace("{{ message }}", escape(message))
        .replace("{{ form_action }}", escape(form_action, quote=True))
        .replace("{{ health_src }}", escape(health_src, quote=True))
        .replace("{{ submit_button_attr }}", submit_button_attr)
    )


def _path_prefix_from_url(url: Optional[str]) -> str:
    if not url:
        return ""
    return _normalize_path_prefix(urlparse(url).path)


def _normalize_path_prefix(path: str) -> str:
    if not path or path == "/":
        return ""
    if not path.startswith("/"):
        path = f"/{path}"
    return path.rstrip("/")


def _strip_path_prefix(path: str, path_prefix: str) -> str:
    path = path.split("?", 1)[0]
    path_prefix = _normalize_path_prefix(path_prefix)
    if path_prefix and (path == path_prefix or path.startswith(f"{path_prefix}/")):
        return path[len(path_prefix) :] or "/"
    return path
