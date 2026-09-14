#!/usr/bin/env python3
"""🧩 دمجُ شرائح تدقيق العناوين (‏label_audit.py --shard i/k) في ملفٍّ واحدٍ للجزء — بلا تكرارٍ بالمفتاح، مع ملخّصٍ محسوبٍ من جديد.

    python tools/finetune/audit_merge.py g0.audit.json g0.s0.audit.json g0.s1.audit.json …
    python tools/finetune/audit_merge.py --selftest

⛔⛔ **ولماذا صار يرفض بدل أن يُكمل (‏D-487 · 2026-09-14):** كان الغائبُ يُطبع `⚠️ غائب` **ثمّ
يُمضى**، و`shards` تُكتب **عدَّ المعطياتِ لا عدَّ المقروء** ⇒ **شريحةٌ ضاعت والملفُّ يبدو تامّاً**:
مجموعةٌ ناقصةُ الرُّبع تُصفّى ويُدرَّب عليها، ولا شيءَ في الملفّ يقول ذلك. والدمجُ **خطوةُ تجميع
بيانات**: نقصُها الصامتُ أسوأُ من توقّفها المعلَن. ⇒ **الغائبُ يُوقف الدمجَ برمزِ خطأ**، ويُكتب
في المخرَج `shards_read` و`shards_requested` معاً.

⚠️ **والتصادمُ بالمفتاح يُعَدّ ويُعلَن** (‏درسُ D-293): المفتاحُ `key` (المسارُ النسبيّ) فريدٌ،
أمّا `id` (اسمُ الملفّ = رقمُ الآية) **فمشتركٌ بين 32 قارئاً وثلاثِ روايات**. فشريحةٌ قديمةٌ بلا
`key` تجعل الدمجَ **يطوي مقاطعَ مختلفةً في واحد** بلا صوتٍ ولا أثر.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from label_audit import summarize


def merge(srcs, out=None):
    """يدمج الشرائحَ ويُعيد الحصيلةَ — **دالّةٌ تُنادى من الاختبار كما تُنادى من الأمر**.

    ترجع: `items` المدموجة · `read`/`missing` · `collisions` (تصادمُ مفتاحٍ) ·
    `no_key` (بنودٌ بلا `key` ⇒ مفتاحُها `id` المشترك) · `partial`.
    """
    items, partial, read, missing = {}, False, [], []
    collisions, no_key, per_file = 0, 0, []
    for f in srcs:
        if not os.path.exists(f):
            missing.append(f)
            continue
        d = json.load(open(f, encoding="utf-8"))
        partial = partial or bool(d.get("partial"))
        got = d.get("items", [])
        for it in got:
            k = it.get("key")
            if not k:
                no_key += 1
                k = it["id"]
            if k in items:
                collisions += 1
            items[k] = it
        read.append(f)
        per_file.append((os.path.basename(f), len(got), bool(d.get("partial"))))
    res = list(items.values())
    body = None
    if res and not missing:
        body = {"summary": summarize(res),
                "worst": sorted(res, key=lambda r: r["match"])[:25],
                "items": res,
                # ⛔ **المقروءُ لا المطلوب** — وكلاهما يُكتب فلا يُخفى النقص
                "shards": len(read), "shards_read": len(read), "shards_requested": len(srcs)}
        if partial:
            body["partial"] = True
        if out:
            json.dump(body, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return {"items": res, "read": read, "missing": missing, "collisions": collisions,
            "no_key": no_key, "partial": partial, "per_file": per_file, "body": body}


def selftest():
    """🧪 حارسُ الدمج — بلا مجموعةٍ ولا صوت (‏D-487)."""
    import tempfile
    ok = True

    def say(good, line):
        nonlocal ok
        ok &= bool(good)
        print(("✅ " if good else "❌ ") + line)

    def item(key, i, m=0.9, rw="hafs"):
        return {"key": key, "id": i, "riwaya": rw, "match": m, "match_strict": m,
                "miss": 0, "sub": 0, "ins": 0, "n": 5}

    def shard(td, name, items, partial=False):
        p = os.path.join(td, name)
        body = {"summary": {}, "items": items}
        if partial:
            body["partial"] = True
        json.dump(body, open(p, "w", encoding="utf-8"), ensure_ascii=False)
        return p

    with tempfile.TemporaryDirectory() as td:
        a = shard(td, "s0.json", [item("g0/hafs/r1/1_1.flac", "1_1.flac"),
                                  item("g0/hafs/r1/1_2.flac", "1_2.flac")])
        b = shard(td, "s1.json", [item("g0/warsh/r2/1_1.flac", "1_1.flac", 0.7, "warsh")])
        out = os.path.join(td, "merged.json")

        # ① الدمجُ السويّ: ثلاثةُ مقاطعَ من شريحتَين — **ولا يطوي المفتاحَ المشترك `1_1.flac`**
        r = merge([a, b], out)
        say(len(r["items"]) == 3 and r["collisions"] == 0 and not r["missing"],
            f"دمجٌ سويّ: {len(r['items'])} مقاطعَ · تصادم {r['collisions']} "
            f"(‏و`id` مشتركٌ بين اثنين — والمفتاحُ الفريدُ يفرّقهما · D-293)")
        body = json.load(open(out, encoding="utf-8"))
        say(body["shards_read"] == 2 and body["shards_requested"] == 2 and body["summary"]["n"] == 3,
            f"والمخرَجُ يقول ما قرأ: {body['shards_read']}/{body['shards_requested']} · ن={body['summary']['n']}")

        # ②⛔ **شريحةٌ غائبةٌ لا تمرّ صامتةً** — وهذا بندُ D-487 نفسُه
        r = merge([a, os.path.join(td, "لا-وجود.json")], out)
        say(r["missing"] and r["body"] is None,
            f"غائبٌ: لا مخرَجَ البتّة · المفقود {len(r['missing'])} (⛔ ولا يُكتب ملفٌّ ناقصٌ يبدو تامّاً)")

        # ③ بندٌ بلا `key` يُعَدّ — فمفتاحُه `id` المشتركُ بين القرّاء والروايات
        c = shard(td, "s2.json", [{"id": "1_1.flac", "riwaya": "qalun", "match": 0.8,
                                   "match_strict": 0.8, "miss": 0, "sub": 0, "ins": 0, "n": 5}])
        r = merge([a, c])
        say(r["no_key"] == 1, f"بلا مفتاحٍ: عُدّ {r['no_key']} (‏تحذيرٌ يُقرأ لا صمت)")

        # ④ والتصادمُ الحقيقيُّ يُعَدّ: مفتاحٌ واحدٌ في شريحتَين (‏شريحتان متداخلتان)
        d = shard(td, "s3.json", [item("g0/hafs/r1/1_1.flac", "1_1.flac", 0.5)])
        r = merge([a, d])
        say(r["collisions"] == 1 and len(r["items"]) == 2,
            f"تداخلُ شريحتَين: تصادم {r['collisions']} · والباقي {len(r['items'])} (الأخيرُ يغلب)")

        # ⑤ `partial` يسري من أيّ شريحة
        e = shard(td, "s4.json", [item("g0/hafs/r1/2_1.flac", "2_1.flac")], partial=True)
        r = merge([a, e], out)
        say(r["partial"] and json.load(open(out, encoding="utf-8")).get("partial") is True,
            "و«ناقصٌ» يسري من أيّ شريحةٍ إلى المخرَج")

        # ⑥⛔ وصفرُ بنودٍ لا يُكتب ولا يُقرأ سلامة
        f0 = shard(td, "s5.json", [])
        r = merge([f0])
        say(not r["items"] and r["body"] is None, "وصفرُ بنودٍ: لا مخرَجَ ولا شهادة")

    print("\n" + ("✅ الدمجُ يفعل ما يدّعي — ولا يكتب ملفّاً ناقصاً يبدو تامّاً"
                  if ok else "❌ الدمجُ لا يفعل ما يدّعي"))
    return 0 if ok else 1


def main():
    if "--selftest" in sys.argv:
        return selftest()
    if len(sys.argv) < 3:
        sys.exit("⛔ الاستعمال: audit_merge.py <المخرَج> <شريحة> [شرائحُ أخرى] — أو `--selftest`")
    out, srcs = sys.argv[1], sys.argv[2:]
    r = merge(srcs, out)
    for name, n, part in r["per_file"]:
        print(f"  {name}: {n} {'(ناقص)' if part else ''}")
    if r["no_key"]:
        print(f"⚠️ **{r['no_key']} بنداً بلا `key`** ⇒ مفتاحُها `id` وهو مشتركٌ بين القرّاء "
              f"والروايات (‏D-293): قد تُطوى مقاطعُ مختلفةٌ في واحد.")
    if r["collisions"]:
        print(f"⚠️ **{r['collisions']} تصادمَ مفتاحٍ** (شرائحُ متداخلةٌ أو مفاتيحُ مكرّرة) — الأخيرُ يغلب.")
    if r["missing"]:
        sys.exit("⛔ **شرائحُ غائبة** ⇒ لم يُكتب شيء: " + " · ".join(r["missing"])
                 + "\n   ولو كُتب لبدا الملفُّ تامّاً وهو ناقص — وعليه تُصفّى مجموعةٌ ويُدرَّب نموذج (D-487).")
    if not r["items"]:
        sys.exit("⛔ لا بنودَ للدمج")
    s = r["body"]["summary"]
    print(f"✅ {out}: {s['n']} مقطعاً · من {r['body']['shards_read']}/{r['body']['shards_requested']} شريحةً "
          f"· متوسّط {s['mean']:.3f} · دون 0.85: {s['below_0.85']*100:.1f}٪ · دون 0.9: {s['below_0.9']*100:.1f}٪ "
          f"· بالرواية {s['dropped_at_0.85_by_riwaya']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
