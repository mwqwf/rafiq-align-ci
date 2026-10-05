#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبارات جرد القراءة: أخطاء الدلو لا تتحوّل إلى شهادة اكتمال أو جودة."""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tools.ci_fleet import agent_cmd


class StateReadErrorsTest(unittest.TestCase):
    def _state(self, indexes, *, catalog_ids=None, previous=None):
        """دلو وهمي كامل: لا شبكة، ولا أسرار، ولا كتابة خارج المجلد المؤقت."""
        client = Mock()
        client.get_paginator.return_value.paginate.return_value = [{
            "Contents": [{"Key": key, "Size": 100} for key in indexes]
        }]
        catalog = {"riwayat": [{"id": "hafs", "reciters": [
            {"id": rid} for rid in (catalog_ids or [
                key.rsplit("/", 1)[1][:-3] for key in indexes
            ])
        ]}]}
        client.get_object.return_value = {
            "Body": io.BytesIO(json.dumps(catalog).encode("utf-8"))
        }

        def fetch(key):
            item = indexes[key]
            if isinstance(item, Exception):
                raise item
            return item, b""

        fake_run = SimpleNamespace(s3=lambda: (client, "test"), fetch_index=Mock(side_effect=fetch))
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            if previous:
                (output / "state.json").write_text(json.dumps(previous), encoding="utf-8")
            with patch.object(agent_cmd, "OUT_DIR", output), \
                    patch.object(agent_cmd, "_gap_surahs", return_value={"1": 6}), \
                    patch.dict(sys.modules, {"run": fake_run}), \
                    patch.object(sys, "path", sys.path.copy()):
                rc, message = agent_cmd.do_state({"action": "state"})
            state = json.loads((output / "state.json").read_text(encoding="utf-8"))
        return rc, message, state, fake_run.fetch_index

    @staticmethod
    def _short_index():
        return {"entries": [{"ayahId": "1:1"}], "engineVersion": "test"}

    def test_success_records_current_read_count_and_timestamp(self):
        started = datetime.now(timezone.utc).replace(microsecond=0)
        rc, message, state, fetch = self._state({
            "timings/hafs/a.jz": self._short_index(),
            "timings/hafs/b.jz": self._short_index(),
        })
        self.assertEqual(rc, 0)
        self.assertEqual(state["fetchedCount"], 2)
        self.assertEqual(state["readErrors"], {})
        self.assertTrue(state["readComplete"])
        self.assertEqual(state["published"], 2)
        self.assertEqual(fetch.call_count, 2)
        timestamp = datetime.fromisoformat(state["generatedAt"].replace("Z", "+00:00"))
        self.assertGreaterEqual(timestamp, started)
        self.assertLessEqual(timestamp, datetime.now(timezone.utc))
        self.assertIn("لا يشهد بصحة التوقيت", message)

    def test_one_failed_read_is_saved_and_later_indexes_are_still_counted(self):
        bad_key = "timings/hafs/a_unreadable.jz"
        good_key = "timings/hafs/z_readable.jz"
        rc, message, state, fetch = self._state({
            bad_key: OSError("تعذّرت قراءة الفهرس"),
            good_key: self._short_index(),
        })
        self.assertNotEqual(rc, 0)
        self.assertEqual(state["published"], 2)
        self.assertEqual(state["missingCount"], 0)
        self.assertEqual(state["fetchedCount"], 1)
        self.assertFalse(state["readComplete"])
        self.assertEqual(state["readErrors"], {bad_key: "OSError: تعذّرت قراءة الفهرس"})
        self.assertIn("hafs/z_readable", state["indexesWithGaps"])
        self.assertEqual(fetch.call_count, 2)
        self.assertIn("الجرد غير مكتمل", message)
        self.assertNotIn("اكتمل الهدف", message)

    def test_all_failed_reads_replace_old_success_report(self):
        key = "timings/hafs/unreadable.jz"
        rc, message, state, _ = self._state(
            {key: ValueError("تعذّر فك الفهرس")},
            previous={"readComplete": True, "generatedAt": "2000-01-01T00:00:00Z"},
        )
        self.assertNotEqual(rc, 0)
        self.assertFalse(state["readComplete"])
        self.assertEqual(state["fetchedCount"], 0)
        self.assertEqual(state["indexesWithGaps"], {})
        self.assertIn(key, state["readErrors"])
        self.assertNotEqual(state["generatedAt"], "2000-01-01T00:00:00Z")
        self.assertIn("0/1", message)

    def test_6236_entries_are_not_presented_as_quality_certification(self):
        # عدد مكتمل ظاهرياً مع تكرار متعمّد؛ جرد الوجود ليس حارس البنية أو الصوت.
        entries = [{"ayahId": f"{surah}:1"} for surah in range(1, 115)]
        entries += [{"ayahId": "1:1"}] * (6236 - len(entries))
        rc, message, state, _ = self._state({"timings/hafs/count_only.jz": {"entries": entries}})
        self.assertEqual(rc, 0)
        self.assertTrue(state["readComplete"])
        self.assertEqual(state["indexesWithGaps"], {})
        self.assertIn("لا يشهد بصحة التوقيت أو جودة الفهرسة", message)
        self.assertNotIn("اكتمل الهدف", message)


if __name__ == "__main__":
    unittest.main()
