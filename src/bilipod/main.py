import argparse
import asyncio
import shutil
import signal
import threading
import time
from pathlib import Path

import schedule
from tinydb import TinyDB

from bp_class import Pod
from executing import (
    data_initialize,
    run_web_server,
    schedule_job,
    update_episodes,
    update_pod,
)
from utils.bp_log import Logger
from utils.config_parser import BiliPodConfig
from utils.login import get_credential, update_credential

BANNER = r"""
.______    __   __       __  .______     ______    _______
|   _  \  |  | |  |     |  | |   _  \   /  __  \  |       \
|  |_)  | |  | |  |     |  | |  |_)  | |  |  |  | |  .--.  |
|   _  <  |  | |  |     |  | |   ___/  |  |  |  | |  |  |  |
|  |_)  | |  | |  `----.|  | |  |      |  `--'  | |  '--'  |
|______/  |__| |_______||__| | _|       \______/  |_______/
"""

stop_event = threading.Event()  # Event to signal program termination


def signal_handler(signum, frame):
    global stop_event
    logger = Logger().get_logger()
    logger.info(f"Received signal {signum}. Stopping...")
    stop_event.set()


def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)


async def main(config: BiliPodConfig, db_path: Path):
    logger = Logger().get_logger()
    credential = await get_credential(config=config)

    logger.info(BANNER)
    logger.info("Start initializing...")

    # init db
    if not db_path.parent.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        shutil.copyfile(db_path, db_path.with_suffix(".bak"))
        db_path.unlink()

    db = TinyDB(db_path)
    pod_tbl = db.table("pod")
    episode_tbl = db.table("episode")

    # media dir init
    media_dir = Path(config.storage.data_dir) / "media"
    if not media_dir.exists():
        media_dir.mkdir(parents=True, exist_ok=True)

    # web server
    web_server_thread = threading.Thread(
        target=run_web_server,
        args=(
            config.server,
            config.storage.data_dir,
        ),
        daemon=True,
    )
    web_server_thread.start()

    await data_initialize(
        config=config,
        pod_tbl=pod_tbl,
        episode_tbl=episode_tbl,
        credential=credential,
    )

    logger.info("Finished initializing...")

    # update pod and episodes by scheduler
    asyncio.create_task(update_episodes(pod_tbl, episode_tbl, credential))

    logger.info("Starting scheduler...")
    for pod_info in pod_tbl.all():
        pod = Pod.from_dict(pod_info)
        schedule_job(
            update_interval=pod_info["update_period"],
            job=update_pod,
            pod=pod,
            pod_tbl=pod_tbl,
            credential=credential,
        )

    # update token every 6 hours
    schedule_job(update_interval='6h', job=update_credential, credential=credential)

    run_scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    run_scheduler_thread.start()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        while not stop_event.is_set():
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Received KeyboardInterrupt. Stopping...")
        stop_event.set()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process the BiliPod configuration file."
    )
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Path to the configuration file.",
    )
    parser.add_argument(
        "--db",
        type=str,
        required=True,
        help="Path to the database file.",
    )
    args = parser.parse_args()
    try:
        config = BiliPodConfig.from_yaml(args.config)
        print("Configuration loaded successfully.")
    except Exception as e:
        print(f"An error occurred while loading the configuration: {e}")
        exit(1)

    Logger.setup(config=config.log)

    asyncio.run(main(config=config, db_path=Path(args.db)))
