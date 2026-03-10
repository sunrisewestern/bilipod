import asyncio
from typing import List, Optional, Sequence

from bilibili_api import Credential, ResponseCodeException, video

from ..bp_class import Episode
from ..exceptions.DownloadError import DownloadError
from ..utils.bp_log import Logger
from ..utils.config_parser import SponsorBlockConfig
from ..utils.endorse import endorse
from ..utils.sponsorblock import get_skip_segments
from .video_downloader import video_downloader

logger = Logger().get_logger()


async def download_episode(
    episode: Episode,
    credential: Optional[Credential],
    sponsorblock: SponsorBlockConfig,
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
        pages = v_info.get("pages") or []
        first_page = pages[0] if pages else {}
        cid = first_page.get("cid") or v_info.get("cid")
        source_duration = first_page.get("duration") or v_info.get("duration")
        skip_segments = []

        if sponsorblock.enabled:
            try:
                skip_segments = await get_skip_segments(
                    video_id=episode.bvid,
                    cid=cid,
                    duration=source_duration,
                    config=sponsorblock,
                )
            except Exception as e:
                logger.warning(
                    f"SponsorBlock lookup failed for {episode.bvid}, continuing without trimming: {e}"
                )
            else:
                if skip_segments:
                    logger.info(
                        f"Found {len(skip_segments)} SponsorBlock segment(s) for {episode.bvid}"
                    )

        try:
            await video_downloader(
                name=episode.bvid,
                video_obj=v_obj,
                outfile=episode.location,
                format=episode.format,
                video_quality=episode.video_quality,
                audio_quality=episode.audio_quality,
                credential=credential,
                skip_segments=skip_segments,
                source_duration=source_duration,
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
    episodes: List[Episode],
    chunk_size,
    credential: Optional[Credential],
    sponsorblock: SponsorBlockConfig,
) -> List[Episode]:
    failed_downloads = []
    chunks = [
        episodes[i : min(i + chunk_size, len(episodes))]
        for i in range(0, len(episodes), chunk_size)
    ]
    for chunk in chunks:
        results = await asyncio.gather(
            *[
                download_episode(episode, credential, sponsorblock=sponsorblock)
                for episode in chunk
            ]
        )
        failed_downloads.extend([episode for episode in results if episode is not None])
        await asyncio.sleep(5)  # Sleep between batches
    return failed_downloads


async def download_episodes(
    episode_list: Sequence[Episode],
    credential: Optional[Credential] = None,
    sponsorblock: Optional[SponsorBlockConfig] = None,
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
            current_to_download,
            chunk_size=chunk_size,
            credential=credential,
            sponsorblock=sponsorblock or SponsorBlockConfig(),
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
