"""
Make a podcast XML feed with feedgen
"""

import datetime

import tzlocal
from feedgen.feed import FeedGenerator
from tinydb import table
import re

from ..bp_class import Episode, Pod
from ..utils.biliuser import get_episode_list
from ..utils.bp_log import Logger
from ..utils.db_query import query_episode

logger = Logger().get_logger()


def sanitize_for_xml(text):
    """Removes characters illegal in XML documents."""
    if not isinstance(text, str):
        return "" 
    sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
    return sanitized

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
    logger.debug(f"Generating feed for {pod.feed_id}")
    
    fg = FeedGenerator()
    fg.load_extension("podcast", atom=False, rss=True)
    fg.title(sanitize_for_xml(f"{pod.title}[{pod.keyword}]" if pod.keyword else pod.title))
    if pod.description:
        fg.description(sanitize_for_xml(pod.description))
    else:
        fg.description(sanitize_for_xml(pod.title))
    fg.link({"href": sanitize_for_xml(pod.link), "rel": "alternate"})
    fg.image(url=sanitize_for_xml(pod.cover_art), title=sanitize_for_xml(pod.title), link=sanitize_for_xml(pod.link))

    fg.podcast.itunes_category(sanitize_for_xml(pod.category), [sanitize_for_xml(sub) for sub in pod.subcategories] if pod.subcategories else [])
    fg.podcast.itunes_author(sanitize_for_xml(pod.author))

    matched_episodes: list[Episode] = []
    for episode in get_episode_list(pod):
        matches = episode_tbl.search(query_episode(episode))
        if not matches:
            logger.warning(f"Episode {episode.bvid} in pod {pod.feed_id} not found")
            continue
        else:
            full_episode = Episode.from_dict(matches[0])
            matched_episodes.append(full_episode)

    for episode in matched_episodes:
        if not episode.exists():
            logger.warning(f"Episode {episode.bvid} is not downloaded")
            continue

        pubdate = convert_timestamp_to_localtime(episode.pubdate)
        fe = fg.add_entry()
        fe.title(sanitize_for_xml(episode.title))
        fe.link({"href": sanitize_for_xml(episode.link), "rel": "alternate"})
        fe.description(sanitize_for_xml(episode.description))
        fe.guid(sanitize_for_xml(episode.bvid), permalink=False)
        fe.pubDate(pubdate)
        fe.enclosure(url=sanitize_for_xml(episode.url), length=episode.size, type=sanitize_for_xml(episode.type))

        fe.podcast.itunes_duration(episode.duration)
        fe.podcast.itunes_image(sanitize_for_xml(episode.image))
        fe.podcast.itunes_explicit(episode.explicit)

    feed_name = f"{pod.feed_id.replace('feed.', '', 1)}"

    try:
        fg.rss_file(
            filename=str(pod.data_dir / f"{feed_name}.xml"),
            pretty=True,
        )
    except Exception as e:
        logger.error(f"Failed to generate feed for {pod.feed_id}: {e}")
        # print all fg attributes to debug
        logger.debug(fg.__dict__)
        logger.debug(fg.rss_str(pretty=True))
        logger.debug(fg.atom_str(pretty=True))
        return
    else:
        logger.info(f"Generated feed for {feed_name}")
