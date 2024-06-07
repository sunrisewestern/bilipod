import asyncio
import re

import schedule

from utils.bp_log import Logger

logger = Logger().get_logger()


def schedule_job(update_interval, job=None, *args, **kwargs):
    """
    Schedules the job based on the provided update interval.

    Args:
        update_interval (str): The update interval string. Can be in formats:
            - "60m", "4h", "2h45m" for durations
            - "12:00" for a specific time of day (24h format)
            - Defaults to "12h"
    """

    if re.match(r"^\d{1,2}d$", update_interval):  # Days only
        days = int(update_interval[:-1])
        schedule.every(days).days.do(run_async, job, *args, **kwargs)

    elif re.match(r"^\d{1,2}d\d{1,2}h$", update_interval):  # Days and hours
        days, hours = map(int, re.findall(r"\d+", update_interval))
        schedule.every(days).days.at(f"{hours:02}:00").do(
            run_async, job, *args, **kwargs
        )

    elif re.match(
        r"^\d{1,2}d\d{1,2}h\d{1,2}m$", update_interval
    ):  # Days, hours, minutes
        days, hours, minutes = map(int, re.findall(r"\d+", update_interval))
        schedule.every(days).days.at(f"{hours:02}:{minutes:02}").do(
            run_async, job, *args, **kwargs
        )
    elif re.match(r"^\d{1,2}h$", update_interval):  # Hours only
        hours = int(update_interval[:-1])
        schedule.every(hours).hours.do(run_async, job, *args, **kwargs)

    elif re.match(r"^\d{1,2}h\d{1,2}m$", update_interval):  # Hours and minutes
        hours, minutes = map(int, re.findall(r"\d+", update_interval))
        schedule.every(hours).hours.at(f":{minutes:02}").do(
            run_async, job, *args, **kwargs
        )

    elif re.match(r"^\d{1,2}m$", update_interval):  # Minutes only
        minutes = int(update_interval[:-1])
        schedule.every(minutes).minutes.do(run_async, job, *args, **kwargs)

    elif re.match(r"^\d{1,2}:\d{2}$", update_interval):  # Specific time of day
        schedule.every().day.at(update_interval).do(run_async, job, *args, **kwargs)

    else:
        logger.error(f"Invalid update interval: {update_interval}")
        raise ValueError(f"Invalid update interval format: {update_interval}")


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
