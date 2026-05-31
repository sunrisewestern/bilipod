import asyncio
from pathlib import Path
from typing import Dict

from bilibili_api import Credential
from tinydb import Query, table

from ..bp_class import Pod
from ..feed import generate_opml
from ..utils.bp_log import Logger
from ..utils.config_parser import FeedConfig, ServerConfig, load_feed_configs
from .clean import clean_untracked_episodes, clean_unused_rss
from .initialize import initialize_or_update_feed
from .scheduler import clear_feed_job, feed_job_tag, schedule_job
from .update import update_pod

logger = Logger().get_logger()
FEED_CONFIG_WATCH_INTERVAL = 30


def feed_config_snapshot(feeds: Dict[str, FeedConfig]) -> dict:
    return {feed_id: feed.to_dict() for feed_id, feed in feeds.items()}


def _format_feed_ids(feed_ids: list[str]) -> str:
    return ", ".join(feed_ids) if feed_ids else "none"


def schedule_pod_update(pod: Pod, pod_tbl: table.Table, credential: Credential):
    return schedule_job(
        update_interval=pod.update_period,
        job=update_pod,
        pod=pod,
        pod_tbl=pod_tbl,
        credential=credential,
        tags=feed_job_tag(pod.feed_id),
    )


async def sync_feed_config(
    config_path: str | Path,
    server_config: ServerConfig,
    data_dir: str | Path,
    pod_tbl: table.Table,
    episode_tbl: table.Table,
    credential: Credential,
    current_feeds: Dict[str, FeedConfig],
) -> Dict[str, FeedConfig]:
    latest_feeds = load_feed_configs(str(config_path))
    current_snapshot = feed_config_snapshot(current_feeds)
    latest_snapshot = feed_config_snapshot(latest_feeds)

    if latest_snapshot == current_snapshot:
        return current_feeds

    current_ids = set(current_snapshot)
    latest_ids = set(latest_snapshot)
    removed_feed_ids = sorted(current_ids - latest_ids)
    added_feed_ids = sorted(latest_ids - current_ids)
    updated_feed_ids = sorted(
        feed_id
        for feed_id in current_ids & latest_ids
        if current_snapshot[feed_id] != latest_snapshot[feed_id]
    )

    applied_feeds = dict(current_feeds)
    applied_added_feed_ids = []
    applied_updated_feed_ids = []
    changed = False

    for feed_id in removed_feed_ids:
        clear_feed_job(feed_id)
        pod_tbl.remove(Query().feed_id == feed_id)
        applied_feeds.pop(feed_id, None)
        changed = True

    for feed_id in added_feed_ids + updated_feed_ids:
        try:
            pod = await initialize_or_update_feed(
                feed_id=feed_id,
                feed_config=latest_feeds[feed_id],
                server_config=server_config,
                data_dir=data_dir,
                pod_tbl=pod_tbl,
                episode_tbl=episode_tbl,
                credential=credential,
            )
        except Exception as e:
            logger.exception(f"Failed to apply feed config for {feed_id}: {e}")
            continue

        clear_feed_job(feed_id)
        schedule_pod_update(pod=pod, pod_tbl=pod_tbl, credential=credential)
        applied_feeds[feed_id] = latest_feeds[feed_id]
        if feed_id in added_feed_ids:
            applied_added_feed_ids.append(feed_id)
        else:
            applied_updated_feed_ids.append(feed_id)
        changed = True

    if changed:
        generate_opml(pod_tbl=pod_tbl, filename=Path(data_dir) / "podcast.opml")
        clean_unused_rss(pod_tbl, data_dir)
        clean_untracked_episodes(pod_tbl, episode_tbl)
        logger.info(
            "Feed config reloaded. "
            f"added: {_format_feed_ids(applied_added_feed_ids)}, "
            f"updated: {_format_feed_ids(applied_updated_feed_ids)}, "
            f"removed: {_format_feed_ids(removed_feed_ids)}"
        )

    return applied_feeds


async def watch_feed_config_changes(
    config_path: str | Path,
    server_config: ServerConfig,
    data_dir: str | Path,
    pod_tbl: table.Table,
    episode_tbl: table.Table,
    credential: Credential,
    initial_feeds: Dict[str, FeedConfig],
    interval: int = FEED_CONFIG_WATCH_INTERVAL,
) -> None:
    current_feeds = dict(initial_feeds)
    logger.info(f"Watching feed config changes every {interval} seconds.")

    while True:
        await asyncio.sleep(interval)
        try:
            current_feeds = await sync_feed_config(
                config_path=config_path,
                server_config=server_config,
                data_dir=data_dir,
                pod_tbl=pod_tbl,
                episode_tbl=episode_tbl,
                credential=credential,
                current_feeds=current_feeds,
            )
        except Exception as e:
            logger.exception(f"Failed to reload feed config: {e}")
