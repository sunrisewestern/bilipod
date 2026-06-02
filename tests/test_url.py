from src.bilipod.bp_class import Episode
from src.bilipod.executing.initialize import build_base_url
from src.bilipod.executing.web_server import _build_base_url
from src.bilipod.utils.config_parser import ServerConfig
from src.bilipod.utils.url import join_url, sanitize_url


def test_sanitize_url_collapses_repeated_path_slashes():
    assert (
        sanitize_url("http://localhost:7001//media/BV11NV86tEjW_192K.mp3")
        == "http://localhost:7001/media/BV11NV86tEjW_192K.mp3"
    )
    assert (
        sanitize_url("https://example.com/feed//media/file.mp3?next=http://x//y")
        == "https://example.com/feed/media/file.mp3?next=http://x//y"
    )
    assert (
        sanitize_url("feed//media/file.mp3?next=http://x//y")
        == "feed/media/file.mp3?next=http://x//y"
    )


def test_join_url_builds_media_url_without_double_slash():
    assert (
        join_url("http://localhost:7001/", "media", "BV11NV86tEjW_192K.mp3")
        == "http://localhost:7001/media/BV11NV86tEjW_192K.mp3"
    )


def test_episode_builds_media_url_without_double_slash(tmp_path):
    episode = Episode(
        bvid="BV11NV86tEjW",
        base_url="http://localhost:7001/",
        format="audio",
        quality="high",
        data_dir=tmp_path,
    )

    assert episode.url == "http://localhost:7001/media/BV11NV86tEjW_192K.mp3"


def test_episode_from_dict_sanitizes_existing_media_url():
    episode = Episode.from_dict(
        {
            "bvid": "BV11NV86tEjW",
            "url": "http://localhost:7001//media/BV11NV86tEjW_192K.mp3",
        }
    )

    assert episode.url == "http://localhost:7001/media/BV11NV86tEjW_192K.mp3"


def test_base_url_builders_sanitize_empty_hostname_path():
    server_config = ServerConfig(hostname="http://localhost:7001", path="")

    assert build_base_url(server_config) == "http://localhost:7001"
    assert _build_base_url(server_config) == "http://localhost:7001"
