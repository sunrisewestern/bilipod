import asyncio
import shutil
import tempfile
from collections.abc import MutableMapping, Sequence
from pathlib import Path
from typing import List, Literal, Union

import aiohttp
from bilibili_api import (
    HEADERS,
    Credential,
    ResponseCodeException,
    select_client,
    video,
)

from ..exceptions.DownloadError import DownloadError
from ..utils.bp_log import Logger

FFMPEG_PATH = "ffmpeg"
DOWNLOAD_TIMEOUT = aiohttp.ClientTimeout(total=None, sock_connect=30, sock_read=30)
select_client("aiohttp")

logger = Logger().get_logger()


def normalize_video_codecs(v_url_data: MutableMapping) -> None:
    dash = v_url_data.get("dash")
    if not isinstance(dash, MutableMapping):
        return

    for stream in dash.get("video") or []:
        if not isinstance(stream, MutableMapping):
            continue

        codecs = stream.get("codecs")
        if not isinstance(codecs, str):
            continue

        codec_name = codecs.split(".", 1)[0].lower()
        if (
            codec_name in {"hvc1", "hev1"}
            and video.VideoCodecs.HEV.value not in codecs
        ):
            # bilibili_api matches HEVC by "hev", but Bilibili may return hvc1/hev1.
            stream["codecs"] = f"{video.VideoCodecs.HEV.value}.{codecs}"


def dedupe_urls(urls: Sequence) -> List[str]:
    result = []
    for url in urls:
        if url and url not in result:
            result.append(url)
    return result


def extract_stream_urls(stream_data: MutableMapping) -> List[str]:
    urls = [
        stream_data.get("url"),
        stream_data.get("baseUrl"),
        stream_data.get("base_url"),
    ]
    backup_urls = stream_data.get("backupUrl") or stream_data.get("backup_url") or []
    if isinstance(backup_urls, str):
        urls.append(backup_urls)
    else:
        urls.extend(backup_urls)
    return dedupe_urls([url for url in urls if isinstance(url, str)])


def get_stream_urls(v_url_data: MutableMapping, stream) -> List[str]:
    stream_url = getattr(stream, "url", None)
    if not stream_url:
        return []

    if isinstance(stream, (video.FLVStreamDownloadURL, video.MP4StreamDownloadURL)):
        for stream_data in v_url_data.get("durl") or []:
            if not isinstance(stream_data, MutableMapping):
                continue
            urls = extract_stream_urls(stream_data)
            if stream_url in urls:
                return urls

    dash = v_url_data.get("dash") or {}
    if not isinstance(dash, MutableMapping):
        return [stream_url]

    stream_data_candidates = []
    if isinstance(stream, video.VideoStreamDownloadURL):
        stream_data_candidates.extend(dash.get("video") or [])
    elif isinstance(stream, video.AudioStreamDownloadURL):
        stream_data_candidates.extend(dash.get("audio") or [])
        flac_data = dash.get("flac") or {}
        if isinstance(flac_data, MutableMapping) and flac_data.get("audio"):
            stream_data_candidates.append(flac_data["audio"])
        dolby_data = dash.get("dolby") or {}
        dolby_audio = (
            dolby_data.get("audio") if isinstance(dolby_data, MutableMapping) else None
        )
        if isinstance(dolby_audio, list):
            stream_data_candidates.extend(dolby_audio)
        elif dolby_audio:
            stream_data_candidates.append(dolby_audio)

    for stream_data in stream_data_candidates:
        if not isinstance(stream_data, MutableMapping):
            continue
        urls = extract_stream_urls(stream_data)
        if stream_url in urls:
            return urls

    return [stream_url]


