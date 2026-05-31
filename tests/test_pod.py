from pathlib import Path

import pytest

from src.bilipod.bp_class import Pod


def test_pod_to_dict_does_not_mutate_data_dir(tmp_path):
    pod = Pod(
        feed_id="feed.test",
        data_dir=tmp_path,
        base_url="http://localhost",
    )

    data = pod.to_dict()

    assert data["data_dir"] == str(tmp_path)
    assert isinstance(pod.data_dir, Path)
    assert pod.data_dir == tmp_path


def test_pod_requires_base_url():
    with pytest.raises(TypeError):
        Pod(feed_id="feed.test")


def test_pod_from_dict_requires_base_url():
    with pytest.raises(ValueError, match="base_url is required"):
        Pod.from_dict({"feed_id": "feed.test"})


def test_pod_builds_xml_url_without_double_slash():
    pod = Pod(feed_id="feed.test", base_url="http://localhost:7001/")

    assert pod.xml_url == "http://localhost:7001/test.xml"
