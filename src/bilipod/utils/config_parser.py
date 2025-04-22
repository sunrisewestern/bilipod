from dataclasses import asdict, dataclass
from typing import Dict, Literal, Optional, Sequence, Union

import yaml

from .parse_netscape import parse_netscape_cookies


@dataclass
class ServerConfig:
    port: int = 8080
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
    username: Optional[str] = None
    password: Optional[str] = None
    phone_number: Optional[str] = None
    country_code: Optional[str] = "+86"


@dataclass
class FeedConfig:
    uid: Optional[str | int] = None
    sid: Optional[str | int] = None
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
    token: TokenConfig
    login: LoginConfig
    feeds: Dict[str, FeedConfig]
    log: LogConfig

    @staticmethod
    def from_yaml(config_file: str) -> "BiliPodConfig":
        with open(config_file, "r") as file:
            config_data = yaml.safe_load(file)

        # Parse and create ServerConfig
        server_data = config_data.get("server", {})
        server_config = ServerConfig(
            port=server_data.get("port", 8080),
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
        token_data = config_data.get("token", {})
        if token_data.get("cookie_file_path"):
            token_data_update = parse_netscape_cookies(token_data["cookie_file_path"])
            token_data.update(token_data_update)

        token_config = TokenConfig(
            bili_jct=token_data["bili_jct"],
            buvid3=token_data["buvid3"],
            buvid4=token_data.get("buvid4", ""),
            dedeuserid=token_data["dedeuserid"],
            sessdata=token_data["sessdata"],
            ac_time_value=token_data.get("ac_time_value", ""),
        )

        # Parse and create login_config
        login_data = config_data.get("login", {})
        login_config = LoginConfig(
            username=login_data.get("username"),
            password=login_data.get("password"),
            phone_number=login_data.get("phone_number"),
            country_code=login_data.get("country_code", "+86"),
        )

        # Parse and create FeedConfig for each feed
        feeds_data = config_data.get("feeds", {})
        feed_configs = {
            feed_id: FeedConfig(**feed) for feed_id, feed in feeds_data.items()
        }

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


if __name__ == "__main__":
    config = BiliPodConfig.from_yaml("/Users/cxx/Projects/bilipod/config_example.yaml")
