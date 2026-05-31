from tinydb import Query, TinyDB
from tinydb.storages import MemoryStorage

from src.bilipod.bp_class import Episode, Pod
from src.bilipod.executing.clean import clean_untracked_episodes


def _episode(bvid, data_dir):
    episode = Episode(
        bvid=bvid,
        format="audio",
        quality="low",
        data_dir=data_dir,
        base_url="http://localhost",
    )
    episode.status = "downloaded"
    return episode


def test_clean_untracked_episodes_removes_rows_and_existing_files(tmp_path):
    media_dir = tmp_path / "media"
    media_dir.mkdir()

    tracked_episode = _episode("BVTRACKED", tmp_path)
    untracked_existing_episode = _episode("BVDELETE", tmp_path)
    untracked_missing_episode = _episode("BVMISSING", tmp_path)
    untracked_existing_episode.location.write_text("audio", encoding="utf-8")

    db = TinyDB(storage=MemoryStorage)
    pod_tbl = db.table("pod")
    episode_tbl = db.table("episode")
    pod_tbl.insert(
        Pod(
            feed_id="feed.test",
            data_dir=tmp_path,
            base_url="http://localhost",
            episodes=[{"bvid": tracked_episode.bvid}],
        ).to_dict()
    )
    episode_tbl.insert_multiple(
        [
            tracked_episode.to_dict(),
            untracked_existing_episode.to_dict(),
            untracked_missing_episode.to_dict(),
        ]
    )

    clean_untracked_episodes(pod_tbl, episode_tbl)

    assert episode_tbl.search(Query().bvid == tracked_episode.bvid)
    assert not episode_tbl.search(Query().bvid == untracked_existing_episode.bvid)
    assert not episode_tbl.search(Query().bvid == untracked_missing_episode.bvid)
    assert not untracked_existing_episode.location.exists()
