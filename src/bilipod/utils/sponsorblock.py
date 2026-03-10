import logging
from typing import TYPE_CHECKING, Iterable, List, Optional, Sequence, Tuple

if TYPE_CHECKING:
    from .config_parser import SponsorBlockConfig

DEFAULT_ORIGIN = "chrome-extension://eaoelafamejbnggahofapllmfhlhajdd"
DEFAULT_EXTENSION_VERSION = "0.5.0"


def get_logger():
    try:
        from .bp_log import Logger
    except Exception:
        return logging.getLogger(__name__)
    return Logger().get_logger()


def normalize_skip_segments(
    segments: Iterable[Tuple[float, float]],
    duration: Optional[float] = None,
    merge_gap: float = 0.05,
) -> List[Tuple[float, float]]:
    normalized: List[Tuple[float, float]] = []
    for start, end in segments:
        start = max(0.0, float(start))
        end = max(0.0, float(end))
        if duration is not None:
            start = min(start, duration)
            end = min(end, duration)
        if end <= start:
            continue
        normalized.append((start, end))

    if not normalized:
        return []

    normalized.sort()
    merged: List[Tuple[float, float]] = [normalized[0]]
    for start, end in normalized[1:]:
        previous_start, previous_end = merged[-1]
        if start <= previous_end + merge_gap:
            merged[-1] = (previous_start, max(previous_end, end))
        else:
            merged.append((start, end))
    return merged


def invert_skip_segments(
    segments: Sequence[Tuple[float, float]],
    duration: float,
    min_segment_length: float = 0.1,
) -> List[Tuple[float, float]]:
    if duration <= 0:
        return []

    keep_ranges: List[Tuple[float, float]] = []
    cursor = 0.0
    for start, end in normalize_skip_segments(segments, duration=duration):
        if start - cursor >= min_segment_length:
            keep_ranges.append((cursor, start))
        cursor = max(cursor, end)

    if duration - cursor >= min_segment_length:
        keep_ranges.append((cursor, duration))

    return keep_ranges


async def get_skip_segments(
    video_id: str,
    cid: Optional[int],
    duration: Optional[float],
    config: "SponsorBlockConfig",
) -> List[Tuple[float, float]]:
    logger = get_logger()

    if not config.enabled:
        return []

    params = [("videoID", video_id), ("actionType", "skip")]
    if cid is not None:
        params.append(("cid", str(cid)))
    for category in config.categories:
        params.append(("category", category))

    headers = {
        "origin": config.origin or DEFAULT_ORIGIN,
        "x-ext-version": config.extension_version or DEFAULT_EXTENSION_VERSION,
    }

    url = f"{config.api_url.rstrip('/')}/skipSegments"
    import aiohttp

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url, params=params) as response:
            if response.status == 404:
                return []
            response.raise_for_status()
            payload = await response.json()

    raw_segments: List[Tuple[float, float]] = []
    for item in payload:
        if item.get("actionType") != "skip":
            continue

        if cid is not None and item.get("cid") not in (None, "", str(cid), cid):
            continue

        submitted_duration = item.get("videoDuration") or 0
        if (
            duration
            and submitted_duration
            and abs(float(submitted_duration) - float(duration)) > 2
        ):
            logger.debug(
                f"Skipping outdated SponsorBlock segment for {video_id}: "
                f"submitted={submitted_duration} current={duration}"
            )
            continue

        segment = item.get("segment") or []
        if len(segment) != 2:
            continue

        raw_segments.append((float(segment[0]), float(segment[1])))

    return normalize_skip_segments(raw_segments, duration=duration)
