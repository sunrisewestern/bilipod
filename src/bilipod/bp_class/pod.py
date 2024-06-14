from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal, Optional, Sequence, Union


@dataclass
class Pod:
    """
    Class representing a video podcast.

    Attributes:
        feed_id (str): Unique identifier for the podcast.
        update_at (float): Unix timestamp representing when the podcast was last updated.
        data_dir (Union[Path, str, None]): The directory where the podcast's data is stored.
        base_url (Optional[str]): The base URL of the podcast.
        uid (Optional[int]): The user ID of the creator of the podcast.
        sid (Optional[int]): The series ID of the podcast.
        title (Optional[str]): Title of the podcast.
        description (Optional[str]): Description of the podcast.
        cover_art (Optional[str]): URL of the cover art of the podcast.
        author (Optional[str]): The author of the podcast.
        link (Optional[str]): Link of the original media.
        category (Optional[str]): Category of the podcast.
        subcategories (Optional[Sequence[str]]): Subcategories of the podcast.
        explicit (Optional[Literal["yes", "no"]]): Indicates if the podcast is explicit.
        lang (Optional[str]): Language of the podcast.
        page_size (int): The number of episodes per page.
        update_period (str): The period of time between updates of the podcast.
        format (Literal["audio", "video"]): The format of the podcast.
        playlist_sort (Literal["asc", "desc"]): The sorting order of the podcast.
        quality (Literal["low", "high"]): The quality of the podcast.
        opml (bool): Indicates if the podcast is an OPML podcast.
        keep_last (int): The number of episodes to keep in the podcast.
        private_feed (bool): Indicates if the podcast is a private feed.
        like (bool): Indicates if the user likes the podcast.
        keyword (Optional[str]): The keyword of the podcast.
        episodes (dict): A dictionary mapping episode IDs to Episode objects.
        xml_url (Optional[Path]): The URL of the podcast's XML file.
    """

    feed_id: str
    update_at: float = 0  # unix timestamp
    data_dir: Union[Path, str, None] = None
    base_url: Optional[str] = None
    uid: Optional[int] = None
    sid: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    cover_art: Optional[str] = None
    author: Optional[str] = None
    link: Optional[str] = None
    category: Optional[str] = None
    subcategories: Optional[Sequence[str]] = None
    explicit: Optional[Literal["yes", "no"]] = None
    lang: Optional[str] = None
    page_size: int = 10
    update_period: str = "12h"
    format: Literal["audio", "video"] = "audio"
    playlist_sort: Literal["asc", "desc"] = "asc"
    quality: Literal["low", "high"] = "low"
    opml: Optional[bool] = None
    keep_last: int = 10
    private_feed: bool = True
    endorse: Union[Literal["triple"], Sequence[str], None] = None
    keyword: Optional[str] = None
    episodes: Sequence[dict] = None
    xml_url: Optional[str] = field(init=False)

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
        if self.base_url is not None:
            self.xml_url = f"{self.base_url}/{self.feed_id.replace('feed.', '', 1)}.xml"
        if self.data_dir is not None:
            self.data_dir = Path(self.data_dir)

    def to_dict(self) -> dict:
        self.data_dir = str(self.data_dir)
        return asdict(self)

    def update(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
