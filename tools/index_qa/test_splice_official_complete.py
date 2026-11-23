#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import drop_surah
import promote
import splice_official_complete as SOC
import stage_transform


def _make_index(riwaya="douri", reciter="husary_douri", skip_ayahs=(), engine="ctc-seg-1"):
    counts = drop_surah.SURAH_AYAHS_OF({"riwaya": riwaya})
    entries = []
    for s in range(1, 115):
        url = f"https://server13.mp3quran.net/husr/Rewayat-Aldori-A-n-Abi-Amr/{s:03d}.mp3"
        t = 1000
        for a in range(1, counts[s - 1] + 1):
            if (s, a) in skip_ayahs:
                t += 2000
                continue
            entries.append({
                "ayahId": f"{s}:{a}",
                "fileRef": url,
                "startMs": t,
                "endMs": t + 1000,
                "conf": 0.9,
                "confBand": "HIGH",
            })
            t += 1000
    return {
        "schema": 1,
        "riwaya": riwaya,
        "reciterId": reciter,
        "sourceKind": "SURAH_FILES",
        "ayahCounting": "KUFI",
        "ayahCount": sum(counts),
        "method": "ASR_ALIGN",
        "engineVersion": engine,
        "refineVersion": "none",
        "refinedCount": 0,
        "audioSha256": ["a" * 64] * 114,
        "missing": {"count": len(skip_ayahs), "byReason": {"count_map_wide_ayah": len(skip_ayahs)} if skip_ayahs else {}, "ids": []},
        "entries": entries,
    }


class _S3:
    def __init__(self, blobs):
        self.blobs = dict(blobs)
        self.puts = {}

    def get_object(self, Bucket, Key):
        return {"Body": mock.Mock(read=lambda: self.blobs[Key])}

    def put_object(self, Bucket, Key, Body, **kw):
        self.puts[Key] = Body

    def head_object(self, Bucket, Key):
        return {"ContentLength": len(self.puts[Key])}


class SpliceOfficialCompleteTest(unittest.TestCase):
    def test_splices_only_complete_surahs_and_passes_stage_transform_guards(self):
        parent = _make_index(skip_ayahs=())
        # s39 missing 10 wide ayahs (65/75), s1 missing all 7, s112 & s113 complete with shifted official times
        skip = {(39, a) for a in range(11, 21)} | {(1, a) for a in range(1, 8)}
        official = _make_index(skip_ayahs=skip, engine="mp3quran-timing-v1")
        for e in official["entries"]:
            if e["ayahId"].startswith(("112:", "113:")):
                e["startMs"] += 500
                e["endMs"] += 500
        # Restrict test to s39 (incomplete -> excluded) vs s112,s113 (complete -> spliced)
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            p_path = tdir / "parent.jz"
            o_path = tdir / "official.jz"
            out_path = tdir / "patched.jz"
            SOC.dump_jz(parent, p_path)
            SOC.dump_jz(official, o_path)

            comp = SOC.complete_official_surahs(parent, official)
            self.assertNotIn(39, comp)
            self.assertNotIn(1, comp)
            self.assertIn(112, comp)
            self.assertIn(113, comp)

            taken = SOC.splice_complete(
                p_path, o_path,
                "https://server13.mp3quran.net/husr/Rewayat-Aldori-A-n-Abi-Amr/{s:03d}.mp3",
                269, out_path, only_surahs=[39, 112, 113],
            )
            self.assertEqual(taken, [112, 113])
            patched = SOC.load_jz(out_path)
            self.assertEqual(len(patched["entries"]), len(parent["entries"]))
            self.assertEqual(patched["engineBySurah"], {"112": "mp3quran-timing-v1", "113": "mp3quran-timing-v1"})
            self.assertEqual(patched["sourceTimingBySurah"]["112"]["readId"], 269)
            self.assertEqual(promote.census_surahs(patched), {"112", "113"})

            # Verify stage_transform accepts official_timing_splice:112,113 without relaxing any guard
            pbytes = p_path.read_bytes()
            psha = __import__("hashlib").sha256(pbytes).hexdigest()
            s3 = _S3({"timings/douri/husary_douri.jz": pbytes})
            argv = [
                "stage_transform.py",
                "--file", str(out_path),
                "--parent", "timings/douri/husary_douri.jz",
                "--parent-sha", psha,
                "--op", "official_timing_splice:112,113",
                "--reason", "اختبار زرع السور التامة فقط",
            ]
            with mock.patch.object(promote, "s3", return_value=(s3, "b")), \
                 mock.patch.object(promote, "catalog", return_value={"reciters": [{"id": "husary_douri", "riwaya": "douri"}]}), \
                 mock.patch.object(sys, "argv", argv):
                stage_transform.main()


if __name__ == "__main__":
    unittest.main()
