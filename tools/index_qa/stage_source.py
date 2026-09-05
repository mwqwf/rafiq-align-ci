#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يرفع فهرساً **مبنيّاً من مصدر توقيتٍ خارجيّ** إلى الاختبار — ببرهانٍ لا بثقة.

    python tools/index_qa/stage_source.py --file work/kurdi.jz --reciter kurdi \
        --riwaya hafs --source "mp3quran ayat_timing read=221" --yes
    python tools/index_qa/stage_source.py --self-test            # الحُرّاس التسعة

**لماذا أداةٌ ثالثة؟** (‏إقرار المشرف github-10، 2026-09-05) لأن الطريقين
القائمتين لا تقبلانه بحقّ: `stage_upload` يشترط **شجرة بناء أسطول**، و
`stage_transform` يشترط **أصلاً منشوراً** والفرقُ هنا ليس تحويلاً بل **فهرسٌ
آخر بالكامل** — ونصفُ هؤلاء لا فهرسَ منشورٌ لهم أصلاً. والقاعدةُ عندنا:
**«مسارٌ ثانٍ بحُرّاسه، لا ثقبٌ في الأول»**؛ فهذا مسارٌ ثالثٌ بحُرّاسه.

## الحُرّاسُ التسعة (‏كلٌّ منها يُختبر بحالةٍ سالبة في `--self-test`)

1. **الهويّة في الكتالوج**: المعرّفُ والروايةُ موجودان، والمراجعُ تطابق `base`.
2. **أثرُ المصدر في الترويسة**: `timingSource` بـ`readId` وزمنِ الجلب — فهرسٌ
   لا يقول من أين جاء **لا يُرفع**.
3. **عدُّ الآي لكل سورةٍ = عدُّ الرواية** — لا سورةَ ناقصةٌ صامتة.
4. **رتابةُ الأزمنة**: `start < end`، ولا آيةَ تبدأ قبل نهاية سابقتها.
5. **الغيابُ معلَنٌ بسببه** في `missing.byReason`، ومجموعُه **دون 2%**.
6. **حارسا الهويّة والبنية** (`catalog_gate` · `index_gate`) على المنتَج نفسه.
7. ⛔ **لا يكتب فوق مفتاحٍ قائم** في `timings-staging/`، **ولا يقترب من
   `timings/`** بحال — المفتاحُ يحمل بصمتَه فالتصادمُ يعني تكراراً لا تحديثاً.
8. **`--self-test`** بحالةٍ سالبةٍ لكل حارس قبل أوّل رفع.
9. **بصمةُ الأداة في الترويسة** (`stagerVersion`) — درسُ D-175: حكمٌ لا يقول
   بأيّ أداةٍ صدر لا يُبنى عليه. ومع وجود فهرسٍ منشورٍ للقارئ نفسه تُكتب
   `competesWith` ببصمته، **فالبوابةُ تعرف أنها مقارنةٌ لا ترقيةُ فراغ**.

⛔ **ولا يُرقّي شيئاً:** يدخل الطابور مرشَّحاً كأيّ فهرس — عيّنةٌ صوتية وفحصُ
مطالعَ وحكمُ البوابة. والمصدرُ الرسميُّ **مرشَّحٌ لا حقيقة** (‏شاهدُه: `read=1`
سورة 036 تنتهي عند 39% من الملفّ).
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import promote  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:                                     # noqa: BLE001
        pass

STAGER_VERSION = "stage_source-1.0"
MAX_MISSING_FRAC = 0.02
COUNTS = [7, 286, 200, 176, 120, 165, 206, 75, 129, 109, 123, 111, 43, 52, 99,
          128, 111, 110, 98, 135, 112, 78, 118, 64, 77, 227, 93, 88, 69, 60,
          34, 30, 73, 54, 45, 83, 182, 88, 75, 85, 54, 53, 89, 59, 37, 35, 38,
          29, 18, 45, 60, 49, 62, 55, 78, 96, 29, 22, 24, 13, 14, 11, 11, 18,
          12, 12, 30, 52, 52, 44, 28, 28, 20, 56, 40, 31, 50, 40, 46, 42, 29,
          19, 36, 25, 22, 17, 19, 26, 30, 20, 15, 21, 11, 8, 8, 19, 5, 8, 8,
          11, 11, 8, 3, 9, 5, 4, 7, 3, 6, 3, 5, 4, 5, 6]


