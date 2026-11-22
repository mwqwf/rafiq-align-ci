"""اختبارات جرد الشواهد المعلّقة بلا اتصال بالدلو."""
import datetime
import json
import unittest
from unittest.mock import Mock

import pending_human_verdicts as mod


class FakePaginator:
    def __init__(self, objects):
        self.objects = objects

    def paginate(self, Bucket, Prefix):
        yield {"Contents": [o for o in self.objects if o["Key"].startswith(Prefix)]}


class FakeS3:
    def __init__(self, objects, bodies):
        self.objects = objects
        self.bodies = bodies
        self.gets = []

    def get_paginator(self, name):
        assert name == "list_objects_v2"
        return FakePaginator(self.objects)

    def get_object(self, Bucket, Key):
        self.gets.append(Key)
        body = self.bodies[Key]
        return {"Body": Mock(read=lambda b=body: b)}


def obj(key, day):
    return {"Key": key, "LastModified": datetime.datetime(2026, 11, day)}


class Classify(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(mod.classify("مقبول"), "مقبول")
        self.assertEqual(mod.classify("مقبول بشرط"), "مقبول")
        self.assertEqual(mod.classify("خلل بنيوي في السلسلة"), "خلل بنيوي")
        self.assertEqual(mod.classify("عطبٌ جسيم 6%"), "عطبٌ جسيم")
        self.assertEqual(mod.classify("حدّي عند الآية"), "حدّي")
        self.assertEqual(mod.classify("موقوف حتى الشاهد"), "موقوف")
        self.assertEqual(mod.classify("سبب غير معروف"), "آخر")


class ScanBudget(unittest.TestCase):
    def test_newest_first_and_budget_truncates(self):
        objects = [obj(f"state-ci/{i}.json", i) for i in range(1, 6)]
        bodies = {f"state-ci/{i}.json": json.dumps({"verdict": "عطبٌ جسيم"}).encode() for i in range(1, 6)}
        s3 = FakeS3(objects, bodies)
        # ميزانية تكفي الدفعة الأولى فقط إن جعلنا العمّال 2 وsleep في الجلب
        result = mod.scan(s3, "b", budget_sec=60, workers=1)
        self.assertEqual(result["listed"], 5)
        self.assertEqual(result["scanned"], 5)
        self.assertFalse(result["truncated"])
        self.assertEqual(result["pending"]["عطبٌ جسيم"], 5)
        # الأحدث أولاً: يوم 5 قبل يوم 1
        self.assertEqual(s3.gets[0], "state-ci/5.json")

    def test_accepted_excluded_from_pending(self):
        objects = [obj("state-ci/a.json", 2), obj("state-ci/b.json", 1)]
        bodies = {
            "state-ci/a.json": json.dumps({"verdict": "مقبول"}).encode(),
            "state-ci/b.json": json.dumps({"verdict": "حدّي"}).encode(),
        }
        result = mod.scan(FakeS3(objects, bodies), "b", budget_sec=30, workers=2)
        self.assertEqual(result["accepted"], 1)
        self.assertEqual(result["pending"], {"حدّي": 1})
        text = mod.render(result)
        self.assertIn("حدّي: 1 شاهداً", text)
        self.assertIn("مُسِح 2/2", text)
        self.assertNotIn("جزئي", text)

    def test_render_marks_partial(self):
        text = mod.render({
            "listed": 1000, "scanned": 80, "accepted": 10, "errors": 2,
            "pending": {"خلل بنيوي": 5}, "truncated": True,
            "list_sec": 1.0, "elapsed_sec": 90.0,
        })
        self.assertIn("الجرد جزئي", text)
        self.assertIn("80/1000", text)


if __name__ == "__main__":
    unittest.main()
