import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import Literal, Union

import httpx
from bilibili_api import HEADERS, Credential, ResponseCodeException, video

from ..exceptions.DownloadError import DownloadError
from ..utils.bp_log import Logger

FFMPEG_PATH = "ffmpeg"

logger = Logger().get_logger()


async def download_url(session, url: str, out: Path, name: str):
    try:
        resp = await session.get(url)
        resp.raise_for_status()
        length = int(resp.headers.get("content-length", 0))
        with open(out, "wb") as f:
            process = 0
            next_report = 0
            async for chunk in resp.aiter_bytes(1024):
                if not chunk:
                    break
                process += len(chunk)
                if process >= next_report or process == length:
                    logger.debug(f"Downloading {name} {process/length:.1%} completed")
                    next_report += length // 10
                f.write(chunk)
        if process != length:
            raise DownloadError("Incomplete download", url, process, length)
    except httpx.HTTPStatusError as e:
        raise DownloadError("HTTP error", url, 0, 0) from e
    except httpx.RequestError as e:
        raise DownloadError("Request error", url, 0, 0) from e


async def run_ffmpeg(args):
    process = await asyncio.create_subprocess_exec(
        FFMPEG_PATH,
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        # logger.error(f"FFmpeg error: {stderr.decode()}")
        raise RuntimeError(f"FFmpeg error: {stderr.decode()}")


async def video_downloader(
    name: str,
    video_obj: video.Video,
    outfile: Union[str, Path],
    credential: Union[Credential, None] = None,
    format: Literal["video", "audio"] = "audio",
    video_quality: Literal[
        "360P",
        "480P",
        "720P",
        "1080P",
        "1080P_PLUS",
        "1080P_60",
        "4K",
        "HDR",
        "DOLBY",
        "8K",
    ] = "1080P",
    audio_quality: Literal["64K", "132K", "192K", "HI_RES", "DOLBY"] = "192K",
) -> None:
    """
    Get video download url

    Args:
        name (str) : video name

        video_obj (video.Video) : video object

        outfile (Union[str, Path]) : output file path

        credential (Credential, optional) : user credential. Defaults to None.

        video_quality (Literal["360P", "480P", "720P", "1080P", "1080P_PLUS", "1080P_60", "4K", "HDR", "DOLBY", "8K"], optional) : video quality. Defaults to "1080P".

        audio_quality (Literal["64K", "132K", "192K", "HI_RES", "DOLBY"], optional) : audio quality. Defaults to "192K".

        format (Literal["video", "audio"], optional) : download format. Defaults to "audio".
    """
    if format not in ["video", "audio"]:
        raise ValueError("format must be 'video', 'audio'")

    try:
        v_url_data = await video_obj.get_download_url(0)
    except ResponseCodeException:
        logger.debug(f"Failed to get video {name}, skipping.")
        return None

    v_detecter = video.VideoDownloadURLDataDetecter(v_url_data)
    streams = v_detecter.detect_best_streams(
        video_max_quality=getattr(video.VideoQuality, f"_{video_quality}"),
        audio_max_quality=getattr(video.AudioQuality, f"_{audio_quality}"),
    )

    outfile = Path(outfile)

    async with httpx.AsyncClient(headers=HEADERS) as session:
        tempdir = tempfile.TemporaryDirectory()
        tempdir_path = Path(tempdir.name)

        # flv stream
        if v_detecter.check_flv_stream() is True:
            temp_flv = tempdir_path / f"{name}_flv_temp.flv"
            await download_url(session, streams[0].url, temp_flv, f"{name} FLV stream")
            if format == "video":
                await run_ffmpeg(
                    [
                        "-y",
                        "-i",
                        temp_flv,
                        "-vcodec",
                        "copy",
                        "-acodec",
                        "copy",
                        str(outfile),
                    ]
                )
            elif format == "audio":
                await run_ffmpeg(
                    [
                        "-y",
                        "-i",
                        temp_flv,
                        "-vn",
                        "-acodec",
                        "copy",
                        str(outfile),
                    ]
                )
            else:
                pass
        
        # html5 mp4 stream
        elif (
            v_detecter.check_html5_mp4_stream() is True
            or v_detecter.check_episode_try_mp4_stream() is True
        ):
            temp_mp4 = tempdir_path / f"{name}_mp4_temp.mp4"
            await download_url(
                session, streams[0].url, temp_mp4, f"{name} HTML5 MP4 stream"
            )
            if format == "video":
                # copy temp_mp4 to outfile
                shutil.copy(temp_mp4, outfile)
            elif format == "audio":
                await run_ffmpeg(
                    [
                        "-y",
                        "-i",
                        temp_mp4,
                        "-vn",
                        "-acodec",
                        "libmp3lame",
                        "-q:a",
                        "2",
                        str(outfile),
                    ]
                )
        else:
            # mp4 stream
            temp_audio = tempdir_path / f"{name}_audio_temp.m4s"
            temp_video = tempdir_path / f"{name}_video_temp.m4s"
            if format == "video":

                await asyncio.gather(
                    download_url(
                        session, streams[0].url, temp_video, f"{name} Video stream"
                    ),
                    download_url(
                        session, streams[1].url, temp_audio, f"{name} Audio stream"
                    ),
                )
                # merge
                await run_ffmpeg(
                    [
                        "-y",
                        "-i",
                        temp_video,
                        "-i",
                        temp_audio,
                        "-vcodec",
                        "copy",
                        "-acodec",
                        "copy",
                        str(outfile),
                    ]
                )
            elif format == "audio":
                await download_url(
                    session, streams[1].url, temp_audio, f"{name} Audio stream"
                )
                await run_ffmpeg(
                    [
                        "-y",
                        "-i",
                        temp_audio,
                        "-vn",
                        "-acodec",
                        "libmp3lame",
                        str(outfile),
                    ]
                )
            else:
                pass

        tempdir.cleanup()
