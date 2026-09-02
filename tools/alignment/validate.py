# -*- coding: utf-8 -*-
"""اختبارات D-025 الإلزامية + كاتب TimingIndex بصيغة 4.2 المجمَّدة.

HIGH يدخل تلقائياً · MED موسوم · LOW لا يُشحن (قائمة استثناءات).
"""
import hashlib
import time

AYAH_COUNTS = {"KUFI": 6236, "MADANI": 6214}


def band(conf):
    return "HIGH" if conf >= 0.75 else ("MED" if conf >= 0.45 else "LOW")


def check_surah(entries, ref_char_counts, total_ms):
    """فحوص D-025 على مستوى سورة واحدة. يعيد قائمة مخالفات نصية."""
    issues = []
    n = len(entries)
    missing = [e["ayahIdx"] for e in entries if e["startMs"] is None]
    if missing:
        issues.append(f"آيات بلا حدود: {[m+1 for m in missing]}")
    good = [e for e in entries if e["startMs"] is not None]
    # رتابة تصاعدية + لا تداخل
    for a, b in zip(good, good[1:]):
        if b["startMs"] < a["startMs"]:
            issues.append(f"كسر الرتابة عند آية {b['ayahIdx']+1}")
        if b["startMs"] < a["endMs"] - 50:
            issues.append(f"تداخل بين {a['ayahIdx']+1} و{b['ayahIdx']+1}")
    # تغطية: فجوة > 4ث داخل السورة مريبة (سكتة/صمت طويل يوسم)
    for a, b in zip(good, good[1:]):
        if b["startMs"] - a["endMs"] > 4000:
            issues.append(f"فجوة {round((b['startMs']-a['endMs'])/1000,1)}ث بعد آية {a['ayahIdx']+1}")
    # معقولية المدة قياساً بعدد الحروف (انحدار خطي بسيط على آيات السورة نفسها)
    if len(good) >= 5:
        rates = []
        for e in good:
            ch = ref_char_counts[e["ayahIdx"]]
            if ch > 0:
                rates.append((e["endMs"] - e["startMs"]) / ch)
        med = sorted(rates)[len(rates) // 2]
        for e in good:
            ch = ref_char_counts[e["ayahIdx"]]
            dur = e["endMs"] - e["startMs"]
            if ch > 3 and med > 0 and not (0.35 * med * ch <= dur <= 3.0 * med * ch):
                issues.append(f"مدة شاذة لآية {e['ayahIdx']+1}: {dur}م.ث لـ{ch} حرفاً")
                # آية-1 المسنودة بعزل تمهيد مدتها مقبولة (≥1.2ث) لا تُذبح بالإحصاء
                if not (e["ayahIdx"] == 0 and e.get("snapped") and dur >= 1200):
                    e["conf"] = min(e["conf"], 0.44)  # ينزلها LOW/MED
    if good and good[-1]["endMs"] > total_ms + 500:
        issues.append("نهاية آخر آية تتجاوز مدة الملف")
    return issues


def make_timing_index(riwaya, reciter_id, source_kind, counting, per_surah,
                      engine_version="align-0.2", strip_low=True):
    """per_surah: {surah_no: {"fileRef":…, "sha256":…, "entries":[…]}} بفهرس كوفي.

    عقد v2 (اتفاق مستهلك 2026-09-01): الإسقاط داخل البناء — LOW لا تُشحن (D-025)،
    وكل مدخل جارُه التالي غائب لحظة البناء يحمل endApprox:true (نهايته امتداد
    مقطعي لا حداً ملصوقاً — لا يصلح تشغيلاً منفرداً)، والترويسة exactEnds:true.
    """
    entries, shas = [], []
    for sn in sorted(per_surah):
        d = per_surah[sn]
        if d.get("sha256"):
            shas.append(d["sha256"])
        surah_entries = d["entries"]
        n = len(surah_entries)
        shipped = set()
        for e in surah_entries:
            if e["startMs"] is None:
                continue
            if strip_low and band(e["conf"]) == "LOW":
                continue
            shipped.add(e["ayahIdx"])
        for e in surah_entries:
            if e["ayahIdx"] not in shipped:
                continue
            row = {
                "ayahId": f"{sn}:{e['ayahIdx']+1}",
                "fileRef": d["fileRef"],
                "startMs": e["startMs"], "endMs": e["endMs"],
                "conf": e["conf"], "confBand": band(e["conf"]),
            }
            # endApprox يصف حقيقة النهاية لا حضور الجار (تدقيق مستهلك 09-01):
            # جار مفقود كلياً ⇒ النهاية امتداد قد ينزف فوقه ⇒ توسم.
            # جار LOW ملصوق (end == start جاره) ⇒ النهاية ترث ثقة LOW ⇒ توسم.
            # جار LOW غير ملصوق ⇒ النهاية قياس ذاتي لكلمات الآية نفسها ⇒ لا توسم.
            if not (e.get("snapped") or e.get("refined")):
                row["startApprox"] = True  # بداية غير مسنودة لصمت — عقد v2.1
            nxt = e["ayahIdx"] + 1
            if nxt < n and nxt not in shipped:
                nxt_e = next((x for x in surah_entries if x["ayahIdx"] == nxt), None)
                if nxt_e is None or nxt_e["startMs"] is None:
                    row["endApprox"] = True
                elif e["endMs"] == nxt_e["startMs"]:
                    row["endApprox"] = True
            entries.append(row)
    return {
        "schema": 1, "riwaya": riwaya, "reciterId": reciter_id,
        "sourceKind": source_kind, "ayahCounting": counting,
        "ayahCount": AYAH_COUNTS[counting],
        "method": "ASR_ALIGN", "engineVersion": engine_version,
        "exactEnds": True,
        "generatedAt": int(time.time() * 1000),
        "audioSha256": shas, "notes": "",
        "entries": entries,
    }


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
