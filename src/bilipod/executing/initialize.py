import asyncio
import time
from pathlib import Path

from bilibili_api import Credential
from tinydb import Query, table

from ..bp_class import Episode, Pod
from ..downloader import download_episodes
from ..feed import generate_feed_xml, generate_opml
from ..utils.biliuser import get_episode_list, get_pod_info
from ..utils.bp_log import Logger
from ..utils.config_parser import BiliPodConfig, FeedConfig, ServerConfig
from ..utils.db_query import query_episode
from .clean import clean_unused_episodes, clean_unused_rss

logger = Logger().get_logger()


def build_base_url(server_config: ServerConfig) -> str:
    if server_config.hostname is None:
        return (
            f"{'https' if server_config.tls else 'http'}://"
            f"{server_config.bind_address}:{server_config.port}"
        )
    return f"{server_config.hostname}/{server_config.path}"


async def initialize_feed_pod(
    feed_id: str,
    feed_config: FeedConfig,
    server_config: ServerConfig,
    data_dir: Path | str,
    pod_tbl: table.Table,
    credential: Credential,
) -> Pod:
    logger.info(f"Initializing feed: {feed_id}...")
    await asyncio.sleep(0.5)

    pod = Pod(
        feed_id=feed_id,
        data_dir=data_dir,
        base_url=build_base_url(server_config),
        uid=feed_config.uid,
        sid=feed_config.sid,
        fid=feed_config.fid,
        playlist_type=feed_config.playlist_type,
        page_size=feed_config.page_size,
        keyword=feed_config.keyword,
        playlist_sort=feed_config.playlist_sort,
    )
    pod_info = await get_pod_info(
        uid=feed_config.uid,
        sid=feed_config.sid,
        fid=feed_config.fid,
        playlist_type=feed_config.playlist_type,
        credential=credential,
        page_size=feed_config.page_size,
        keyword=pod.keyword,
        playlist_sort=feed_config.playlist_sort,
    )

    pod.update(**pod_info)
    pod.update(**{k: v for k, v in feed_config.to_dict().items() if v is not None})
    pod.update_at = time.time()
    pod_tbl.upsert(pod.to_dict(), Query().feed_id == feed_id)
    return pod


def _episode_needs_download(episode: Episode, episode_tbl: table.Table) -> bool:
    matches = episode_tbl.search(query_episode(episode))
    if not matches:
        return True

    stored_episode = Episode.from_dict(matches[0])
    return stored_episode.status != "downloaded" or not stored_episode.exists()


def _upsert_episodes(episode_list: list[Episode], episode_tbl: table.Table) -> None:
    for episode in episode_list:
        episode_tbl.upsert(episode.to_dict(), query_episode(episode))


async def initialize_or_update_feed(
    feed_id: str,
    feed_config: FeedConfig,
    server_config: ServerConfig,
    data_dir: Path | str,
    pod_tbl: table.Table,
    episode_tbl: table.Table,
    credential: Credential,
) -> Pod:
    pod = await initialize_feed_pod(
        feed_id=feed_id,
        feed_config=feed_config,
        server_config=server_config,
        data_dir=data_dir,
        pod_tbl=pod_tbl,
        credential=credential,
    )

    episode_list = list(set(get_episode_list(pod)))
    episode_to_update = [
        episode
        for episode in episode_list
        if _episode_needs_download(episode, episode_tbl)
    ]

    if episode_to_update:
        logger.info(
            f"Downloading {len(episode_to_update)} episodes for feed {feed_id}."
        )
        await download_episodes(
            episode_to_update, credential=credential, max_attempts=10
        )
        _upsert_episodes(episode_to_update, episode_tbl)

    generate_feed_xml(pod=pod, episode_tbl=episode_tbl)
    return pod


async def data_initialize(
    config: BiliPodConfig,
    pod_tbl: table.Table,
    episode_tbl: table.Table,
    credential: Credential,
) -> None:

    for feed_id, feed_config in config.feeds.items():
        await initialize_feed_pod(
            feed_id=feed_id,
            feed_config=feed_config,
            server_config=config.server,
            data_dir=config.storage.data_dir,
            pod_tbl=pod_tbl,
            credential=credential,
        )

    # init episode list
    episode_list = []
    for pod_info in pod_tbl.all():
        pod = Pod.from_dict(pod_info)
        pod_episode_list = get_episode_list(pod)
        episode_list.extend(pod_episode_list)

    logger.info(f"Initializing download, {len(episode_list)} episodes found.")
    if episode_list:
        await download_episodes(episode_list, credential=credential, max_attempts=10)

    if episode_list:
        episode_tbl.insert_multiple(
            [episode.to_dict() for episode in set(episode_list)]
        )

    # init feed xml
    for pod_info in pod_tbl.all():
        pod = Pod.from_dict(pod_info)
        generate_feed_xml(pod=pod, episode_tbl=episode_tbl)

    generate_opml(
        pod_tbl=pod_tbl,
        filename=f"{config.storage.data_dir}/podcast.opml",
    )

    clean_unused_rss(pod_tbl, config.storage.data_dir)
    clean_unused_episodes(episode_tbl, config.storage.data_dir)
