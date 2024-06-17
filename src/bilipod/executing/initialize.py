import asyncio
import time

from bilibili_api import Credential
from tinydb import table

from bp_class import Pod
from downloader import download_episodes
from feed import generate_feed_xml, generate_opml
from utils.biliuser import get_episode_list, get_pod_info
from utils.bp_log import Logger
from utils.config_parser import BiliPodConfig

from .clean import clean_unused_episodes, clean_unused_rss

logger = Logger().get_logger()


async def data_initialize(
    config: BiliPodConfig,
    pod_tbl: table.Table,
    episode_tbl: table.Table,
    credential: Credential,
) -> None:

    # base_url
    if config.server.hostname is None:
        base_url = f"{'https' if config.server.tls else 'http'}://{config.server.bind_address}:{config.server.port}"
    else:
        base_url = f"{config.server.hostname}/{config.server.path}"

    # init pod list
    for feed_id, feed_config in config.feeds.items():
        logger.info(f"Initializing feed: {feed_id}...")
        await asyncio.sleep(0.5)

        # init pod
        pod = Pod(
            feed_id=feed_id,
            data_dir=config.storage.data_dir,
            base_url=base_url,
            **feed_config.to_dict(),
        )

        # get user info and video list
        pod_info = await get_pod_info(
            uid=pod.uid,
            credential=credential,
            page_size=pod.page_size,
            keyword=pod.keyword,
        )
        pod.update(**pod_info)
        pod.update_at = time.time()
        pod_tbl.insert(pod.to_dict())

    # init episode list
    episode_list = []
    for pod_info in pod_tbl.all():
        pod = Pod.from_dict(pod_info)
        pod_episode_list = get_episode_list(pod)
        episode_list.extend(pod_episode_list)

    logger.info(f"Initializing download, {len(episode_list)} episodes found.")
    await download_episodes(episode_list, credential=credential)

    episode_tbl.insert_multiple([episode.to_dict() for episode in set(episode_list)])

    # init feed xml
    for pod_info in pod_tbl.all():
        pod = Pod.from_dict(pod_info)
        generate_feed_xml(pod=pod, episode_tbl=episode_tbl)

    generate_opml(pod_tbl=pod_tbl, filename=f"{config.storage.data_dir}/podcast.opml")

    clean_unused_rss(pod_tbl, config.storage.data_dir)
    clean_unused_episodes(episode_tbl, config.storage.data_dir)
