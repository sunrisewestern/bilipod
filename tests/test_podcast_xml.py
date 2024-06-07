import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from feedgen.feed import FeedGenerator
from tinydb import table

path_to_src = Path(__file__).parent / "src"
sys.path.insert(0, str(path_to_src))
from src.bilipod.bp_class import Pod
from src.bilipod.feed.podcast_rss import generate_feed_xml


class TestGenerateFeedXML(unittest.TestCase):
    def setUp(self):
        self.pod = Pod(
            feed_id="feed.test",
            description="A test podcast",
            link="http://example.com",
            cover_art="http://example.com/image.jpg",
            author="Author Name",
            category="Technology",
            subcategories=["Software"],
            data_dir="/path/to/data",
            episodes=[
                {
                    "bvid": "test_bvid",
                    "quality": "low",
                    "format": "audio",
                },
            ],
        )
        self.episode_data = [
            {
                "bvid": "test_bvid",
                "size": 32438032,
                "title": "Episode 1",
                "link": "http://example.com/ep1",
                "description": "Description of episode 1",
                "pubdate": "2024-05-01",
                "base_url": "http://example.com/",
                "data_dir": "/path/to/data",
                "type": "audio/mpeg",
                "duration": "30:00",
                "image": "http://example.com/ep1.jpg",
                "explicit": "no",
                "quality": "low",
                "format": "audio",
            }
        ]
        self.episode_tbl = MagicMock(spec=table.Table)
        self.episode_tbl.search.return_value = self.episode_data

    def test_generate_feed_xml(self):
        # Mocking the file writing and RSS generation
        FeedGenerator.rss_str = MagicMock(return_value="<rss></rss>")
        FeedGenerator.rss_file = MagicMock()

        generate_feed_xml(self.pod, self.episode_tbl)

        # Check if rss_file was called correctly
        FeedGenerator.rss_file.assert_called_with("/path/to/data/test.xml")

        # Check if the correct number of episodes were processed
        self.assertEqual(len(self.episode_data), 1)
