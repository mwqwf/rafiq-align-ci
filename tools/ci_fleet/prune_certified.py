# -*- coding: utf-8 -*-
"""ينقّي قائمةَ موجةٍ من **المشهودين سلفاً** — قياساً من الكتالوج لا من ترويسةٍ مكتوبة.

⛔ **سببه مقيسٌ بثمنه (2026-09-08 00:0xZ):** موجةُ `align` ‏34161827083 خصّصت
   **شريحةً كاملةً من عشرين** (‏5% من سقف الحساب المجانيّ، لساعات) لإعادة بناء
   `mrifai` — **وهو مشهودٌ مرقّى 20:35Z، أي قبل إطلاق الموجة بثلاثين دقيقة**.

⛔ **ولماذا لم يمنعه حارسُ «منجَزٌ سلفاً»؟** الحارسُ في `run_shard.sh:109` صحيحٌ
   ويسري (‏السطر 269 يمرّر `"1-114"` حرفاً، فشرطُه متحقّق) — **لكن
   `align.yml:273` يثبّت `FORCE_REALIGN: "1"` لكلّ تشغيلة**، والفرعُ الأول في
   الحارس يعلن أنّ المفتاح يرفعه. فالمكتوبُ عند المفتاح «يُطلبه المشغّلُ عمداً
   ولا يقع سهواً»، **والواقعُ أنه دائمٌ في كلّ موجة**.

⛔ **ولا يُنزع التثبيت**، وهذا مقيسٌ لا مظنون: موجاتُ إعادة البناء (`_gen1_redo`
   · `_resume`) **كلُّها إعادةُ محاذاةٍ مقصودةٌ بوصفةٍ أحدث**، وأكثرُ قرّائها لهم
   بصمةٌ في `timings-staging/` من الجيل الأول ⇒ نزعُ المفتاح **يُبطل الموجةَ
   كلَّها** (‏وهو D-178 نصّاً: «الفهرسُ القائم ليس منجَزاً بل منجَزٌ بعدّةٍ أخرى»).

⇒ **فالحارسُ الصحيح ليس عند التشغيل بل عند التوليد**: المشهودُ لا يُدرَج في
   قائمةِ إعادة بناءٍ أصلاً. و«مشهود» **حالةٌ في الكتالوج تتغيّر بين كتابةِ
   القائمة وإطلاقِها** — ولذلك تُقاس عند الإطلاق لا تُورَث من الترويسة:
   ترويسةُ `reciters_resume.tsv` تقول «كلُّ غيرِ مشهودٍ له صوت» **وكانت صادقةً
   حين كُتبت**، ثم شُهد `mrifai` فكذبت بلا أن يمسّها أحد.

⛔ **ولا يُنقّى ملفُّ موجةٍ جارية:** كلُّ شريحةٍ تحسب توزيعَها من الملفّ نفسِه
   (`assign_shard.py`)، فحذفُ صفٍّ يزيح ما بعده ⇒ إعادةُ تشغيلِ شريحةٍ تعمل على
   قرّاءٍ آخرين وقد يسقط قارئ. **يُنقّى قبل الإطلاق، لا أثناءه.**

    python prune_certified.py <القائمة>              # عرضٌ فقط
    python prune_certified.py <القائمة> --yes        # يكتب الملفّ منقّى
    python prune_certified.py --self-test
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CATALOG_KEY = "catalog/reciters.json"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def parse_rows(text):
    """يعيد [(نصُّ السطر, id, riwaya)] للأسطر ذاتِ المعنى، ويحفظ التعليقات كما هي."""
    out = []
    for line in text.splitlines():
        s = line.rstrip("\r")
        if not s.strip() or s.lstrip().startswith("#"):
            out.append((s, None, None))
            continue
        c = s.split("\t")
        if len(c) >= 2:
            out.append((s, c[0], c[1]))
        else:
            out.append((s, None, None))
    return out


def certified_set(catalog):
    """{(riwaya, id)} لكلِّ مشهودٍ في الكتالوج. البنية `riwayat[].reciters[]`."""
    got = set()
    for r in catalog.get("riwayat", []):
        riw = r.get("id") or r.get("key")
        for x in r.get("reciters", []):
            if x.get("ayahCertified") is True:
                got.add((str(riw), str(x.get("id"))))
    return got


def prune(text, certified):
    """يعيد (النصُّ المنقّى, المزالون). كلُّ مُزالٍ يُكتب سطرَ تعليقٍ بسببه —
    فلا يُعاد اكتشافُه ولا يُظنّ أنه سقط سهواً."""
    removed = []
    out = []
    for raw, rid, riw in parse_rows(text):
        if rid is not None and (riw, rid) in certified:
            removed.append((rid, riw))
            out.append(f"# ⏭ {rid}\t{riw} — أُزيل: **مشهودٌ سلفاً** في الكتالوج "
                       f"(‏قِيس عند التنقية). إعادةُ بنائه تُنفق شريحةً بلا مردودٍ "
                       f"على الرقم الرسميّ.")
            continue
        out.append(raw)
    return "\n".join(out) + "\n", removed


def self_test():
    cat = {"riwayat": [
        {"id": "hafs", "reciters": [
            {"id": "mrifai", "ayahCertified": True},
            {"id": "qasm", "ayahCertified": False},
            {"id": "obk"},
        ]},
        {"id": "warsh", "reciters": [{"id": "mrifai", "ayahCertified": False}]},
    ]}
    cs = certified_set(cat)
    assert cs == {("hafs", "mrifai")}, cs
    src = ("# ترويسة\n"
           "qasm\thafs\thttps://x/{surah:03d}.mp3\t1\n"
           "mrifai\thafs\thttps://y/{surah:03d}.mp3\t1\n"
           "mrifai\twarsh\thttps://z/{surah:03d}.mp3\t1\n"
           "obk\thafs\thttps://w/{surah:03d}.mp3\t1\n")
    out, rem = prune(src, cs)
    # (١) يُزال المشهودُ وحدَه
    assert [r[0] for r in rem] == ["mrifai"] and rem[0][1] == "hafs", rem
    # (٢) ⛔ والرواية جزءٌ من المفتاح: `mrifai` في ورشٍ غيرُ مشهودٍ فيبقى
    assert "mrifai\twarsh" in out, out
    # (٣) الترويسةُ والباقون كما هم
    assert "# ترويسة" in out and "qasm\thafs" in out and "obk\thafs" in out
    # (٤) السببُ مكتوبٌ في الملفّ لا في التقرير وحده
    assert "مشهودٌ سلفاً" in out
    # (٥) غيابُ الحقل ليس شهادةً (‏`obk` بلا `ayahCertified`)
    assert ("hafs", "obk") not in cs
    # (٦) القائمةُ النظيفةُ لا تُمسّ بحرف
    clean = "# ه\nqasm\thafs\tu\t1\n"
    out2, rem2 = prune(clean, cs)
    assert rem2 == [] and out2 == clean, (out2, rem2)
    print("✅ الاختبارُ الذاتيّ: ستُّ حالاتٍ خضراء")
    return 0


def load_catalog():
    import boto3
    c = json.load(open(os.path.join(ROOT, "secure", "r2_credentials.json"),
                       encoding="utf-8"))
    s3 = boto3.client("s3", endpoint_url=c["endpoint"],
                      aws_access_key_id=c["accessKeyId"],
                      aws_secret_access_key=c["secretAccessKey"],
                      region_name="auto")
    o = s3.get_object(Bucket=c["bucket"], Key=CATALOG_KEY)
    print(f"الكتالوج: {CATALOG_KEY} · LastModified {o['LastModified']:%Y-%m-%d %H:%M:%S}Z")
    return json.loads(o["Body"].read().decode("utf-8"))


def main():
    if "--self-test" in sys.argv:
        return self_test()
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    path = args[0]
    if not os.path.isabs(path):
        cand = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
        if os.path.exists(cand):
            path = cand
    text = open(path, encoding="utf-8").read()
    cs = certified_set(load_catalog())
    out, removed = prune(text, cs)
    rows = sum(1 for _, r, _ in parse_rows(text) if r)
    print(f"القائمة: {os.path.basename(path)} · صفوفٌ عاملة {rows} · "
          f"مشهودون في الكتالوج {len(cs)}")
    if not removed:
        print("✅ لا مشهودَ في القائمة — لا تنقية")
        return 0
    for rid, riw in removed:
        print(f"  ⏭ {rid} ({riw}) — مشهودٌ سلفاً")
    if "--yes" not in sys.argv:
        print(f"عرضٌ فقط — أضف --yes لكتابة {len(removed)} إزالة")
        return 0
    open(path, "w", encoding="utf-8", newline="\n").write(out)
    print(f"✍️ كُتبت — أُزيل {len(removed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
