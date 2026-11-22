"""اختبارات مقارنة بصمات pV بلا اتصال بالدلو."""
import datetime
import gzip
import hashlib
import json
import unittest
from unittest.mock import Mock
from pathlib import Path

import compressed_repair_status as mod


class FakeS3:
    def __init__(self, objects):
        self.objects = objects

    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            raise FileNotFoundError(Key)
        raw, when = self.objects[Key]
        return {"Body": Mock(read=lambda r=raw: r), "ContentLength": len(raw), "LastModified": when}


def jz(payload: dict) -> bytes:
    return gzip.compress(json.dumps(payload).encode(), mtime=0)


class Compare(unittest.TestCase):
    def test_same_and_changed_and_missing(self):
        raw = jz({"sha256": "abcdefgh" + "0"*56, "fromKey": "old"})
        sha8 = hashlib.sha256(raw).hexdigest()[:8]
        self.assertEqual(mod.compare({"pv_sha8": sha8}, {"live_sha8": sha8}), "كما_في_pV")
        self.assertEqual(mod.compare({"pv_sha8": "deadbeef"}, {"live_sha8": sha8}), "تغيّرت_بصمته")
        self.assertEqual(mod.compare({"pv_sha8": "deadbeef"}, {"error": "404"}), "غائب")

    def test_report_counts(self):
        catalog = {"indexes": [
            {"key": "timings/hafs/a.jz", "pv_sha8": "aaaaaaaa", "n_confirmed_surahs": 2},
            {"key": "timings/hafs/b.jz", "pv_sha8": "bbbbbbbb", "n_confirmed_surahs": 1},
        ]}
        lives = [
            {"live_sha8": "aaaaaaaa", "last_modified": "2026-10-13T00:00:00Z"},
            {"live_sha8": "cccccccc", "last_modified": "2026-11-20T00:00:00Z"},
        ]
        text, buckets = mod.report(catalog, lives)
        self.assertEqual(len(buckets["كما_في_pV"]), 1)
        self.assertEqual(len(buckets["تغيّرت_بصمته"]), 1)
        self.assertIn("تغيّرت بصمته منذ المسح 1", text)
        self.assertIn("لا يثبت وحده زوال الضغط", text)


if __name__ == "__main__":
    unittest.main()
