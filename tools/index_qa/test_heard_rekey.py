import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import heard_gate as H
import heard_rekey as RK

CS = {1: {1: (0, 10, "u/001.mp3")}, 2: {1: (0, 10, "u/002.mp3")}}
WANT = {1: "aaa", 2: "bbb"}


def rep(sha="old", version=None, kind="heard", m1="aaa", m2="OTHER"):
    return {"sha256": sha, "version": version or H.VERSION, "kind": kind, "maps": {
        "1": {"sha256": m1, "anchors": [1], "fileRef": "u/001.mp3"},
        "2": {"sha256": m2, "anchors": [1], "fileRef": "u/002.mp3"}}}


class RekeyTest(unittest.TestCase):
    def test_same_sha_keeps_all(self):
        self.assertEqual(set(RK.valid_old_maps(rep(sha="live"), "live", CS, WANT, False)), {1, 2})

    def test_stale_without_rekey_drops_all(self):
        self.assertEqual(RK.valid_old_maps(rep(), "live", CS, WANT, False), {})

    def test_rekey_keeps_only_matching_audio(self):
        self.assertEqual(set(RK.valid_old_maps(rep(), "live", CS, WANT, True)), {1})   # س2 تغيّر صوتها فلا تُربط

    def test_changed_audio_never_rekeyed(self):
        r = rep(m1="CHANGED", m2="CHANGED")
        self.assertEqual(RK.valid_old_maps(r, "live", CS, WANT, True), {})

    def test_wrong_ref_or_missing_anchors_or_version(self):
        r = rep(m2="bbb"); r["maps"]["2"]["fileRef"] = "u/OTHER.mp3"
        self.assertEqual(set(RK.valid_old_maps(r, "live", CS, WANT, True)), {1})
        r = rep(m2="bbb"); r["maps"]["2"]["anchors"] = []
        self.assertEqual(set(RK.valid_old_maps(r, "live", CS, WANT, True)), {1})
        self.assertEqual(RK.valid_old_maps(rep(version=-5), "live", CS, WANT, True), {})
        self.assertEqual(RK.valid_old_maps(rep(kind="x"), "live", CS, WANT, True), {})

    def test_missing_declared_sha_not_rekeyed(self):
        self.assertEqual(RK.valid_old_maps(rep(m1=None), "live", CS, {1: None, 2: None}, True), {})


if __name__ == "__main__":
    unittest.main()
