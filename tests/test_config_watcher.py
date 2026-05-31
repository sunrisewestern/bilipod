import asyncio

from tinydb import Query, TinyDB
from tinydb.storages import MemoryStorage

from src.bilipod.bp_class import Pod
from src.bilipod.executing import config_watcher
from src.bilipod.utils.config_parser import FeedConfig, ServerConfig


def test_sync_feed_config_reconciles_changed_feeds(tmp_path, monkeypatch):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
feeds:
  feed_existing:
    uid: 1
    update_period: 2m
  feed_added:
    uid: 2
    update_period: 3m
""",
        encoding="utf-8",
    )

    db = TinyDB(storage=MemoryStorage)
    pod_tbl = db.table("pod")
    episode_tbl = db.table("episode")
    pod_tbl.insert(
        Pod(
            feed_id="feed_existing",
            data_dir=tmp_path,
            base_url="http://localhost",
            update_period="1m",
        ).to_dict()
    )
    pod_tbl.insert(
        Pod(
            feed_id="feed_removed",
            data_dir=tmp_path,
            base_url="http://localhost",
        ).to_dict()
    )

    scheduled_feeds = []
    cleared_feeds = []
    regenerated_opml = []
    cleaned_rss = []
    cleaned_untracked = []

    async def fake_initialize_or_update_feed(
        feed_id,
        feed_config,
        server_config,
        data_dir,
        pod_tbl,
        episode_tbl,
        credential,
    ):
        pod = Pod(
            feed_id=feed_id,
            data_dir=data_dir,
            base_url="http://localhost",
            uid=feed_config.uid,
            update_period=feed_config.update_period,
        )
        pod_tbl.upsert(pod.to_dict(), Query().feed_id == feed_id)
        return pod

    def fake_schedule_pod_update(pod, pod_tbl, credential):
        scheduled_feeds.append((pod.feed_id, pod.update_period))

    def fake_clear_feed_job(feed_id):
        cleared_feeds.append(feed_id)

    monkeypatch.setattr(
        config_watcher, "initialize_or_update_feed", fake_initialize_or_update_feed
    )
    monkeypatch.setattr(config_watcher, "schedule_pod_update", fake_schedule_pod_update)
    monkeypatch.setattr(config_watcher, "clear_feed_job", fake_clear_feed_job)
    monkeypatch.setattr(
        config_watcher,
        "generate_opml",
        lambda pod_tbl, filename: regenerated_opml.append(filename),
    )
    monkeypatch.setattr(
        config_watcher,
        "clean_unused_rss",
        lambda pod_tbl, data_dir: cleaned_rss.append(data_dir),
    )
    monkeypatch.setattr(
        config_watcher,
        "clean_untracked_episodes",
        lambda pod_tbl, episode_tbl: cleaned_untracked.append(True),
    )

    current_feeds = {
        "feed_existing": FeedConfig(uid=1, update_period="1m"),
        "feed_removed": FeedConfig(uid=3),
    }

    updated_feeds = asyncio.run(
        config_watcher.sync_feed_config(
            config_path=config_file,
            server_config=ServerConfig(),
            data_dir=tmp_path,
            pod_tbl=pod_tbl,
            episode_tbl=episode_tbl,
            credential=None,
            current_feeds=current_feeds,
        )
    )

    assert sorted(updated_feeds) == ["feed_added", "feed_existing"]
    assert not pod_tbl.search(Query().feed_id == "feed_removed")
    assert sorted(scheduled_feeds) == [("feed_added", "3m"), ("feed_existing", "2m")]
    assert sorted(cleared_feeds) == ["feed_added", "feed_existing", "feed_removed"]
    assert regenerated_opml == [tmp_path / "podcast.opml"]
    assert cleaned_rss == [tmp_path]
    assert cleaned_untracked == [True]
