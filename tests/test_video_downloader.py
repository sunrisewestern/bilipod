from enum import Enum

from bilipod.downloader.video_downloader import codec_aliases, normalize_video_codecs


class StringCodec(Enum):
    HEV = "hev"


class TupleCodec(Enum):
    HEV = ("hev", "hvc")


def test_codec_aliases_supports_string_and_tuple_enum_values():
    assert codec_aliases(StringCodec.HEV) == ("hev",)
    assert codec_aliases(TupleCodec.HEV) == ("hev", "hvc")


def test_normalize_video_codecs_accepts_tuple_codec_value():
    data = {"dash": {"video": [{"codecs": "hvc1.1.6.L150.90"}]}}

    normalize_video_codecs(data)

    assert data["dash"]["video"][0]["codecs"] == "hvc1.1.6.L150.90"
