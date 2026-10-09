import unittest, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import graft_surah_range as g


def e(s, a, st, en):
    return {"ayahId": f"{s}:{a}", "startMs": st, "endMs": en, "confBand": "HIGH"}


class GraftTest(unittest.TestCase):
    def setUp(self):
        self.base = {"riwaya": "hafs", "reciterId": "x", "entries": [e(1, 1, 0, 10), e(2, 1, 10, 20), e(2, 2, 20, 30), e(2, 3, 30, 40)]}
        self.donor = {"riwaya": "hafs", "reciterId": "x", "transform": {"fromSha256": "B"},
                      "entries": [e(1, 1, 0, 10), e(2, 1, 10, 15), e(2, 2, 15, 33), e(2, 3, 33, 40)]}

    def test_ok(self):
        out, rep = g.graft(self.base, self.donor, "B", 2, 2)
        got = [(x["ayahId"], x["startMs"], x["endMs"]) for x in out["entries"]]
        self.assertEqual(got, [("1:1", 0, 10), ("2:1", 10, 15), ("2:2", 15, 33), ("2:3", 33, 40)])

    def test_wrong_parent(self):
        with self.assertRaises(SystemExit):
            g.graft(self.base, self.donor, "C", 2, 2)

    def test_other_surah_changed(self):
        self.donor["entries"][0]["endMs"] = 11
        with self.assertRaises(SystemExit):
            g.graft(self.base, self.donor, "B", 2, 2)


if __name__ == "__main__":
    unittest.main()
