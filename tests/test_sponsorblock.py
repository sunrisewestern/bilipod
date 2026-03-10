import sys
import unittest
from pathlib import Path

path_to_src = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(path_to_src))

from bilipod.utils.sponsorblock import invert_skip_segments, normalize_skip_segments


class TestSponsorBlockHelpers(unittest.TestCase):
    def test_normalize_skip_segments_merges_overlaps(self):
        segments = [(10, 20), (19.98, 30), (-5, 4), (35, 35)]

        self.assertEqual(
            normalize_skip_segments(segments, duration=40),
            [(0.0, 4.0), (10.0, 30.0)],
        )

    def test_invert_skip_segments_returns_keep_ranges(self):
        segments = [(5, 10), (15, 20)]

        self.assertEqual(
            invert_skip_segments(segments, duration=25),
            [(0.0, 5.0), (10.0, 15.0), (20.0, 25.0)],
        )


if __name__ == "__main__":
    unittest.main()
