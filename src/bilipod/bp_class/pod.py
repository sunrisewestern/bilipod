from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal, Optional, Sequence, Union


@dataclass
class Pod:
    """Represents a video or audio podcast.

    Attributes:
        feed_id: Unique identifier for the podcast.
        update_at: Unix timestamp representing the last update time.
        data_dir: Directory where podcast data is stored.
        base_url: Base URL of the podcast.
        uid: User ID of the podcast creator.
        sid: Series ID of the podcast. Used for FavoriteLists. Use either uid or sid.
        title: Title of the podcast.
        description: Description of the podcast.
        cover_art: URL of the cover art.
        author: Author of the podcast.
        link: Link to the original media source.
        category: Category of the podcast.
        subcategories: Subcategories of the podcast.
        explicit: Whether the podcast is explicit ('yes' or 'no').
        lang: Language of the podcast.
        page_size: Number of episodes per page.
        update_period: Frequency of podcast updates (e.g., '12h').
        format: Format of the podcast ('audio' or 'video').
        playlist_sort: Sorting order of the playlist ('asc' or 'desc').
        quality: Quality of the podcast ('low' or 'high').
        opml: Whether the podcast is an OPML podcast.
        keep_last: Number of episodes to keep.
        private_feed: Whether the podcast is a private feed.
        endorse: Endorsement information ('triple' or a list of strings).
        keyword: Keyword associated with the podcast.
        episodes: List of episode dictionaries (each representing an Episode object).
        xml_url: URL of the podcast's XML file (automatically generated).
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
