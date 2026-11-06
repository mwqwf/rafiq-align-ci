"""(2026-11-06) حارسُ «الغياب منحازٌ إلى القصار» يستثني السورَ المُسقطةَ بإعلان — حتى حين يكون
كلُّ المفقود فيها — ويبقى قاتلاً للمفقود غيرِ المعلَن. بلا شبكة وبلا دلو."""
import unittest

from tools.index_qa import run as R

C = R.COUNTS


def _idx(skip_surah, declare):
    E, ms = [], 0
    for s in range(1, 115):
        for a in range(1, C[s - 1] + 1):
            if s == skip_surah:
                continue
            E.append({"ayahId": f"{s}:{a}", "startMs": ms, "endMs": ms + 1000,
                      "fileRef": f"https://example.org/q/{s:03d}.mp3"})
            ms += 1000
    idx = {"ayahCounting": "KUFI", "ayahCount": 6236, "entries": E}
    if declare:
        idx["transform"] = {"op": f"drop_surah:{skip_surah}", "reason": "اختبار"}
    return idx


def _txt(short_surah):
    out = []
    for s in range(1, 115):
        for _ in range(C[s - 1]):
            out.append("كلمة" if s == short_surah else " ".join(["كلمة"] * 12))
    return out


class BiasDeclaredDrop(unittest.TestCase):
    def _fatal(self, declare):
        f, _w, _i = R.structural(_idx(37, declare), "timings-staging/qalun/x.abcdef12.jz",
                                 txt_ref=_txt(37))[:3]
        return [x for x in f if "منحاز" in x]

    def test_all_missing_declared_not_fatal(self):
        self.assertEqual(self._fatal(True), [])

    def test_same_missing_undeclared_still_fatal(self):
        self.assertTrue(self._fatal(False))


if __name__ == "__main__":
    unittest.main()
