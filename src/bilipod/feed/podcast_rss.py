"""
Make a podcast XML feed with feedgen
"""

import datetime

import tzlocal
from feedgen.feed import FeedGenerator
from tinydb import table

from bp_class import Episode, Pod
from utils.biliuser import get_episode_list
from utils.bp_log import Logger
from utils.db_query import query_episode

logger = Logger().get_logger()


def convert_timestamp_to_localtime(timestamp: int) -> str:
    local_timezone = tzlocal.get_localzone()
    dt_object = datetime.datetime.fromtimestamp(timestamp)
    local_dt = dt_object.astimezone(local_timezone)
    return local_dt


def generate_feed_xml(
    pod: Pod,
    episode_tbl: table.Table,
):
    """
    user_info: {
        "title": str,
        "description": str,
        "cover_art": str,
        "author": str,
        "link": str
    }
    """
    fg = FeedGenerator()
    fg.load_extension("podcast", atom=False, rss=True)
    fg.title(f"{pod.title}[{pod.keyword}]" if pod.keyword else pod.title)
    if pod.description:
        fg.description(pod.description)
    else:
        fg.description(pod.title)
    fg.link({"href": pod.link, "rel": "alternate"})
    fg.image(url=pod.cover_art, title=pod.title, link=pod.link)

    fg.podcast.itunes_category(pod.category, pod.subcategories)
    fg.podcast.itunes_author(pod.author)

    matches = [
        episode_tbl.search(query_episode(episode_info))[0]
        for episode_info in get_episode_list(pod)
    ]
    episodes = (Episode.from_dict(episode) for episode in matches)

    for episode in episodes:
        if not episode.exists():
            continue

        pubdate = convert_timestamp_to_localtime(episode.pubdate)
        fe = fg.add_entry()
        fe.title(episode.title)
        fe.link({"href": episode.link, "rel": "alternate"})
        fe.description(episode.description)
        fe.guid(episode.bvid, permalink=False)
        fe.pubDate(pubdate)
        fe.enclosure(url=episode.url, length=episode.size, type=episode.type)

        fe.podcast.itunes_duration(episode.duration)
        fe.podcast.itunes_image(episode.image)
        fe.podcast.itunes_explicit(episode.explicit)

    feed_name = f"{pod.feed_id.replace('feed.','',1)}"

    # Remove old feed if exists
    # str(pod.data_dir / f"{feed_name}.xml").unlink(missing_ok=True)

    fg.rss_file(
        filename=str(pod.data_dir / f"{feed_name}.xml"),
        pretty=True,
    )
    logger.info(f"Generated feed for {feed_name}")