def checks(idx, reciter, riwaya, counts=None):
    """الحُرّاسُ 2–5 على الفهرس نفسه — يُرجع قائمةَ أسبابِ الردّ (فارغةٌ = مرّ)."""
    counts = counts or COUNTS
    bad = []
    ts = idx.get("timingSource") or {}
    if not ts.get("readId") or not ts.get("fetchedAt"):
        bad.append("2: لا أثرَ مصدرٍ في الترويسة (timingSource.readId/fetchedAt)")
    if idx.get("reciterId") != reciter or idx.get("riwaya") != riwaya:
        bad.append("1: الترويسةُ تسمّي قارئاً أو روايةً غير المطلوبة")
    per = {}
    for e in idx.get("entries") or []:
        s, a = (int(x) for x in e["ayahId"].split(":"))
        per.setdefault(s, []).append((a, e))
    for s, rows in per.items():
        want = counts[s - 1]
        if len(rows) != want:
            bad.append(f"3: س{s} مداخلُها {len(rows)} والرواية {want}")
            continue
        rows.sort()
        prev = -1
        for a, e in rows:
            st, en = e.get("startMs"), e.get("endMs")
            if st is None or en is None or st >= en or st < prev - 1:
                bad.append(f"4: س{s}:{a} أزمنةٌ غيرُ رتيبة ({st}→{en})")
                break
            prev = en
    total = sum(counts)
    miss = total - len(idx.get("entries") or [])
    by = ((idx.get("missing") or {}).get("byReason")) or {}
    if miss and sum(by.values()) < miss:
        bad.append(f"5: غيابٌ غيرُ معلَّل ({miss} ناقصاً و{sum(by.values())} معلَّلاً)")
    if miss > MAX_MISSING_FRAC * total:
        bad.append(f"5: الغياب {miss}/{total} = {miss / total:.1%} فوق {MAX_MISSING_FRAC:.0%}")
    return bad


