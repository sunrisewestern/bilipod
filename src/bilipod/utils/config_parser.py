import os
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, Literal, Optional, Sequence, Union

import yaml

from .parse_netscape import parse_netscape_cookies

ENV_VAR_PATTERN = re.compile(r"\$env\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _has_config_value(value) -> bool:
    return value is not None and str(value).strip() != ""


def _optional_str(value) -> Optional[str]:
    if not _has_config_value(value):
        return None
    return str(value)


def _expand_env_values(value: Any) -> Any:
    if isinstance(value, str):
        return ENV_VAR_PATTERN.sub(
            lambda match: os.environ.get(match.group(1), ""), value
        )
    if isinstance(value, dict):
        return {key: _expand_env_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_env_values(item) for item in value]
    return value


@dataclass
class ServerConfig:
    port: int = 5728
    hostname: Optional[str] = None
    bind_address: str = "localhost"
    path: str = ""
    tls: bool = False
    certificate_path: Optional[str] = None
    key_file_path: Optional[str] = None


@dataclass
class StorageConfig:
    type: str
    data_dir: str


@dataclass
class TokenConfig:
    bili_jct: str
    buvid3: str
    buvid4: str
    dedeuserid: str | int
    sessdata: str
    ac_time_value: str


@dataclass
class LoginConfig:
    method: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    phone_number: Optional[str] = None
    country_code: Optional[str] = "+86"
    geetest_bind_address: str = "0.0.0.0"
    geetest_login_port: int = 41942
    geetest_verify_port: int = 41943
    geetest_login_url: Optional[str] = None
    geetest_verify_url: Optional[str] = None
    qrcode_bind_address: str = "0.0.0.0"
    qrcode_port: int = 41944
    qrcode_url: Optional[str] = None


@dataclass
class FeedConfig:
    uid: Optional[str | int] = None
    sid: Optional[str | int] = None
    fid: Optional[str | int] = None
    playlist_type: Literal["season", "series"] | None = None
    page_size: int = 10
    update_period: str = "12h"
    format: str = "audio"
    playlist_sort: str = "desc"
    quality: str = "low"
    opml: bool = True
    keep_last: int = 10
    private_feed: bool = False
    endorse: Union[Literal["triple"], Sequence[str], None] = None
    keyword: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None
    cover_art: Optional[str] = None
    category: Optional[str] = None
    subcategories: Optional[Sequence[str]] = None
    explicit: Optional[bool] = None
    lang: Optional[str] = None
    link: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LogConfig:
    filename: str = "bilipod.log"
    max_size: int = 50  # MB
    max_age: int = 30  # days
    compress: bool = True
    debug: bool = False


@dataclass
class BiliPodConfig:
    server: ServerConfig
    storage: StorageConfig
    token: Optional[TokenConfig]
    login: LoginConfig
    feeds: Dict[str, FeedConfig]
    log: Optional[LogConfig]

    @staticmethod
    def from_yaml(config_file: str) -> "BiliPodConfig":
        with open(config_file, "r") as file:
            config_data = _expand_env_values(yaml.safe_load(file) or {})

        # Parse and create ServerConfig
        server_data = config_data.get("server", {})
        server_config = ServerConfig(
            port=server_data.get("port", 5728),
            hostname=server_data.get("hostname"),
            bind_address=server_data.get("bind_address", "localhost"),
            path=server_data.get("path", ""),
            tls=server_data.get("tls", False),
            certificate_path=server_data.get("certificate_path"),
            key_file_path=server_data.get("key_file_path"),
        )

        # Parse and create StorageConfig
        storage_data = config_data.get("storage", {})
        storage_config = StorageConfig(
            type=storage_data.get("type", "local"),
            data_dir=storage_data.get("storage.local", {}).get("data_dir", "/app/data"),
        )

        # Parse and create TokenConfig
        token_data = config_data.get("token")
        token_config = None
        if token_data:
            if _has_config_value(token_data.get("cookie_file_path")):
                token_data_update = parse_netscape_cookies(
                    token_data["cookie_file_path"]
                )
                token_data.update(token_data_update)

            required_token_fields = ("bili_jct", "buvid3", "dedeuserid", "sessdata")
            has_any_token_field = any(
                _has_config_value(token_data.get(field))
                for field in required_token_fields
            )

            if has_any_token_field:
                missing_token_fields = [
                    field
                    for field in required_token_fields
                    if not _has_config_value(token_data.get(field))
                ]
                if missing_token_fields:
                    raise ValueError(
                        "Token config is incomplete. Missing: "
                        + ", ".join(missing_token_fields)
                    )

                token_config = TokenConfig(
                    bili_jct=token_data["bili_jct"],
                    buvid3=token_data["buvid3"],
                    buvid4=token_data.get("buvid4", ""),
                    dedeuserid=token_data["dedeuserid"],
                    sessdata=token_data["sessdata"],
                    ac_time_value=token_data.get("ac_time_value", ""),
                )

        # Parse and create login_config
        login_data = config_data.get("login", {}) or {}
        login_config = LoginConfig(
            method=_optional_str(login_data.get("method")),
            username=_optional_str(login_data.get("username")),
            password=_optional_str(login_data.get("password")),
            phone_number=_optional_str(login_data.get("phone_number")),
            country_code=_optional_str(login_data.get("country_code")) or "+86",
            geetest_bind_address=str(
                login_data.get("geetest_bind_address", "0.0.0.0")
            ),
            geetest_login_port=login_data.get("geetest_login_port", 41942),
            geetest_verify_port=login_data.get("geetest_verify_port", 41943),
            geetest_login_url=_optional_str(login_data.get("geetest_login_url")),
            geetest_verify_url=_optional_str(login_data.get("geetest_verify_url")),
            qrcode_bind_address=str(login_data.get("qrcode_bind_address", "0.0.0.0")),
            qrcode_port=login_data.get("qrcode_port", 41944),
            qrcode_url=_optional_str(login_data.get("qrcode_url")),
        )

        # Parse and create FeedConfig for each feed
        feed_configs = parse_feed_configs(config_data)

        # Parse and create LogConfig if it exists
        log_data = config_data.get("log", None)
        log_config = LogConfig(**log_data) if log_data else None

        return BiliPodConfig(
            server=server_config,
            storage=storage_config,
            token=token_config,
            login=login_config,
            feeds=feed_configs,
            log=log_config,
        )


def parse_feed_configs(config_data: dict) -> Dict[str, FeedConfig]:
    feeds_data = config_data.get("feeds", {}) or {}
    return {
        feed_id: FeedConfig(**(feed or {})) for feed_id, feed in feeds_data.items()
    }


def load_feed_configs(config_file: str) -> Dict[str, FeedConfig]:
    """Load only the feed section from a config file."""
    with open(config_file, "r") as file:
        config_data = _expand_env_values(yaml.safe_load(file) or {})
    return parse_feed_configs(config_data)


if __name__ == "__main__":
    config = BiliPodConfig.from_yaml("/Users/cxx/Projects/bilipod/config_example.yaml")
