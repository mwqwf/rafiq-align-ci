"""اختبار وحدة لأداة حزم الأجزاء على صور صغيرة مصنوعة (بلا صور حقيقية ولا شبكة)."""
import hashlib
import json
import os
import re
import sys
import tempfile
import unittest
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_juz_packs as b  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def fake_images(root, riwaya, pages=604, skip=None):
    d = os.path.join(root, riwaya)
    os.makedirs(d)
    for p in range(1, pages + 1):
        if p == skip:
            continue
        with open(os.path.join(d, b.page_name(p)), "wb") as f:
            f.write(b"RIFF" + p.to_bytes(4, "little") + bytes([p % 251]) * (50 + p % 17))


class JuzPacksTest(unittest.TestCase):
    def test_ranges_partition_all_pages_without_overlap(self):
        rs = b.juz_ranges()
        self.assertEqual(len(rs), 30)
        seen = []
        for _, first, last in rs:
            seen.extend(range(first, last + 1))
        self.assertEqual(seen, list(range(1, 605)))

    def test_table_matches_kotlin_default(self):
        # الجدولُ المعتمد في التطبيق (ReadingProgressRules.JuzPages.DEFAULT) منسوخاً حرفاً: المستودعُ العامّ لا يحمل مصدرَ التطبيق.
        app = [1, 22, 42, 62, 82, 102, 121, 142, 162, 182, 201, 222, 242, 262, 282,
               302, 322, 342, 362, 382, 402, 422, 442, 462, 482, 502, 522, 542, 562, 582]
        self.assertEqual(app, b.JUZ_FIRST)

    def test_build_stored_zip_and_index_hashes(self):
        with tempfile.TemporaryDirectory() as t:
            img, out = os.path.join(t, "img"), os.path.join(t, "out")
            fake_images(img, "hafs")
            idx = b.build_riwaya(img, out, "hafs")
            self.assertEqual(len(idx["packs"]), 30)
            self.assertEqual(len(idx["pages"]), 604)
            on_disk = json.load(open(os.path.join(out, "hafs", "index.json"), encoding="utf8"))
            self.assertEqual(on_disk, json.loads(json.dumps(idx)))
            for pk in idx["packs"]:
                path = os.path.join(out, "hafs", pk["file"])
                self.assertEqual(hashlib.sha256(open(path, "rb").read()).hexdigest(), pk["sha256"])
                self.assertEqual(os.path.getsize(path), pk["bytes"])
                with zipfile.ZipFile(path) as z:
                    names = [i.filename for i in z.infolist()]
                    self.assertEqual(names, [b.page_name(p) for p in range(pk["first"], pk["last"] + 1)])
                    for info in z.infolist():
                        self.assertEqual(info.compress_type, zipfile.ZIP_STORED)
                        page = int(info.filename[:3])
                        original = open(os.path.join(img, "hafs", info.filename), "rb").read()
                        self.assertEqual(z.read(info), original)  # بايتات الصفحة حرفاً
                        self.assertEqual(idx["pages"][str(page)], hashlib.sha256(original).hexdigest())

    def test_deterministic_output(self):
        with tempfile.TemporaryDirectory() as t:
            img = os.path.join(t, "img")
            fake_images(img, "warsh")
            a = b.build_riwaya(img, os.path.join(t, "o1"), "warsh")
            c = b.build_riwaya(img, os.path.join(t, "o2"), "warsh")
            self.assertEqual(a, c)

    def test_missing_page_fails_loudly(self):
        with tempfile.TemporaryDirectory() as t:
            img = os.path.join(t, "img")
            fake_images(img, "qalun", skip=300)
            with self.assertRaises(ValueError):
                b.build_riwaya(img, os.path.join(t, "out"), "qalun")


if __name__ == "__main__":
    unittest.main()
