import asyncio
import re
import threading
from collections.abc import Iterable

import schedule

from ..utils.bp_log import Logger

logger = Logger().get_logger()
schedule_lock = threading.RLock()


def feed_job_tag(feed_id: str) -> str:
    return f"feed:{feed_id}"


def _normalize_tags(tags: str | Iterable[str] | None) -> tuple[str, ...]:
    if tags is None:
        return ()
    if isinstance(tags, str):
        return (tags,)
    return tuple(tags)


def _tag_job(scheduled_job, tags: str | Iterable[str] | None):
    normalized_tags = _normalize_tags(tags)
    if normalized_tags:
        scheduled_job.tag(*normalized_tags)
    return scheduled_job


def clear_jobs(tag: str | None = None) -> None:
    with schedule_lock:
        schedule.clear(tag)


def clear_feed_job(feed_id: str) -> None:
    clear_jobs(feed_job_tag(feed_id))


def run_pending() -> None:
    with schedule_lock:
        schedule.run_pending()


def schedule_job(update_interval, job=None, *args, tags=None, **kwargs):
    """
    Schedules the job based on the provided update interval.

    Args:
        update_interval (str): The update interval string. Can be in formats:
            - "1d", "1d2h", "60m", "4h", "2h45m" for durations
            - "12:00" for a specific time of day (24h format)
            - Defaults to "12h"
    """

    with schedule_lock:
        if re.match(r"^\d{1,2}d$", update_interval):  # Days only
            days = int(update_interval[:-1])
            scheduled_job = schedule.every(days).days.do(
                run_async, job, *args, **kwargs
            )

        elif re.match(r"^\d{1,2}d\d{1,2}h$", update_interval):  # Days and hours
            days, hours = map(int, re.findall(r"\d+", update_interval))
            scheduled_job = schedule.every(days).days.at(f"{hours:02}:00").do(
                run_async, job, *args, **kwargs
            )

        elif re.match(
            r"^\d{1,2}d\d{1,2}h\d{1,2}m$", update_interval
        ):  # Days, hours, minutes
            days, hours, minutes = map(int, re.findall(r"\d+", update_interval))
            scheduled_job = schedule.every(days).days.at(
                f"{hours:02}:{minutes:02}"
            ).do(run_async, job, *args, **kwargs)
        elif re.match(r"^\d{1,2}h$", update_interval):  # Hours only
            hours = int(update_interval[:-1])
            scheduled_job = schedule.every(hours).hours.do(
                run_async, job, *args, **kwargs
            )

        elif re.match(r"^\d{1,2}h\d{1,2}m$", update_interval):  # Hours and minutes
            hours, minutes = map(int, re.findall(r"\d+", update_interval))
            scheduled_job = schedule.every(hours).hours.at(f":{minutes:02}").do(
                run_async, job, *args, **kwargs
            )

        elif re.match(r"^\d{1,2}m$", update_interval):  # Minutes only
            minutes = int(update_interval[:-1])
            scheduled_job = schedule.every(minutes).minutes.do(
                run_async, job, *args, **kwargs
            )

        elif re.match(r"^\d{1,2}:\d{2}$", update_interval):  # Specific time of day
            scheduled_job = schedule.every().day.at(update_interval).do(
                run_async, job, *args, **kwargs
            )

        else:
            logger.error(f"Invalid update interval: {update_interval}")
            raise ValueError(f"Invalid update interval format: {update_interval}")

        return _tag_job(scheduled_job, tags)


def run_async(job, *args, **kwargs):
    """
    Wrapper function to run an async job in a separate event loop.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(job(*args, **kwargs))
    finally:
        loop.close()
