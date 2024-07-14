import asyncio
from typing import List, Optional, Sequence

from bilibili_api import Credential, ResponseCodeException, video

from ..bp_class import Episode
from ..exceptions.DownloadError import DownloadError
from ..utils.bp_log import Logger
from ..utils.endorse import endorse
from .video_downloader import video_downloader

logger = Logger().get_logger()


async def download_episode(
    episode: Episode, credential: Optional[Credential]
) -> Optional[Episode]:
    """
    Download an episode and update info of the episode object
    """
    try:
        v_obj = video.Video(episode.bvid, credential=credential)
        v_info = await v_obj.get_info()
    except ResponseCodeException as e:
        logger.error(f"Failed to download {episode.bvid}: {e}")
        return episode

    if episode.exists():
        logger.debug(f"Episode {episode.bvid} already exists.")
    else:
        try:
            await video_downloader(
                name=episode.bvid,
                video_obj=v_obj,
                outfile=episode.location,
                format=episode.format,
                video_quality=episode.video_quality,
                audio_quality=episode.audio_quality,
                credential=credential,
            )
            
            try:
                await endorse(episode.endorse, v_obj, credential)
            except Exception as e:
                logger.error(f"Failed to endorse {episode.bvid}: {e}")
            
        except DownloadError as e:
            logger.debug(f"Attempt to download {episode.bvid} failed: {e}")
            return episode

    episode.status = "downloaded"  # Update status on successful download
    episode.set_size()
    logger.debug(f"Downloaded {episode.bvid} with size {episode.size}")
    episode.expand_description(v_info["dynamic"])


async def process_chunks(
    episodes: List[Episode], credential: Optional[Credential]
) -> List[Episode]:
    failed_downloads = []
    chunks = [episodes[i : i + 10] for i in range(0, len(episodes), 10)]
    for chunk in chunks:
        results = await asyncio.gather(
            *[download_episode(episode, credential) for episode in chunk]
        )
        failed_downloads.extend([episode for episode in results if episode is not None])
        await asyncio.sleep(10)  # Sleep for 10 seconds between batches
    return failed_downloads


async def download_episodes(
    episode_list: Sequence[Episode],
    credential: Optional[Credential] = None,
    max_attempts: int = 3,
):
    attempts = 0

    current_to_download = [
        episode for episode in list(episode_list) if episode.status != "downloaded"
    ]

    while attempts < max_attempts and current_to_download:
        attempts += 1
        logger.debug(f"Attempt {attempts}/{max_attempts}")
        current_to_download = await process_chunks(current_to_download, credential)

    # Optionally handle the failed downloads after all retries
    if current_to_download:
        logger.error(
            "Episodes failed to download after all retries:",
            [episode.bvid for episode in current_to_download],
        )
        logger.info(
            f" {len(episode_list) - len(current_to_download)} episodes downloaded successfully."
        )
    else:
        logger.info(f" {len(episode_list)} episodes downloaded successfully.")
