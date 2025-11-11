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
    download_status = False
    try:
        v_obj = video.Video(episode.bvid, credential=credential)
        v_info = await v_obj.get_info()
    except ResponseCodeException as e:
        logger.error(f"Failed to get {episode.bvid} info: {e}")
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
            download_status = True

        except DownloadError as e:
            logger.debug(f"Attempt to download {episode.bvid} failed: {e}")
            return episode
        except RuntimeError as e:
            logger.error(f"Failed to download {episode.bvid}: {e}")
            return episode
        except Exception as e:
            logger.error(
                f"An unexpected error occurred when downloading {episode.bvid}: {e}"
            )

        try:
            await endorse(episode.endorse, v_obj, credential)
            logger.debug(f"Endorsed {episode.bvid}")
        except Exception as e:
            logger.error(f"Failed to endorse {episode.bvid}: {e}")

    if download_status:
        episode.status = "downloaded"  # Update status on successful download
        episode.set_size()
        logger.debug(f"Downloaded {episode.bvid} with size {episode.size}")
    episode.expand_description(v_info["dynamic"])


async def process_chunks(
    episodes: List[Episode], chunk_size, credential: Optional[Credential]
) -> List[Episode]:
    failed_downloads = []
    chunks = [
        episodes[i : min(i + chunk_size, len(episodes))]
        for i in range(0, len(episodes), chunk_size)
    ]
    for chunk in chunks:
        results = await asyncio.gather(
            *[download_episode(episode, credential) for episode in chunk]
        )
        failed_downloads.extend([episode for episode in results if episode is not None])
        await asyncio.sleep(5)  # Sleep between batches
    return failed_downloads


async def download_episodes(
    episode_list: Sequence[Episode],
    credential: Optional[Credential] = None,
    max_attempts: int = 3,
    chunk_size: int = 20,
):
    attempts = 0

    current_to_download = [
        episode for episode in list(episode_list) if not episode.status == "downloaded"
    ]

    while attempts < max_attempts and current_to_download:
        attempts += 1
        logger.debug(f"Attempt {attempts}/{max_attempts}")
        current_to_download = await process_chunks(
            current_to_download, chunk_size=chunk_size, credential=credential
        )

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
