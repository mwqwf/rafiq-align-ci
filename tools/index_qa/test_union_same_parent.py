# -*- coding: utf-8 -*-
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import splice_surah as sp
import union_same_parent as u

C = u.COUNTS
URL = "https://archive.example/reciter/{s:03d}.mp3"
PARENT_KEY = "timings/hafs/x.jz"
PARENT_SHA = "a" * 64


def rows(s, shift=0):
    ref = URL.format(s=s)
    return [{"ayahId": f"{s}:{a}", "fileRef": ref,
             "startMs": a * 100 + shift, "endMs": a * 100 + 90 + shift,
             "conf": 0.9, "confBand": "HIGH"}
            for a in range(1, C[s - 1] + 1)]


def idx(present, shifts=None, **kw):
    shifts = shifts or {}
    ents = []
    for s in present:
        ents += rows(s, shifts.get(s, 0))
    d = {"riwaya": "hafs", "reciterId": "x", "engineVersion": "ctc-seg-1",
         "entries": ents, "audioSha256": [""] * 114}
    d.update(kw)
    return d


def child(present, shifts=None, **kw):
    t = {"op": "realign_surah:" + ",".join(map(str, present)),
         "fromKey": PARENT_KEY, "fromSha256": PARENT_SHA}
    t.update(kw.pop("transform", {}))
    return idx(present, shifts, transform=t, **kw)


class T(unittest.TestCase):
    def setUp(self):
        # الأب فيه 108 و114 فقط؛ 109 و112 غائبتان.
        self.parent = idx([108, 114], engineBySurah={"108": "ctc-dualfix-1"})

    def plan(self, donors, url=URL):
        return u.plan(self.parent, PARENT_KEY, PARENT_SHA, donors, url)

    def test_fills_gap_and_repairs(self):
        d1 = child([108, 109, 114], {109: 0, 108: 7},
                   engineBySurah={"108": "whisper-x", "109": "whisper-x"})
        d2 = child([108, 112, 114], {112: 0})
        # d2 لا يصلح 108 (نفس الأب) فيُعرض 112 فقط
        taken = self.plan([
            ("timings-staging/hafs/x.aaaa0001.jz", "b" * 64, d1, None),
            ("timings-staging/hafs/x.bbbb0002.jz", "c" * 64, d2, None),
        ])
        self.assertEqual(sorted(taken), [108, 109, 112])
        self.assertEqual(taken[108]["rows"][0]["startMs"], 107)
        self.assertEqual(taken[109]["maps"]["engineBySurah"], "whisper-x")
        self.assertIsNone(taken[112]["maps"]["engineBySurah"])

    def test_conflict_rejected(self):
        d1 = child([108, 114], {108: 7})
        d2 = child([108, 114], {108: 9})
        with self.assertRaises(SystemExit) as cm:
            self.plan([
                ("k1", "b" * 64, d1, None),
                ("k2", "c" * 64, d2, None),
            ])
        self.assertIn("تعارض س108", str(cm.exception))

    def test_identical_offers_ok(self):
        d1 = child([108, 114], {108: 7})
        d2 = child([108, 114], {108: 7})
        taken = self.plan([
            ("k1", "b" * 64, d1, None),
            ("k2", "c" * 64, d2, None),
        ])
        self.assertEqual(list(taken), [108])
        self.assertEqual(taken[108]["donor_key"], "k1")

    def test_wrong_parent_rejected(self):
        d = child([109])
        d["transform"]["fromSha256"] = "f" * 64
        with self.assertRaises(SystemExit) as cm:
            self.plan([("k", "b" * 64, d, None)])
        self.assertIn("ابنٌ مباشر", str(cm.exception))

    def test_wrong_from_key_rejected(self):
        d = child([109])
        d["transform"]["fromKey"] = "timings/hafs/other.jz"
        with self.assertRaises(SystemExit) as cm:
            self.plan([("k", "b" * 64, d, None)])
        self.assertIn("fromKey", str(cm.exception))

    def test_incomplete_named_surah_rejected(self):
        d = child([109])
        d["entries"] = d["entries"][:-1]
        with self.assertRaises(SystemExit) as cm:
            self.plan([("k", "b" * 64, d, [109])])
        self.assertIn("لم تُحلّ", str(cm.exception))

    def test_file_ref_must_match_template(self):
        d = child([109])
        for e in d["entries"]:
            e["fileRef"] = "https://other.example/109.mp3"
        with self.assertRaises(SystemExit) as cm:
            self.plan([("k", "b" * 64, d, None)])
        self.assertIn("لا يُخمَّن", str(cm.exception))

    def test_unchanged_complete_ignored(self):
        d = child([108, 114])  # مطابق للأب
        with self.assertRaises(SystemExit) as cm:
            self.plan([("k", "b" * 64, d, None)])
        self.assertIn("لا سورةَ تُدمج", str(cm.exception))

    def test_splice_preserves_other_entries_and_maps(self):
        d1 = child([108, 109, 114], {109: 0, 108: 7},
                   engineBySurah={"108": "whisper-x", "109": "whisper-x"})
        d2 = child([112, 114], engineBySurah={"112": "ctc-quran-surah-1"})
        taken = self.plan([
            ("k1", "b" * 64, d1, None),
            ("k2", "c" * 64, d2, None),
        ])
        with tempfile.TemporaryDirectory() as td:
            out, path, sha, surahs = u.splice_union(self.parent, taken, URL, td)
            self.assertTrue(Path(path).is_file())
            self.assertTrue(sha)
        self.assertEqual(sorted(surahs), [108, 109, 112])
        by = {e["ayahId"]: e for e in out["entries"]}
        # الأب يُحفظ خارج المأخوذ
        p114 = [e for e in self.parent["entries"] if e["ayahId"].startswith("114:")]
        self.assertEqual([e for e in out["entries"] if e["ayahId"].startswith("114:")], p114)
        self.assertEqual(by["108:1"]["startMs"], 107)
        self.assertEqual(by["109:1"]["startMs"], 100)
        self.assertIn("112:1", by)
        self.assertEqual(out["engineBySurah"]["108"], "whisper-x")
        self.assertEqual(out["engineBySurah"]["109"], "whisper-x")
        self.assertEqual(out["engineBySurah"]["112"], "ctc-quran-surah-1")
        # المداخل حاضرة للثلاث المضافة/المصلحة + 114
        present = sorted({int(e["ayahId"].split(":")[0]) for e in out["entries"]})
        self.assertEqual(present, [108, 109, 112, 114])


