#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""الخريطة المستخرجة من السجل تحتفظ بكل الحقول، ويُرفض البناء والاقتطاع."""
import base64
import hashlib
import json
import re
import unittest
from unittest.mock import patch

from tools.ci_fleet import emit_probe_map as emitter


class ProbeMapTest(unittest.TestCase):
    def data(self):
        return {"surah": 63, "riwaya": "hafs", "engine": "ctc-heardmap-1", "entries": [],
                "sha256": "a" * 64, "totalMs": 285000,
                "heardMap": {str(i): {"anchorMs": [i * 1000, i * 1000 + 800],
                    "heard": i != 5, "occurrences": [[i * 1000, i * 1000 + 800, 0.9]]}
                    for i in range(1, 12)},
                "chunkMap": [[0, 15000, 0, 0.9, 120]], "extra": "حقل عربي محفوظ"}

    def test_multiple_log_chunks_restore_every_field_and_match_digest(self):
        original = self.data()
        with patch.object(emitter, "CHUNK_CHARS", 96):
            lines = list(emitter.map_lines(original, 63, "hafs"))
        header = re.fullmatch(r"CTC_COMPACT_MAP_BEGIN bytes=(\d+) sha256=([0-9a-f]{64}) chunks=(\d+)", lines[0])
        self.assertIsNotNone(header)
        count = int(header[3])
        self.assertGreater(count, 1)
        self.assertEqual(len(lines), count + 2)
        encoded = []
        for position, line in enumerate(lines[1:-1], 1):
            prefix = f"CTC_COMPACT_MAP_CHUNK {position}/{count} "
            self.assertTrue(line.startswith(prefix))
            encoded.append(line[len(prefix):])
        raw = base64.b64decode("".join(encoded), validate=True)
        self.assertEqual(len(raw), int(header[1]))
        self.assertEqual(hashlib.sha256(raw).hexdigest(), header[2])
        self.assertEqual(lines[-1], f"CTC_COMPACT_MAP_END sha256={header[2]}")
        self.assertEqual(json.loads(raw), original)

    def test_build_output_is_rejected(self):
        data = self.data()
        data["entries"] = [{"ayahIdx": 0, "startMs": 1000}]
        with self.assertRaisesRegex(ValueError, "مداخل محاذاة"):
            list(emitter.map_lines(data, 63, "hafs"))

    def test_wrong_source_identity_is_rejected(self):
        for surah, riwaya in ((64, "hafs"), (63, "warsh")):
            with self.subTest(surah=surah, riwaya=riwaya), self.assertRaisesRegex(ValueError, "هوية"):
                list(emitter.map_lines(self.data(), surah, riwaya))

    def test_oversized_map_fails_before_any_begin_marker(self):
        with patch.object(emitter, "MAX_BYTES", 100):
            lines = emitter.map_lines(self.data(), 63, "hafs")
            with self.assertRaisesRegex(ValueError, "مبتورة"):
                next(lines)

    def test_missing_map_or_fingerprint_is_rejected(self):
        for key in ("heardMap", "sha256"):
            data = self.data()
            del data[key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                list(emitter.map_lines(data, 63, "hafs"))


if __name__ == "__main__":
    unittest.main()
