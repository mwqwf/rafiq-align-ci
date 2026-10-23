import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import graft_surahs as g

C = g.ayah_counts()


def surah(s, shift=0):
    return [{"ayahId": f"{s}:{a}", "startMs": a * 100 + shift, "endMs": a * 100 + 90 + shift,
             "confBand": "HIGH", "fileRef": f"f{s}"} for a in range(1, C[s - 1] + 1)]


def idx(shifts=None, **kw):
    shifts = shifts or {}
    ents = []
    for s in (1, 2, 3):
        ents += surah(s, shifts.get(s, 0))
    d = {"riwaya": "hafs", "reciterId": "x", "engineVersion": "E1", "entries": ents}
    d.update(kw)
    return d


class T(unittest.TestCase):
    def setUp(self):
        self.base = idx()
        self.donor = idx({2: 5}, transform={"fromSha256": "B"}, engineBySurah={"2": "E2"})

    def run_g(self, surahs=(2,), **kw):
        return g.graft(kw.get("base", self.base), kw.get("donor", self.donor), "B", list(surahs),
                       kw.get("anc"), "D", C)

    def bad(self, msg=None, **kw):
        with self.assertRaises(SystemExit) as cm:
            self.run_g(**kw)
        if msg:
            self.assertIn(msg, str(cm.exception))

    def test_ok(self):
        out, rep = self.run_g()
        by = {e["ayahId"]: e for e in out["entries"]}
        self.assertEqual(by["2:1"]["startMs"], 105)
        self.assertEqual(by["1:1"], self.base["entries"][0])
        self.assertEqual(len(out["entries"]), len(self.base["entries"]))
        self.assertEqual(out["engineBySurah"], {"2": "E2"})
        self.assertEqual(rep["engines"], {"2": "E2"})

    def test_other_surah_change_in_donor_ignored(self):
        self.donor["entries"][0]["endMs"] = 55            # س1 غيرُ مسمّاة
        out, _ = self.run_g()
        self.assertEqual(out["entries"][0], self.base["entries"][0])

    def test_header_transform(self):
        out, rep = self.run_g()
        t = g.build_transform(self.base, out, "B", "k", "dk", rep, "r")
        self.assertEqual(t["fromSha256"], "B")
        self.assertEqual(t["graft"]["surahs"], [2])
        self.assertEqual(t["graft"]["engineBySurah"], {"2": "E2"})
        self.assertEqual(t["graft"]["donorSha256"], "D")

    def test_engine_same_as_index_not_hidden(self):
        del self.donor["engineBySurah"]
        self.donor["engineVersion"] = "E9"
        out, _ = self.run_g()
        self.assertEqual(out["engineBySurah"]["2"], "E9")   # لا يُخفى محرّكٌ مغاير

    def test_audio_sha_taken_from_donor_for_grafted_only(self):
        base = idx(audioSha256=["a1", "a2", "a3"])
        donor = idx({2: 5}, transform={"fromSha256": "B"}, audioSha256=["x1", "NEW", "x3"])
        out, _ = g.graft(base, donor, "B", [2], None, "D", C)
        self.assertEqual(out["audioSha256"], ["a1", "NEW", "a3"])

    def test_audio_sha_fixed_114_layout(self):
        fixed = ["f%d" % i for i in range(114)]
        don = list(fixed)
        don[1] = "NEW"
        base = idx(audioSha256=fixed)
        donor = idx({2: 5}, transform={"fromSha256": "B"}, audioSha256=don)
        out, _ = g.graft(base, donor, "B", [2], None, "D", C)
        self.assertEqual(out["audioSha256"][1], "NEW")
        self.assertEqual(out["audioSha256"][0], "f0")
        self.assertEqual(out["audioSha256"][2], "f2")

    def test_audio_sha_empty_donor_value_not_taken(self):
        base = idx(audioSha256=["a1", "a2", "a3"])
        donor = idx({2: 5}, transform={"fromSha256": "B"}, audioSha256=["x1", "", "x3"])
        out, _ = g.graft(base, donor, "B", [2], None, "D", C)
        self.assertEqual(out["audioSha256"], ["a1", "a2", "a3"])

    def test_audio_sha_untouched_when_lists_misaligned(self):
        base = idx(audioSha256=["a1", "a2", "a3"])
        donor = idx({2: 5}, transform={"fromSha256": "B"}, audioSha256=["a1", "NEW"])
        out, _ = g.graft(base, donor, "B", [2], None, "D", C)
        self.assertEqual(out["audioSha256"], ["a1", "a2", "a3"])

    def test_grafted_sha_not_matching_current_source_still_rejected_by_heard_gate(self):
        # الحارس لم يضعف: بصمةٌ مزروعةٌ من متبرِّعٍ لا تطابق الصوتَ المسموع فعلاً تُردّ في heard_gate
        import heard_gate as H
        base = idx(audioSha256=["a1", "OLD", "a3"])
        donor = idx({2: 5}, transform={"fromSha256": "B"}, audioSha256=["a1", "DONOR", "a3"])
        out, _ = g.graft(base, donor, "B", [2], None, "D", C)
        self.assertEqual(out["audioSha256"][1], "DONOR")
        def m(sha):
            return {"sha256": sha, "fileRef": "f2", "anchors": {"1": [[105, 995], 0.9, []]}}
        bad = H.judge(out, base, "x" * 64, {2: m("CURRENT"), 1: m("a1"), 3: m("a3")})
        self.assertFalse(bad["ok"])
        self.assertIn("غيرُ صوت المرشّح", bad["reason"])
        ok = H.judge(out, base, "x" * 64, {2: m("DONOR"), 1: m("a1"), 3: m("a3")})
        self.assertNotIn("غيرُ صوت المرشّح", ok["reason"] or "")

    def test_empty(self):
        self.bad("فارغة", surahs=())

    def test_duplicate(self):
        self.bad("مكرَّرة", surahs=(2, 2))

    def test_parse(self):
        self.assertEqual(g.parse_surahs("28, 2"), [2, 28])
        for t in ("", " ", "2,2", "x", "0", "115"):
            with self.assertRaises(SystemExit):
                g.parse_surahs(t)

    def test_unmodified(self):
        self.bad("غيرُ معدَّلة", surahs=(1,))

    def test_wrong_parent(self):
        self.donor["transform"]["fromSha256"] = "Z"
        self.bad("غيرُ مشتق")

    def test_other_reciter(self):
        self.donor["reciterId"] = "y"
        self.bad("لقارئين")

    def test_chain_ok(self):
        mid = idx({2: 3}, transform={"fromSha256": "B"})
        self.donor["transform"]["fromSha256"] = "M"
        out, rep = self.run_g(anc=[{"sha": "M", "idx": mid}])
        self.assertEqual(rep["lineage"], ["M"])

    def test_chain_broken_hop(self):
        mid = idx({2: 3}, transform={"fromSha256": "Q"})
        self.donor["transform"]["fromSha256"] = "M"
        self.bad("غيرُ مشتق", anc=[{"sha": "M", "idx": mid}])

    def test_chain_sha_mismatch(self):
        mid = idx({2: 3}, transform={"fromSha256": "B"})
        self.donor["transform"]["fromSha256"] = "M"
        self.bad("لا تطابق", anc=[{"sha": "X", "idx": mid}])

    def test_chain_other_reciter(self):
        mid = idx({2: 3}, transform={"fromSha256": "B"})
        mid["reciterId"] = "y"
        self.donor["transform"]["fromSha256"] = "M"
        self.bad("أخرى", anc=[{"sha": "M", "idx": mid}])

    def _long_chain(self, n, break_at=None):
        anc, prev = [], "B"
        for i in range(n):
            sha = f"H{i}"
            mid = idx({2: i + 1}, transform={"fromSha256": "Z" if i == break_at else prev})
            anc.insert(0, {"sha": sha, "idx": mid})
            prev = sha
        self.donor["transform"]["fromSha256"] = prev
        return anc

    def test_chain_long_ok(self):
        anc = self._long_chain(12)
        out, rep = self.run_g(anc=anc)
        self.assertEqual(len(rep["lineage"]), 12)

    def test_chain_long_broken_deep_hop(self):
        self.bad("لا تطابق", anc=self._long_chain(12, break_at=3))

    def test_chain_too_long(self):
        self.bad("أطول", anc=self._long_chain(g.MAX_CHAIN + 2))

    def test_chain_missing_hop(self):
        self.donor["transform"]["fromSha256"] = "M"
        self.bad("غيرُ مشتق")

    def test_donor_incomplete(self):
        self.donor["entries"] = [e for e in self.donor["entries"] if e["ayahId"] != "2:7"]
        self.bad("ناقصة")

    def test_donor_declares_missing(self):
        self.donor["missing"] = {"ids": ["2:7"]}
        self.bad()

    def test_donor_declares_truncated_tail(self):
        self.donor["transform"]["truncatedTail"] = {"2": {"published": 100}}
        self.bad("يعلن")

    def test_donor_declare_gap_op(self):
        self.donor["transform"]["op"] = "declare_gap:2"
        self.bad("يعلن")

    def test_base_surah_incomplete(self):
        self.base["entries"] = [e for e in self.base["entries"] if e["ayahId"] != "2:7"]
        self.bad("الأصل نفسِه")

    def test_base_declares_missing(self):
        self.base["missing"] = {"ids": ["2:3"]}
        self.bad("الأصل نفسِه")

    def test_duplicate_key(self):
        self.donor["entries"].append(copy.deepcopy(self.donor["entries"][10]))
        self.bad("مكرَّرة")

    def test_key_out_of_reference(self):
        self.donor["entries"].append({"ayahId": "1:8", "startMs": 0, "endMs": 1})
        self.bad("خارج مرجع")

    def test_overlap(self):
        self.donor["entries"][12]["startMs"] = 0           # س2: تداخل
        self.bad("غيرُ صاعدة")

    def test_text_changed(self):
        for e in self.base["entries"]:
            e["text"] = "a"
        for e in self.donor["entries"]:
            e["text"] = "b" if e["ayahId"] == "2:5" else "a"
        self.bad("نصٌّ مغيَّر")

    def test_donor_engine_in_nonlisted_ignored(self):
        self.donor["engineBySurah"]["1"] = "E3"            # س1 غيرُ مسمّاة: لا تدخل الترويسة
        out, _ = self.run_g()
        self.assertNotIn("1", out["engineBySurah"])


if __name__ == "__main__":
    unittest.main()
