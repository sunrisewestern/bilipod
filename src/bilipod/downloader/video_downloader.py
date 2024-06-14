import tempfile
from pathlib import Path
from subprocess import run
from typing import Literal, Union

import httpx
from bilibili_api import HEADERS, Credential, ResponseCodeException, video

from exceptions.DownloadError import DownloadError
from utils.bp_log import Logger

FFMPEG_PATH = "ffmpeg"

logger = Logger().get_logger()


async def download_url(url: str, out: Path, info: str):
    try:
        async with httpx.AsyncClient(headers=HEADERS) as sess:
            resp = await sess.get(url)
            length = int(resp.headers.get("content-length"))
            with open(out, "wb") as f:
                process = 0
                next_report = 0

                for chunk in resp.iter_bytes(1024):
                    if not chunk:
                        break
                    process += len(chunk)

                    if process >= next_report or process == length:
                        logger.debug(
                            f"Downloading {info} {process/length:.1%} completed"
                        )
                        next_report += length // 10

                    f.write(chunk)

                if process != length:
                    raise DownloadError("Incomplete download", url, process, length)

    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        raise DownloadError("Request error", url, 0, 0) from e


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

    tempdir = tempfile.TemporaryDirectory()

    tempdir_path = Path(tempdir.name)

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
    if outfile.exists():
        logger.debug(f"File {outfile} already exists, skipping.")

    # flv stream
    if v_detecter.check_flv_stream() is True:
        temp_flv = tempdir_path / f"{name}_flv_temp.flv"
        await download_url(streams[0].url, temp_flv, f"{name} FLV stream")
        if format == "video":
            run(
                args=[
                    FFMPEG_PATH,
                    "-y",
                    "-i",
                    temp_flv,
                    "-vcodec",
                    "copy",
                    "-acodec",
                    "copy",
                    outfile,
                ]
            )
        elif format == "audio":
            run(
                args=[
                    FFMPEG_PATH,
                    "-y",
                    "-i",
                    temp_flv,
                    "-vn",
                    "-acodec",
                    "copy",
                    outfile,
                ]
            )
        else:
            pass
    else:
        # mp4 stream
        temp_audio = tempdir_path / f"{name}_audio_temp.m4s"
        temp_video = tempdir_path / f"{name}_video_temp.m4s"
        if format == "video":
            await download_url(streams[0].url, temp_video, f"{name} Video stream")
            await download_url(streams[1].url, temp_audio, f"{name} Audio stream")
            # merge
            run(
                args=[
                    FFMPEG_PATH,
                    "-y",
                    "-i",
                    temp_video,
                    "-i",
                    temp_audio,
                    "-vcodec",
                    "copy",
                    "-acodec",
                    "copy",
                    outfile,
                ]
            )
        elif format == "audio":
            await download_url(streams[1].url, temp_audio, f"{name} Audio stream")

            run(
                args=[
                    FFMPEG_PATH,
                    "-y",
                    "-i",
                    temp_audio,
                    "-vn",
                    "-acodec",
                    "libmp3lame",
                    outfile,
                ]
            )
        else:
            pass

    tempdir.cleanup()