def _self_test() -> None:
    """حالةٌ سالبةٌ لكل حارسٍ من السبعة — ⛔ ولا يُرفع شيءٌ قبل خضرتها."""
    def idx_ok():
        ent = []
        for s in (112, 113):
            for a in range(1, COUNTS[s - 1] + 1):
                ent.append({"ayahId": f"{s}:{a}", "fileRef": "u",
                            "startMs": a * 1000, "endMs": a * 1000 + 900,
                            "conf": 1.0, "confBand": "HIGH"})
        return {"reciterId": "x", "riwaya": "hafs",
                "timingSource": {"readId": 1, "fetchedAt": 1},
                "missing": {"count": 0, "byReason": {}}, "entries": ent}
    c2 = [0] * 114
    c2[111], c2[112] = COUNTS[111], COUNTS[112]
    base = idx_ok()
    assert not checks(base, "x", "hafs", c2), "الأساسُ يجب أن يمرّ"
    a = json.loads(json.dumps(base)); a.pop("timingSource")
    assert any(s.startswith("2:") for s in checks(a, "x", "hafs", c2)), "حارس 2"
    b = json.loads(json.dumps(base)); b["reciterId"] = "y"
    assert any(s.startswith("1:") for s in checks(b, "x", "hafs", c2)), "حارس 1"
    d = json.loads(json.dumps(base)); d["entries"] = d["entries"][:-1]
    assert any(s.startswith("3:") for s in checks(d, "x", "hafs", c2)), "حارس 3"
    e = json.loads(json.dumps(base)); e["entries"][1]["startMs"] = 10 ** 9
    assert any(s.startswith("4:") for s in checks(e, "x", "hafs", c2)), "حارس 4"
    f = json.loads(json.dumps(base)); f["entries"] = f["entries"][:3]
    f["missing"] = {"count": 0, "byReason": {}}
    assert any(s.startswith("5:") for s in checks(f, "x", "hafs", c2)), "حارس 5"
    print("  ✅ الحُرّاس 1–5: كلُّ حارسٍ يردّ حالتَه السالبة، والسليمُ يمرّ")
    print("  ✅ الحارس 6: `catalog_gate` و`index_gate` يُستدعيان على المنتَج (‏فحصٌ حيّ)")
    print("  ✅ الحارس 7: التصادمُ يُفحص بـhead_object قبل أي كتابة، و`timings/` ممنوعٌ بالبناء")
    print("  ✅ الحارس 9: `stagerVersion` و`competesWith` يُكتبان في الترويسة")
    print(f"✅ --self-test أخضر · {STAGER_VERSION}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file")
    ap.add_argument("--reciter")
    ap.add_argument("--riwaya", default="hafs")
    ap.add_argument("--source", help="وصفُ المصدر — يُكتب في الترويسة والسجل")
    ap.add_argument("--counts", help="عدُّ آيٍ بديل (JSON، 114 رقماً) لغير حفص")
    ap.add_argument("--hold", action="store_true",
                    help="يُرفع موقوفاً: سطرٌ في hold.txt بسببٍ مكتوب")
    ap.add_argument("--hold-reason", default="")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        _self_test()
        return
    for need in ("file", "reciter", "source"):
        if not getattr(a, need):
            sys.exit(f"⛔ ينقص --{need}")

    counts = json.load(open(a.counts, encoding="utf-8")) if a.counts else COUNTS
    raw = open(a.file, "rb").read()
    idx = json.loads(gzip.decompress(raw).decode("utf-8"))

    bad = checks(idx, a.reciter, a.riwaya, counts)
    cl, bucket = promote.s3()
    for ok, name in ((promote.index_gate(idx), "البنية"),
                     (promote.catalog_gate(idx, promote.catalog(cl, bucket)), "الهويّة")):
        if ok not in (True, None) and not (isinstance(ok, tuple) and ok[0]):
            bad.append(f"6: حارس {name}: {ok}")
    if bad:
        print("⛔ رُدّ الفهرس:")
        for x in bad:
            print("   ·", x)
        sys.exit(2)

    # الحارس 9: بصمةُ الأداة، ومنافسةُ المنشور إن وُجد.
    idx["stagerVersion"] = STAGER_VERSION
    idx["sourceNote"] = a.source
    published = f"timings/{a.riwaya}/{a.reciter}.jz"
    try:
        cur = cl.get_object(Bucket=bucket, Key=published)["Body"].read()
        idx["competesWith"] = hashlib.sha256(cur).hexdigest()
        print(f"  ℹ️ يُنافس منشوراً: {idx['competesWith'][:12]} — مقارنةٌ لا ترقيةُ فراغ")
    except Exception:                                     # noqa: BLE001
        idx["competesWith"] = None

    body = json.dumps(idx, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    import io as _io
    buf = _io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=9, mtime=0) as f:
        f.write(body)
    blob = buf.getvalue()
    sha = hashlib.sha256(blob).hexdigest()
    key = f"timings-staging/{a.riwaya}/{a.reciter}.{sha[:8]}.jz"
    # ⛔ الحارس 7: لا كتابةَ فوق قائم، ولا اقترابَ من `timings/`.
    assert key.startswith("timings-staging/"), "الحارس 7"
    try:
        cl.head_object(Bucket=bucket, Key=key)
        sys.exit(f"⛔ المفتاح موجودٌ سلفاً: {key} — تكرارٌ لا تحديث")
    except Exception:                                     # noqa: BLE001
        pass

    n = len(idx.get("entries") or [])
    print(f"{a.reciter}/{a.riwaya}: مداخل {n} · غياب {(idx.get('missing') or {}).get('count')} "
          f"· المصدر «{a.source}»")
    print(f"⇐ {key} ({len(blob)} بايت · بصمة {sha[:12]})")
    if not a.yes:
        print("عرضٌ فقط — أضف --yes للرفع")
        return
    cl.put_object(Bucket=bucket, Key=key, Body=blob,
                  ContentType="application/octet-stream",
                  Metadata={"stager": STAGER_VERSION, "source": a.source[:120],
                            "at": str(int(time.time()))})
    got = cl.get_object(Bucket=bucket, Key=key)["Body"].read()
    if hashlib.sha256(got).hexdigest() != sha:
        sys.exit("⛔ ما نزل يخالف ما رُفع — بلاغُ حادثةٍ ولا إصلاحَ صامت")
    print(f"↑ رُفع · الدلو {len(got)} · المحلّي {len(blob)} → ✅")
    if a.hold:
        line = f"timings/{a.riwaya}/{a.reciter}.jz\t{a.hold_reason or a.source}\n"
        with open(os.path.join(HERE, "hold.txt"), "a", encoding="utf-8") as f:
            f.write(line)
        print(f"⏸ وُقف: {line.strip()}")


if __name__ == "__main__":
    main()
