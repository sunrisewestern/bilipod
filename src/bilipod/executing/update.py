import asyncio
import threading
import time

from bilibili_api import Credential
from tinydb import Query, table

from bp_class import Pod
from downloader import download_episodes
from feed import generate_feed_xml, generate_opml  # noqa: F401
from utils.biliuser import get_episode_list, get_pod_info
from utils.bp_log import Logger
from utils.db_query import query_episode

from .clean import clean_untracked_episodes

logger = Logger().get_logger()

max_delay = 5 * 60
episode_tbl_lock = threading.Lock()
update_event = asyncio.Event()


async def update_pod(pod: Pod, pod_tbl: table.Table, credential: Credential):
    updated_pod_info = await get_pod_info(
        uid=pod.uid,
        credential=credential,
        page_size=Pod.page_size,
        keyword=Pod.keyword,
    )

    pod.episodes = updated_pod_info["episodes"]
    pod.update_at = time.time()
    # update eposide list in pod_tbl, query only by feed_id
    pod_tbl.update(
        {"episodes": pod.episodes, "update_at": pod.update_at},
        Query().feed_id == pod.feed_id,
    )

    update_event.set()

    logger.info(f"Pod {pod.feed_id} updated")


async def update_episodes(
    pod_tbl: table.Table, episode_tbl: table.Table, credential: Credential
):
    while True:
        logger.debug("Waiting for update signal...")
        await update_event.wait()
        logger.debug("Update signal received.")

        await asyncio.sleep(max_delay)

        update_event.clear()
        logger.debug("Event cleared, fetching updated podcasts.")

        # Fetch updated pods from pod_tbl
        updated_pods = [
            Pod(**pod_info)
            for pod_info in pod_tbl.search(
                Query().updated_at >= time.time() - max_delay
            )
        ]

        # gather the episode list to download
        episode_to_update = []
        for pod in updated_pods:
            episode_list = get_episode_list(pod)
            for episode in episode_list:
                if episode_tbl.search(query_episode(episode)):
                    continue
                else:
                    episode_to_update.append(episode)

        if episode_to_update:
            logger.debug(f"Episodes to update: {episode_to_update}")
            await download_episodes(episode_to_update, credential=credential)

            # update episode list in episode_tbl
            episode_tbl.insert_multiple(
                [episode.to_dict() for episode in set(episode_list)]
            )

            # update feed xml
            for pod in updated_pods:
                generate_feed_xml(pod=pod, episode_tbl=episode_tbl)
                logger.info(f"Feed {pod.feed_id} updated.")

            clean_untracked_episodes(pod_tbl, episode_tbl)

        else:
            logger.info("No episodes to update.")
