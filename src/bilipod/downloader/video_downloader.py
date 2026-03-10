import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import Literal, Optional, Sequence, Tuple, Union

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
from ..utils.sponsorblock import invert_skip_segments

FFMPEG_PATH = "ffmpeg"
select_client("aiohttp")

logger = Logger().get_logger()


async def download_url(session, url: str, out: Path, name: str):
    try:
        async with session.get(url, headers=HEADERS) as resp:
            resp.raise_for_status()
            length = int(resp.headers.get("content-length", 0))
            with open(out, "wb") as f:
                process = 0
                next_report = 0
                block_size = 1024 * 1024
                async for chunk in resp.content.iter_chunked(block_size):
                    if not chunk:
                        break
                    process += len(chunk)
                    if process >= next_report or process == length:
                        logger.debug(
                            f"Downloading {name} {process/length:.1%} completed"
                        )
                        next_report += length // 5
                    f.write(chunk)
            if process != length:
                raise DownloadError("Incomplete download", url, process, length)
    except aiohttp.ClientResponseError as e:
        raise DownloadError("HTTP error", url, 0, 0) from e
    except aiohttp.ClientConnectorError as e:
        raise DownloadError("Connection error", url, 0, 0) from e


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


def format_ffmpeg_timestamp(seconds: float) -> str:
    return f"{seconds:.6f}".rstrip("0").rstrip(".")


def build_audio_trim_filter(keep_ranges: Sequence[Tuple[float, float]]) -> str:
    if len(keep_ranges) == 1:
        start, end = keep_ranges[0]
        return (
            "[0:a]"
            f"atrim=start={format_ffmpeg_timestamp(start)}:end={format_ffmpeg_timestamp(end)},"
            "asetpts=PTS-STARTPTS[outa]"
        )

    segments = []
    labels = []
    for index, (start, end) in enumerate(keep_ranges):
        segments.append(
            "[0:a]"
            f"atrim=start={format_ffmpeg_timestamp(start)}:end={format_ffmpeg_timestamp(end)},"
            f"asetpts=PTS-STARTPTS[a{index}]"
        )
        labels.append(f"[a{index}]")
    segments.append(
        f"{''.join(labels)}concat=n={len(keep_ranges)}:v=0:a=1[outa]"
    )
    return ";".join(segments)


def build_video_trim_filter(keep_ranges: Sequence[Tuple[float, float]]) -> str:
    if len(keep_ranges) == 1:
        start, end = keep_ranges[0]
        return ";".join(
            [
                "[0:v]"
                f"trim=start={format_ffmpeg_timestamp(start)}:end={format_ffmpeg_timestamp(end)},"
                "setpts=PTS-STARTPTS[outv]",
                "[0:a]"
                f"atrim=start={format_ffmpeg_timestamp(start)}:end={format_ffmpeg_timestamp(end)},"
                "asetpts=PTS-STARTPTS[outa]",
            ]
        )

    segments = []
    labels = []
    for index, (start, end) in enumerate(keep_ranges):
        segments.extend(
            [
                "[0:v]"
                f"trim=start={format_ffmpeg_timestamp(start)}:end={format_ffmpeg_timestamp(end)},"
                f"setpts=PTS-STARTPTS[v{index}]",
                "[0:a]"
                f"atrim=start={format_ffmpeg_timestamp(start)}:end={format_ffmpeg_timestamp(end)},"
                f"asetpts=PTS-STARTPTS[a{index}]",
            ]
        )
        labels.append(f"[v{index}][a{index}]")
    segments.append(
        f"{''.join(labels)}concat=n={len(keep_ranges)}:v=1:a=1[outv][outa]"
    )
    return ";".join(segments)


async def trim_media(
    input_path: Path,
    output_path: Path,
    format: Literal["video", "audio"],
    keep_ranges: Sequence[Tuple[float, float]],
) -> None:
    if not keep_ranges:
        raise RuntimeError("No keep ranges available after SponsorBlock trimming")

    if format == "audio":
        filter_complex = build_audio_trim_filter(keep_ranges)
        await run_ffmpeg(
            [
                "-y",
                "-i",
                str(input_path),
                "-filter_complex",
                filter_complex,
                "-map",
                "[outa]",
                "-acodec",
                "libmp3lame",
                "-q:a",
                "2",
                str(output_path),
            ]
        )
    else:
        filter_complex = build_video_trim_filter(keep_ranges)
        await run_ffmpeg(
            [
                "-y",
                "-i",
                str(input_path),
                "-filter_complex",
                filter_complex,
                "-map",
                "[outv]",
                "-map",
                "[outa]",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                str(output_path),
            ]
        )


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
    skip_segments: Optional[Sequence[Tuple[float, float]]] = None,
    source_duration: Optional[float] = None,
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

    async with aiohttp.ClientSession() as session:
        tempdir = tempfile.TemporaryDirectory()
        tempdir_path = Path(tempdir.name)
        suffix = "mp3" if format == "audio" else "mp4"
        trim_requested = bool(skip_segments) and source_duration is not None
        if skip_segments and source_duration is None:
            logger.warning(
                f"SponsorBlock segments found for {name} but source duration is unavailable; keeping original media."
            )
        render_outfile = (
            tempdir_path / f"{name}_assembled.{suffix}" if trim_requested else outfile
        )

        # flv stream
        if v_detecter.check_flv_mp4_stream() is True:
            if isinstance(streams[0], video.FLVStreamDownloadURL):
                temp_flv = tempdir_path / f"{name}_flv_temp.flv"
                await download_url(
                    session, streams[0].url, temp_flv, f"{name} FLV stream"
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
                            str(render_outfile),
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
                            str(render_outfile),
                        ]
                    )
                else:
                    pass

            # html5 mp4 stream
            else:
                temp_mp4 = tempdir_path / f"{name}_mp4_temp.mp4"
                await download_url(
                    session, streams[0].url, temp_mp4, f"{name} HTML5 MP4 stream"
                )
                if format == "video":
                    # copy temp_mp4 to outfile
                    shutil.copy(temp_mp4, render_outfile)
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
                            str(render_outfile),
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
                        str(render_outfile),
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
                        str(render_outfile),
                    ]
                )
            else:
                pass

        if trim_requested:
            keep_ranges = invert_skip_segments(
                skip_segments, duration=float(source_duration)
            )
            if keep_ranges:
                try:
                    await trim_media(render_outfile, outfile, format, keep_ranges)
                except Exception as e:
                    logger.warning(
                        f"SponsorBlock trimming failed for {name}, keeping original media: {e}"
                    )
                    shutil.copy(render_outfile, outfile)
            else:
                logger.warning(
                    f"SponsorBlock removed all content for {name}, keeping original media."
                )
                shutil.copy(render_outfile, outfile)

        tempdir.cleanup()
