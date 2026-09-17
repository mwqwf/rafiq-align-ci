#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import hashlib
import io
import unittest

from tools.packages.catalog_backup import LIVE_KEY, backup_live


class FakeS3:
    def __init__(self, body=b'{"packages":[]}'):
        self.objects = {LIVE_KEY: body}
        self.puts = []

    def get_object(self, Bucket, Key):
        return {"Body": io.BytesIO(self.objects[Key])}

    def put_object(self, Bucket, Key, Body, **kwargs):
        if kwargs.get("IfNoneMatch") == "*" and Key in self.objects:
            raise RuntimeError("would overwrite")
        self.objects[Key] = Body
        self.puts.append((Key, kwargs))


class BackupTest(unittest.TestCase):
    def test_exact_old_bytes_are_saved_and_verified(self):
        s3 = FakeS3()
        sha = hashlib.sha256(s3.objects[LIVE_KEY]).hexdigest()
        result = backup_live(
            s3, "bucket", sha,
            dt.datetime(2026, 9, 16, 18, 0, tzinfo=dt.timezone.utc))
        self.assertEqual(result["sha256"], sha)
        self.assertEqual(
            result["backupKey"], f"packages/backups/catalog.20260916T180000Z.{sha}.json")
        self.assertEqual(s3.objects[result["backupKey"]], s3.objects[LIVE_KEY])
        self.assertEqual(s3.puts[0][1]["IfNoneMatch"], "*")

    def test_changed_live_catalog_is_blocked_before_write(self):
        s3 = FakeS3()
        with self.assertRaisesRegex(ValueError, "changed"):
            backup_live(s3, "bucket", "0" * 64)
        self.assertEqual(s3.puts, [])


if __name__ == "__main__":
    unittest.main()
