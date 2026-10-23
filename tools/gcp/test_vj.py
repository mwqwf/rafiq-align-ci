import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vj import billable_seconds, t

H = 3600
def job(i, state, create, start, end=None):
    d = {"name": f"projects/1/locations/us-central1/customJobs/{i}", "state": f"JOB_STATE_{state}",
         "createTime": create, "startTime": start}
    if end: d["endTime"] = end
    return d

START = t("2026-10-01T00:00:00Z")
E0 = t("2026-10-20T00:00:00Z")  # أقدم إقلاعٍ معلَّم (بدء العهد)
NOW = t("2026-10-23T20:00:00Z")
marker_old = f"900.{int(E0)}"  # مهمة قديمة أقلعت وعلّمت العهد

class T(unittest.TestCase):
    def test_cancelled_never_ran(self):  # الحالة الحقيقية: 14:25Z→17:08Z بلا تشغيل
        j = job("2179237621119582208", "CANCELLED", "2026-10-23T14:25:00Z", "2026-10-23T14:25:05Z", "2026-10-23T17:08:00Z")
        self.assertEqual(billable_seconds([j], START, marker_old, "", NOW), 0)

    def test_cancelled_never_ran_legacy_skiplist(self):  # قبل عهد العلامات: القائمة اليدويّة
        j = job("111", "CANCELLED", "2026-10-10T14:25:00Z", "2026-10-10T14:25:05Z", "2026-10-10T17:08:00Z")
        self.assertEqual(billable_seconds([j], START, "", "111", NOW), 0)
        self.assertGreater(billable_seconds([j], START, "", "", NOW), 2 * H)  # بلا قائمة: يُحسب تحفّظاً

    def test_cancelled_after_run(self):  # انتظر ساعتين ثم أقلع ساعةً ثم أُلغيت
        boot = t("2026-10-23T16:00:00Z")
        j = job("222", "CANCELLED", "2026-10-23T14:00:00Z", "2026-10-23T14:00:05Z", "2026-10-23T17:00:00Z")
        s = billable_seconds([j], START, marker_old + f" 222.{int(boot)}", "", NOW)
        self.assertEqual(s, 3600 + 600)  # من الإقلاع (ناقص هامش التهيئة) لا من القبول

    def test_running(self):
        boot = t("2026-10-23T18:00:00Z")
        j = job("333", "RUNNING", "2026-10-23T17:00:00Z", "2026-10-23T17:00:05Z")
        s = billable_seconds([j], START, marker_old + f" 333.{int(boot)}", "", NOW)
        self.assertEqual(s, 2 * H + 600)
        # بلا علامة وهي جارية: تُحسب كاملةً (آمن)
        self.assertEqual(billable_seconds([j], START, marker_old, "", NOW), NOW - t("2026-10-23T17:00:05Z"))

    def test_succeeded(self):
        j = job("444", "SUCCEEDED", "2026-10-22T10:00:00Z", "2026-10-22T10:00:10Z", "2026-10-22T13:00:10Z")
        self.assertEqual(billable_seconds([j], START, marker_old, "", NOW), 3 * H)  # لا علامة: تُحسب (نجاح)

    def test_pending_not_counted(self):
        j = job("555", "PENDING", "2026-10-23T14:00:00Z", "2026-10-23T14:00:05Z")
        self.assertEqual(billable_seconds([j], START, marker_old, "", NOW), 0)

if __name__ == "__main__":
    unittest.main()
