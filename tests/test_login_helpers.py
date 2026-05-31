import asyncio
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.bilipod.utils.login import (
    QRCodeLoginServer,
    SMSCodeServer,
    _format_public_url,
    _normalize_login_method,
    _path_prefix_from_url,
    _render_qrcode_login_page,
    _render_sms_code_page,
    _strip_path_prefix,
)


def test_login_method_aliases():
    assert _normalize_login_method("password") == "pwd"
    assert _normalize_login_method("sms") == "sms"
    assert _normalize_login_method("qr") == "qrcode"
    assert _normalize_login_method("") is None


def test_public_url_defaults_to_loopback_for_wildcard_bind():
    assert _format_public_url(None, "0.0.0.0", 41942) == "http://127.0.0.1:41942/"


def test_public_url_uses_explicit_configured_url():
    assert _format_public_url("https://example.com/login", "0.0.0.0", 41942) == (
        "https://example.com/login/"
    )


def test_auth_url_path_prefix_helpers():
    assert _path_prefix_from_url("https://example.com/bilipod/geetest-login/") == (
        "/bilipod/geetest-login"
    )
    assert _strip_path_prefix(
        "/bilipod/geetest-login/result/validate=ok",
        "/bilipod/geetest-login",
    ) == "/result/validate=ok"
    assert _strip_path_prefix("/result/validate=ok", "/bilipod/geetest-login") == (
        "/result/validate=ok"
    )


def test_qrcode_login_template_rendering_escapes_values():
    html = _render_qrcode_login_page(
        '<img src="{{ qrcode_src }}"><p data-health-src="{{ health_src }}">{{ status }}</p>',
        '/qrcode.png?next=<script>',
        'Waiting for <scan>',
        '/health?next=<script>',
    )

    assert "/qrcode.png?next=&lt;script&gt;" in html
    assert "/health?next=&lt;script&gt;" in html
    assert "Waiting for &lt;scan&gt;" in html


def test_sms_code_template_rendering_escapes_values():
    html = _render_sms_code_page(
        (
            '<form action="{{ form_action }}"><h1>{{ title }}</h1>'
            '<p data-health-src="{{ health_src }}">{{ message }}</p>'
            '<button {{ submit_button_attr }}>Submit</button></form>'
        ),
        'SMS <Title>',
        'Enter <code>',
        '/login?next=<script>',
        health_src='/health?next=<script>',
        submitted=True,
    )

    assert 'action="/login?next=&lt;script&gt;"' in html
    assert 'data-health-src="/health?next=&lt;script&gt;"' in html
    assert "SMS &lt;Title&gt;" in html
    assert "Enter &lt;code&gt;" in html
    assert "disabled" in html


def test_qrcode_login_server_serves_page_image_and_health():
    server = QRCodeLoginServer(
        image_bytes=b"fake-png",
        bind_address="127.0.0.1",
        port=0,
        status_getter=lambda: "Waiting for scan",
        path_prefix="/login",
    )

    try:
        server.start()
        base_url = f"http://127.0.0.1:{server.port}/login"

        with urlopen(f"{base_url}/", timeout=2) as response:
            html = response.read().decode("utf-8")
            assert response.status == 200
            assert 'src="/login/qrcode.png"' in html
            assert 'data-health-src="/login/health"' in html
            assert 'http-equiv="refresh"' not in html
            assert "Waiting for scan" in html

        with urlopen(f"{base_url}/qrcode.png", timeout=2) as response:
            assert response.status == 200
            assert response.headers["Content-Type"] == "image/png"
            assert response.read() == b"fake-png"

        with urlopen(f"{base_url}/health", timeout=2) as response:
            assert response.status == 200
            assert response.read().decode("utf-8") == "Waiting for scan"
    finally:
        server.stop()


def test_sms_code_server_serves_form_and_receives_code():
    server = SMSCodeServer(
        bind_address="127.0.0.1",
        port=0,
        path_prefix="/verify",
        title="Security Verification",
    )

    try:
        server.start()
        base_url = f"http://127.0.0.1:{server.port}/verify"

        with urlopen(f"{base_url}/", timeout=2) as response:
            html = response.read().decode("utf-8")
            assert response.status == 200
            assert 'action="/verify/"' in html
            assert 'data-health-src="/verify/health"' in html
            assert "Security Verification" in html

        body = urlencode({"code": "312225"}).encode("utf-8")
        request = Request(
            f"{base_url}/",
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urlopen(request, timeout=2) as response:
            html = response.read().decode("utf-8")
            assert response.status == 200
            assert "SMS code received" in html

        with urlopen(f"{base_url}/health", timeout=2) as response:
            assert response.status == 200
            assert (
                response.read().decode("utf-8")
                == "SMS code received. Verifying with Bilibili."
            )

        assert asyncio.run(server.wait_for_code()) == "312225"

        server.set_status("Login successful.", submitted=True)
        with urlopen(f"{base_url}/health", timeout=2) as response:
            assert response.status == 200
            assert response.read().decode("utf-8") == "Login successful."
    finally:
        server.stop()
