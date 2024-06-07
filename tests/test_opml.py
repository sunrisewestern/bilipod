import sys
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

scr_to_src = Path(__file__).parent / "src"
sys.path.insert(0, str(scr_to_src))
print(sys.path)
from src.bilipod import generate_opml


@pytest.mark.parametrize(
    "mock_pod_tbl_return_value, expected_opml_content",
    [
        (
            [
                {
                    "title": "Podcast 1",
                    "keyword": "Tech",
                    "description": "A podcast about technology.",
                    "xml_url": "https://example.com/podcast1.xml",
                    "opml": True,
                },
                {
                    "title": "Podcast 2",
                    "keyword": None,
                    "description": "Another great podcast.",
                    "xml_url": "https://example.com/podcast2.xml",
                    "opml": True,
                },
                {
                    "title": "Podcast 3",
                    "keyword": "News",
                    "description": "Stay informed with the latest news.",
                    "xml_url": "https://example.com/podcast3.xml",
                    "opml": False,
                },
            ],
            '<?xml version="1.0" encoding="utf-8"?>\n'
            "<opml version='1.0'>\n"
            "  <head>\n"
            "    <title>Bilipod feeds</title>\n"
            "  </head>\n"
            "  <body>\n"
            "<!--\n-->\n"
            "    <outline text='A podcast about technology.' type='rss' xmlUrl='https://example.com/podcast1.xml' title='Podcast 1[Tech]'/>\n"
            "    \t\t<!--\n-->\n"
            "    <outline text='Another great podcast.' type='rss' xmlUrl='https://example.com/podcast2.xml' title='Podcast 2'/>\n"
            "    \t\t<!--\n-->\n"
            "  </body>\n"
            "</opml>",
        ),
    ],
)
def test_generate_opml(mock_pod_tbl_return_value, expected_opml_content):
    mock_pod_tbl = MagicMock()
    mock_pod_tbl.all.return_value = mock_pod_tbl_return_value

    mock_file = mock_open()
    with patch("src.bilipod.feed.open", mock_file):
        generate_opml(mock_pod_tbl, "test.opml")

    mock_file.assert_called_once_with("test.opml", "w", encoding="utf-8")
    mock_file().write.assert_called_once_with(expected_opml_content)