async def download_url(
    session,
    urls: Union[str, Sequence],
    out: Path,
    name: str,
    max_attempts: int = 3,
):
    url_options = [urls] if isinstance(urls, str) else dedupe_urls(urls)
    if not url_options:
        raise DownloadError("No download URL", "", 0, 0)

    last_error = None
    last_cause = None
    for url_index, url in enumerate(url_options, start=1):
        for attempt in range(1, max_attempts + 1):
            process = 0
            length = 0
            try:
                if out.exists():
                    out.unlink()

                async with session.get(
                    url, headers=HEADERS, timeout=DOWNLOAD_TIMEOUT
                ) as resp:
                    resp.raise_for_status()
                    length = int(resp.headers.get("content-length", 0))
                    with open(out, "wb") as f:
                        next_report = 0
                        block_size = 1024 * 1024
                        async for chunk in resp.content.iter_chunked(block_size):
                            if not chunk:
                                break
                            process += len(chunk)
                            if length and (
                                process >= next_report or process == length
                            ):
                                logger.debug(
                                    f"Downloading {name} "
                                    f"{process/length:.1%} completed"
                                )
                                next_report += max(length // 5, block_size)
                            f.write(chunk)
                    if length and process != length:
                        raise DownloadError(
                            "Incomplete download", url, process, length
                        )
                return
            except DownloadError as e:
                error = e
                cause = None
            except aiohttp.ClientResponseError as e:
                error = DownloadError("HTTP error", url, process, length)
                cause = e
            except aiohttp.ClientConnectorError as e:
                error = DownloadError("Connection error", url, process, length)
                cause = e
            except aiohttp.ClientPayloadError as e:
                error = DownloadError("Incomplete response", url, process, length)
                cause = e
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as e:
                error = DownloadError("Network error", url, process, length)
                cause = e

            last_error = error
            last_cause = cause
            if attempt == max_attempts and url_index == len(url_options):
                if cause is not None:
                    raise error from cause
                raise error
            if attempt == max_attempts:
                logger.debug(
                    f"Downloading {name} failed after {max_attempts} attempts: "
                    f"{error}. Trying backup URL {url_index + 1}/{len(url_options)}..."
                )
                break

            logger.debug(
                f"Downloading {name} failed on attempt {attempt}/{max_attempts}: "
                f"{error}. Retrying..."
            )
            await asyncio.sleep(min(2**attempt, 10))

    if last_error is not None:
        if last_cause is not None:
            raise last_error from last_cause
        raise last_error


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

    normalize_video_codecs(v_url_data)
    v_detecter = video.VideoDownloadURLDataDetecter(v_url_data)
    streams = v_detecter.detect_best_streams(
        video_max_quality=getattr(video.VideoQuality, f"_{video_quality}"),
        audio_max_quality=getattr(video.AudioQuality, f"_{audio_quality}"),
    )

    outfile = Path(outfile)

    async with aiohttp.ClientSession() as session:
        tempdir = tempfile.TemporaryDirectory()
        tempdir_path = Path(tempdir.name)

        # flv stream
        if v_detecter.check_flv_mp4_stream() is True:
            if isinstance(streams[0], video.FLVStreamDownloadURL):
                temp_flv = tempdir_path / f"{name}_flv_temp.flv"
                await download_url(
                    session,
                    get_stream_urls(v_url_data, streams[0]),
                    temp_flv,
                    f"{name} FLV stream",
                )
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
            else:
                temp_mp4 = tempdir_path / f"{name}_mp4_temp.mp4"
                await download_url(
                    session,
                    get_stream_urls(v_url_data, streams[0]),
                    temp_mp4,
                    f"{name} HTML5 MP4 stream",
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
                        session,
                        get_stream_urls(v_url_data, streams[0]),
                        temp_video,
                        f"{name} Video stream",
                    ),
                    download_url(
                        session,
                        get_stream_urls(v_url_data, streams[1]),
                        temp_audio,
                        f"{name} Audio stream",
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
                    session,
                    get_stream_urls(v_url_data, streams[1]),
                    temp_audio,
                    f"{name} Audio stream",
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
