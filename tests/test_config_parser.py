import pytest

from src.bilipod.utils.config_parser import BiliPodConfig


def test_blank_token_config_uses_login_config(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
server: {}
storage: {}
token:
  bili_jct:
  buvid3:
  dedeuserid:
  sessdata:
login:
  method: qrcode
  geetest_login_port: 5001
  geetest_verify_port: 5002
  qrcode_port: 5003
feeds: {}
""",
        encoding="utf-8",
    )

    config = BiliPodConfig.from_yaml(str(config_file))

    assert config.token is None
    assert config.login.method == "qrcode"
    assert config.login.geetest_login_port == 5001
    assert config.login.geetest_verify_port == 5002
    assert config.login.qrcode_port == 5003


def test_partial_token_config_raises(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
server: {}
storage: {}
token:
  bili_jct: token
login: {}
feeds: {}
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Token config is incomplete"):
        BiliPodConfig.from_yaml(str(config_file))


def test_numeric_login_fields_are_loaded_as_strings(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
server: {}
storage: {}
token:
login:
  method: sms
  username: 12345678901
  password: 123456
  phone_number: 12345678901
  country_code: 86
  geetest_login_url: https://example.com/login
feeds: {}
""",
        encoding="utf-8",
    )

    config = BiliPodConfig.from_yaml(str(config_file))

    assert config.login.method == "sms"
    assert config.login.username == "12345678901"
    assert config.login.password == "123456"
    assert config.login.phone_number == "12345678901"
    assert config.login.country_code == "86"
    assert config.login.geetest_login_url == "https://example.com/login"


def test_env_variables_are_expanded_in_config(tmp_path, monkeypatch):
    monkeypatch.setenv("BILIPOD_HOSTNAME", "https://example.com")
    monkeypatch.setenv("BILIPOD_DATA_DIR", "/tmp/bilipod-data")
    monkeypatch.setenv("BILIPOD_USERNAME", "alice")
    monkeypatch.setenv("BILIPOD_PASSWORD", "secret")
    monkeypatch.delenv("BILIPOD_PHONE_NUMBER", raising=False)
    monkeypatch.delenv("BILIPOD_COUNTRY_CODE", raising=False)

    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
server:
  hostname: $env{BILIPOD_HOSTNAME}
storage:
  storage.local:
    data_dir: $env{BILIPOD_DATA_DIR}/media
token:
login:
  method: password
  username: $env{BILIPOD_USERNAME}
  password: $env{BILIPOD_PASSWORD}
  phone_number: $env{BILIPOD_PHONE_NUMBER}
  country_code: $env{BILIPOD_COUNTRY_CODE}
  geetest_login_url: $env{BILIPOD_HOSTNAME}/login
feeds: {}
""",
        encoding="utf-8",
    )

    config = BiliPodConfig.from_yaml(str(config_file))

    assert config.server.hostname == "https://example.com"
    assert config.storage.data_dir == "/tmp/bilipod-data/media"
    assert config.login.username == "alice"
    assert config.login.password == "secret"
    assert config.login.phone_number is None
    assert config.login.country_code == "+86"
    assert config.login.geetest_login_url == "https://example.com/login"
