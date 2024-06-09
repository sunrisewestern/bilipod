from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal, Optional, Union


@dataclass
class Episode:
    """
    Class representing an episode of a video.

    Attributes:
        bvid (str): Bilibili video ID.
        url (Optional[str]): URL to access the episode.
        link (Optional[str]): Link of the original media.
        title (Optional[str]): Title of the episode.
        description (Optional[str]): Description of the episode.
        image (Optional[str]): Image URL of the episode.
        duration (Optional[str]): Duration of the episode.
        pubdate (Optional[str]): Publication date of the episode.
        explicit (Literal["yes", "no"]): Indicates if the episode is explicit.
        format (Literal["audio", "video"]): Format of the episode.
        quality (Optional[Literal["low", "medium", "high"]]): Quality of the episode.
        data_dir (Optional[Path]): Data directory.
        location (Optional[Path]): Location of the episode.
        size (Optional[int]): Size of the episode in bytes.
        status (str): Status of the episode, downloaded,to_download, to_delete, deleted, default is to_download.
    """

    bvid: str
    base_url: Optional[str] = None
    url: Optional[str] = field(default=None, repr=False, init=False)
    link: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    image: Optional[str] = None
    duration: Optional[str] = None
    pubdate: Optional[str] = None
    explicit: Literal["yes", "no"] = "no"

    format: Literal["audio", "video"] = None
    type: Literal["audio/mpeg", "video/mp4"] = None
    quality: Optional[Literal["low", "medium", "high"]] = None
    video_quality: Optional[Literal["360P", "720P", "4K"]] = None
    audio_quality: Optional[Literal["64K", "132K", "192K"]] = None
    data_dir: Union[Path, str, None] = None
    location: Union[Path, str, None] = field(default=None, repr=False, init=False)
    size: Optional[int] = field(default=None, repr=False, init=False)
    status: Literal["downloaded", "to_be_deleted", "deleted"] = (
        "to_be_downloaded"
    )
    on_track: bool = True

    @classmethod
    def from_dict(cls, data: dict):
        # Create a new instance without calling __post_init__
        obj = cls.__new__(cls)
        for field_name, field_type in cls.__annotations__.items():
            value = data.get(field_name, None)
            if isinstance(value, str) and "Path" in str(field_type):
                value = Path(value)
            setattr(obj, field_name, value)
        return obj

    def __post_init__(self):
        self._set_link()
        self._set_type()
        self._set_quality()
        self._set_location()
        self._set_url()

    def _set_link(self):
        self.link = f"https://www.bilibili.com/video/{self.bvid}"

    def _set_location(self):
        if self.data_dir is None:
            return None

        self.data_dir = Path(self.data_dir)
        suffix = "mp3" if self.format == "audio" else "mp4"
        quility = self.video_quality if self.format == "video" else self.audio_quality
        self.location = self.data_dir / "media" / f"{self.bvid}_{quility}.{suffix}"

    def _set_url(self):
        suffix = "mp3" if self.format == "audio" else "mp4"
        quility = self.video_quality if self.format == "video" else self.audio_quality
        self.url = f"{self.base_url}/media/{self.bvid}_{quility}.{suffix}"

    def _set_quality(self):
        self.video_quality = {"low": "360P", "medium": "720P", "high": "4K"}[
            self.quality
        ]
        self.audio_quality = {"low": "64K", "medium": "132K", "high": "192K"}[
            self.quality
        ]

    def _set_type(self):
        self.type = "audio/mpeg" if self.format == "audio" else "video/mp4"

    def exists(self):
        if self.location is None:
            return False
        return self.location.exists()

    def to_dict(self) -> dict:
        # Convert the instance to a dictionary, excluding non-serializable fields
        data = asdict(self)
        data["data_dir"] = str(self.data_dir)
        data["location"] = str(self.location) if self.location else None
        return data

    def set_size(self) -> int:
        if self.location.exists() and self.status == "downloaded":
            self.size = self.location.stat().st_size

    def clean(self):
        if self.location is not None and self.location.exists():
            self.location.unlink()
        else:
            raise FileNotFoundError(f"File {self.location} does not exist.")

    def expand_description(self, text: str):
        self.description = f"{self.description}\n{text}"

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, Episode):
            return False
        return (
            self.bvid == value.bvid
            and self.quality == value.quality
            and self.format == value.format
        )

    def __hash__(self) -> int:
        return hash((self.bvid, self.quality, self.format))
