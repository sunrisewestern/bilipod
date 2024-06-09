from pathlib import Path

from tinydb import Query, table

from bp_class import Episode, Pod
from utils.biliuser import get_episode_list
from utils.bp_log import Logger
from utils.db_query import query_episode

logger = Logger().get_logger()


def clean_episodes(episode_tbl: table.Table, data_dir: Path):
    media_dir = Path(data_dir) / "media"
    for media in media_dir.iterdir():
        if media.is_file():
            query = episode_tbl.search(Query().location == str(media))
            if not query:
                media.unlink()
                logger.debug(f"Deleted unused episode: {media}")


def clean_untracked_episodes(
    pod_tbl: table.Table,
    episode_tbl: table.Table,
):
    episode_tbl.update({"on_track": False})
    for pod_info in pod_tbl.all():
        pod = Pod.from_dict(pod_info)
        for episode in get_episode_list(pod):
            episode_tbl.update({"on_track": True}, query_episode(episode))

    for episode_info in episode_tbl.search(Query().on_track == False):  # noqa E712
        episode = Episode.from_dict(episode_info)
        try:
            episode.clean()
            episode_tbl.update({"status": "deleted"}, query_episode(episode))
        except FileNotFoundError as e:
            logger.error(e)
            episode_tbl.update({"status": "deleted"}, query_episode(episode))
    logger.debug("Cleaned untracked episodes.")


def clean_unused_rss(pod_tbl: table.Table, data_dir):
    data_dir = Path(data_dir)
    for filename in data_dir.glob("*.xml"):
        feed_id1 = filename.stem
        feed_id2 = f"feed.{filename.stem}"
        if not pod_tbl.search(Query().feed_id.one_of([feed_id1, feed_id2])):
            filename.unlink()
            logger.debug(f"Deleted unused RSS file: {filename.stem}")