if __name__ == "__main__":
    unittest.main()


class OpAndMapGuardT(unittest.TestCase):
    """حارس الترويسة لـ union_same_parent كما في stage_transform: زيادة السجلّ
    للسور المسمّاة فقط وبمحرّك معروف. لا يُرخى الإحصاء."""

    def test_op_regex_parses_union(self):
        import re, promote
        splice_names = "|".join(re.escape(n) for n in sorted(promote.SPLICE_OPS))
        rx = re.compile(rf"^(?:realign_surah|source_timing_splice|union_same_parent|{splice_names}):([\d,\s]+)$")
        m = rx.match("union_same_parent:2,3,4,40")
        self.assertIsNotNone(m)
        self.assertEqual(sorted({int(x) for x in re.findall(r"\d+", m.group(1))}), [2, 3, 4, 40])
        self.assertIsNone(promote.splice_op_name("union_same_parent:2,3"))  # ليس محرّكاً واحداً

    def test_growth_only_named_known_engines(self):
        named = {"4", "40"}
        p_ebs = {"19": "ctc-heardmap-1"}
        ebs = {"19": "ctc-heardmap-1", "4": "ctc-quran-surah-1", "40": "ctc-quran-surah-1"}
        extra = set(ebs) - set(p_ebs)
        self.assertEqual(extra, named)
        import promote
        known = set(promote.SPLICE_OPS.values()) | {"ctc-seg-1"}
        self.assertTrue(all(ebs[k] in known for k in extra))
        # سورة خارج التحويل تُردّ
        ebs2 = dict(ebs, **{"99": "ctc-quran-surah-1"})
        extra2 = set(ebs2) - set(p_ebs)
        self.assertTrue(extra2 - named)
