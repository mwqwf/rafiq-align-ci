# -*- coding: utf-8 -*-
"""ختم الأحكام المصحَّحة في التشخيص — **من جهاز المالك بلا خادم**.

⛔ ما يستطيعه وما لا يستطيعه، وكلاهما معلَن:
   ✅ **الأحكام**: فارز الأرباع يعمل من **الفهرس والنصّ وحدهما** (الفهارس
      على R2 والنصوص محلية) ⇒ يُصحَّح حكم كل مرشَّح لعيب صوت بلا خادم.
   ⛔ **النسب** (`durationRatio`): تحتاج **مدّة كل ملف** وهي قياسٌ على الصوت
      نفسه — 114 ملفاً لكل قارئ. وقياسها من هنا يمرّ بخط المالك (عشرات
      الجيغابايتات)، وقياسها على الخادم متعذّر ما دام SSH منقطعاً.
      ⇒ تبقى **بالمقام المنفوخ**، ويُكتب في الملف ما يمنع قراءتها على أنها
      مصحَّحة: `ratiosPendingRemeasure`.

**ونصفُ تصحيحٍ معلَنٌ خيرٌ من كاملٍ مؤجَّل** — ما دام الناقص مسمّى في الملف
نفسه لا في رسالةٍ تتقادم.

    python3 patch_diagnosis_verdicts.py [--apply]
"""
import argparse
import importlib.util
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
_s = importlib.util.spec_from_file_location(
    "pp", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "pace_profile.py"))
pp = importlib.util.module_from_spec(_s)
_s.loader.exec_module(pp)

NOTE = ("الأحكام مصحَّحة بفارز انتظام الوتيرة عبر أرباع السورة (يعمل من "
        "الفهرس والنصّ بلا صوت). أما durationRatio فمحسوبٌ بمقامٍ منفوخ "
        "(وتيرةٌ من وسيط السور كلها، والسور القصيرة تنفخها) ⇒ منخفضٌ نحو "
        "الربع للسور الكبيرة. يُعاد قياسه متى عاد الوصول إلى الخادم.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    s3, b = pp.client()

    keys = []
    for pg in s3.get_paginator("list_objects_v2").paginate(
            Bucket=b, Prefix="catalog/diagnosis/"):
        keys += [o["Key"] for o in pg.get("Contents", [])]
    print("ملفات التشخيص: {}".format(len(keys)))

    changed_files = 0
    for k in sorted(keys):
        d = json.loads(s3.get_object(Bucket=b, Key=k)["Body"].read())
        riwaya, rid = d["riwaya"], d["reciter"]
        hits = [w for w in d.get("weakSurahs", [])
                if w["verdict"].startswith("AUDIO")]
        if not hits:
            continue
        changed = False
        for w in hits:
            try:
                r = pp.profile(s3, b, riwaya, rid, w["surah"],
                               w.get("durationRatio"))
            except Exception as e:
                print("  ⚠️ {}/{} س{}: {}".format(riwaya, rid, w["surah"],
                                                  str(e)[:40]))
                continue
            v = r["verdict"]
            new = (v if v in ("AUDIO_SHORT", "AUDIO_IRREGULAR_LONG",
                              "PACE_ANOMALY")
                   else "UNCLEAR")     # لا مرجع / مداخل قليلة ⇒ لا يُدان
            if new != w["verdict"] or "paceQuarters" not in w:
                w["verdict"] = new
                w["paceQuarters"] = r.get("quarters")
                w["paceSpreadPoints"] = r.get("spreadPoints")
                w["paceVerdictRaw"] = v
                changed = True
                print("  {}/{} س{}: → {} · أرباع {}".format(
                    riwaya, rid, w["surah"], new, r.get("quarters")))
        if not changed:
            continue
        cnt = {}
        for w in d.get("weakSurahs", []):
            cnt[w["verdict"]] = cnt.get(w["verdict"], 0) + 1
        d["counts"] = cnt
        d["verdictsCorrectedAt"] = int(time.time())
        d["ratiosPendingRemeasure"] = True
        d["correctionNote"] = NOTE
        changed_files += 1
        if a.apply:
            if "_quarantine" in k:
                sys.exit("⛔ كتابة ممنوعة تحت مسار محجور: " + k)
            s3.put_object(Bucket=b, Key=k, ContentType="application/json",
                          Body=json.dumps(d, ensure_ascii=False,
                                          indent=1).encode("utf-8"))
    print("\n{} ملفاً {}".format(
        changed_files, "خُتم" if a.apply else "سيُختم (تجربة جافة)"))


if __name__ == "__main__":
    main()
