import sys
from pathlib import Path
from unittest.mock import MagicMock
from xml.etree import ElementTree as ET

import pytest

scr_to_src = Path(__file__).parent / "src"
sys.path.insert(0, str(scr_to_src))
print(sys.path)
from src.bilipod.feed import generate_opml


@pytest.mark.parametrize(
    "mock_pod_tbl_return_value",
    [
        [
            {
                "feed_id": "feed.podcast1",
                "base_url": "https://example.com",
                "title": "Podcast 1",
                "keyword": "Tech",
                "description": "A podcast about technology.",
                "xml_url": "https://example.com/podcast1.xml",
                "opml": True,
            },
            {
                "feed_id": "feed.podcast2",
                "base_url": "https://example.com",
                "title": "Podcast 2",
                "keyword": None,
                "description": "Another great podcast.",
                "xml_url": "https://example.com/podcast2.xml",
                "opml": True,
            },
            {
                "feed_id": "feed.podcast3",
                "base_url": "https://example.com",
                "title": "Podcast 3",
                "keyword": "News",
                "description": "Stay informed with the latest news.",
                "xml_url": "https://example.com/podcast3.xml",
                "opml": False,
            },
        ],
    ],
)
def test_generate_opml(mock_pod_tbl_return_value, tmp_path):
    mock_pod_tbl = MagicMock()
    mock_pod_tbl.all.return_value = mock_pod_tbl_return_value
    output_file = tmp_path / "test.opml"

    generate_opml(mock_pod_tbl, output_file)
    root = ET.parse(output_file).getroot()
    outlines = root.find("body").findall("outline")

    assert root.tag == "opml"
    assert root.attrib["version"] == "1.0"
    assert root.find("head/title").text == "Bilipod feeds"
    assert len(outlines) == 2
    assert outlines[0].attrib == {
        "text": "A podcast about technology.",
        "type": "rss",
        "xmlUrl": "https://example.com/podcast1.xml",
        "title": "Podcast 1[Tech]",
    }
    assert outlines[1].attrib == {
        "text": "Another great podcast.",
        "type": "rss",
        "xmlUrl": "https://example.com/podcast2.xml",
        "title": "Podcast 2",
    }
