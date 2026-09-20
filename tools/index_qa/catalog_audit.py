#!/usr/bin/env python3
"""تدقيقُ الكتالوج بعينِ المستخدم — لا بعينِ الأداة.

⛔⛔ **سببُه شكوى المالك 2026-09-20 نصّاً:** «بعض القرّاء يظهر اسماؤهم
باللاتينيّة في التطبيق العربيّ وبعضهم لا يشغّل حتّى قارئاً».
⇒ وهذان عطبان **يراهما المستخدمُ ولا يراهما أيٌّ من حُرّاسنا**: حُرّاسُ الفهرسة
كلُّها تسأل «أصحيحٌ توقيتُ الآية؟» ولا تسأل **«أيصلح هذا للعرض والتشغيل؟»**.
⭐ **والدرس: حارسٌ يقيس الصحّةَ ولا يقيس الصلاحيّةَ يُمرّر منتَجاً معطوباً سليمَ البيانات.**

يفحص ثلاثةَ أشياء لكلّ قارئٍ في `catalog/reciters.json`:
  ① **الاسمُ غيرُ عربيّ** — يُعرض للقارئ العربيّ حروفاً لاتينيّة، أو يساوي
     المعرّفَ نفسَه (`bilal`) وهو ليس اسماً بل مفتاحاً.
  ② **لا مصدرَ صوتٍ** (`base` فارغٌ أو غائب) ⇒ لا يُشغَّل شيءٌ البتّة.
  ③ **مصدَّقٌ بلا فهرس** أو **فهرسٌ بلا تصديق** — تناقضٌ يجعل القارئَ يظهر
     ولا يعمل.

⚖️ وهو **قارئٌ محض**: لا يكتب بايتاً واحداً، ولا يُصلح شيئاً — يُسمّي العطبَ
ويعدّه، والإصلاحُ قرارٌ يُتّخذ بعده بسببٍ مكتوب.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run import s3  # noqa: E402

# ⛔ المدى العربيّ الأساسيّ + التكميليّ + الحروفُ المرتبطة. ولا يكفي «فيه حرفٌ
#    عربيّ» حكماً: اسمٌ مثل «Bilal الشيخ» يمرّ به وهو معطوبٌ للعرض ⇒ الحكمُ
#    **بوجود لاتينيّةٍ لا بغياب عربيّة**.
LATIN = re.compile(r"[A-Za-z]")
ARABIC = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")


def collect(node, out=None, seen=None):
    """كلُّ قاموسٍ فيه `id` هو صفُّ قارئ — أيّاً كان عمقُه في الشجرة.

    ⭐ **ولا يُفترض الشكل**: الكتالوج قد يكون قائمةً، أو قاموساً بالرواية،
    أو قاموساً بالمعرّف. فالبحثُ عن **الصفة** لا عن **المسار**.
    """
    out = [] if out is None else out
    seen = set() if seen is None else seen
    if isinstance(node, dict):
        # ⛔⛔ **الحاوي يشبه الصفّ** (‏وقعت 2026-09-20): شكلُ الكتالوج
        #    `riwayat[6]` وكلُّ روايةٍ `{id, name, reciters[]}` — ففيها `id`
        #    و`name` كالصفّ تماماً، فتوقّف الجمعُ عندها وأعطى **6 قرّاء** بدل
        #    المئتين. ⭐ **والفارقُ أنّ الحاويَ يحمل أبناءً من جنسه.**
        kids = [v for v in node.values()
                if isinstance(v, list) and any(isinstance(x, dict) and "id" in x
                                               for x in v)]
        if kids:
            for v in kids:
                collect(v, out, seen)
            return out
        if "id" in node and not isinstance(node.get("id"), (dict, list)):
            if id(node) not in seen:
                seen.add(id(node))
                out.append(node)
            return out
        for k, v in node.items():
            # قاموسٌ مفتاحُه المعرّفُ وقيمتُه الصفُّ بلا حقل `id`
            if isinstance(v, dict) and "id" not in v and (
                    "name" in v or "base" in v or "mode" in v):
                v = dict(v, id=k)
                out.append(v)
            else:
                collect(v, out, seen)
    elif isinstance(node, list):
        for v in node:
            collect(v, out, seen)
    return out


def skeleton(node, depth=0, path="$"):
    """هيكلُ الوثيقة — **لأنّ التخمينَ أنفق دورتين** (2026-09-20).

    ⭐ حين لا تعرف شكلَ البيانات فاطبعه، ولا تبنِ مُحلِّلاً على ظنٍّ ثمّ
    تُصدّق مخرجَه. صفرُ صفوفٍ ثمّ ستّةٌ من 77 كيلوبايت: كلاهما ظنٌّ كاذب.
    """
    pad = "  " * depth
    if isinstance(node, dict):
        print(f"{pad}{path} {{}} · {len(node)} مفتاحاً: "
              f"{', '.join(list(node)[:12])}")
        if depth < 2:
            for k in list(node)[:4]:
                skeleton(node[k], depth + 1, k)
    elif isinstance(node, list):
        print(f"{pad}{path} [] · {len(node)} عنصراً")
        if node and depth < 3:
            skeleton(node[0], depth + 1, f"{path}[0]")
    else:
        print(f"{pad}{path} = {str(node)[:60]!r}")


def main():
    cl, bucket = s3()
    key = "catalog/reciters.json"
    for a in sys.argv[1:]:
        if a.startswith("--key="):
            key = a.split("=", 1)[1]
    raw = cl.get_object(Bucket=bucket, Key=key)["Body"].read()
    if "--skeleton" in sys.argv:
        print(f"المفتاح {key} · {len(raw):,} بايتاً")
        skeleton(json.loads(raw.decode("utf-8")))
        # وأسماءُ كلِّ ملفّات الكتالوج في الدلو — فلعلّ التطبيقَ يقرأ غيرَه
        print("\nملفّاتُ catalog/ في الدلو:")
        for o in (cl.list_objects_v2(Bucket=bucket, Prefix="catalog/")
                  .get("Contents") or []):
            print(f"   {o['Key']:<45} {o['Size']:>10,}")
        return 0
    doc = json.loads(raw.decode("utf-8"))
    rows = collect(doc)
    print(f"الكتالوج: {len(rows)} قارئاً · {len(raw):,} بايتاً\n")
    # ⛔⛔ **حارسٌ لا يجد شيئاً ليس حارساً ناجحاً** (‏وقعت 2026-09-20 نصّاً):
    #    قرأتُ الكتالوجَ بشكلٍ مفترَضٍ (`list` أو `reciters`) فخرجت بصفرِ صفوف
    #    وطبعتُ «✅ لا عطبَ ظاهر» — بينما شاشةُ المالك تعرض `kentaoui_warsh`
    #    و`asali_warsh` بحروفٍ لاتينيّة. ⇒ **الصفرُ ليس براءةً بل فشلُ قراءة.**
    if not rows:
        print("⛔ لم يُقرأ صفٌّ واحد — الشكلُ غيرُ متوقَّع، لا براءة.")
        print("   المفاتيحُ العليا: " + ", ".join(list(doc)[:20]
                                                 if isinstance(doc, dict) else ["<list>"]))
        return 2

    # ⭐ `--show a,b,c`: يعرض صفوفاً بأعيانها كما هي في الدلو — لأنّ الفصلَ
    #   بين «عطبٍ في بياناتي» و«عطبٍ في التطبيق» يحتاج مقابلةَ ما تعرضه
    #   الشاشةُ بما يقوله المصدرُ حرفاً، لا استنتاجاً من إحصاء.
    want = set()
    for a in sys.argv[1:]:
        if a.startswith("--show="):
            want |= {x.strip() for x in a.split("=", 1)[1].split(",") if x.strip()}
    if want:
        by = {r.get("id"): r for r in rows}
        for w in sorted(want):
            r = by.get(w)
            print(f"   {w:<20} " + (json.dumps(r, ensure_ascii=False)
                                    if r else "⛔ غيرُ موجودٍ في الكتالوج"))
        print()

    latin, no_name, no_base, odd = [], [], [], []
    for r in rows:
        rid = r.get("id") or "?"
        name = (r.get("name") or "").strip()
        base = (r.get("base") or r.get("urlTemplate") or "").strip()
        mode = r.get("mode") or "?"
        certified = r.get("ayahCertified")
        cov = r.get("ayahCoverage")

        if not name:
            no_name.append((rid, mode))
        elif LATIN.search(name):
            latin.append((rid, name, mode, "= المعرّف" if name == rid else ""))
        elif not ARABIC.search(name):
            no_name.append((rid, mode))

        if mode == "surah" and not base:
            no_base.append((rid, name or rid))

        # ⛔ التناقض: مصدَّقٌ بلا تغطية، أو تغطيةٌ بلا تصديق — كلاهما يُظهر
        #    القارئَ في الواجهة بحالٍ لا يطابق ما يجده المستخدمُ حين يضغط.
        if certified and not cov:
            odd.append((rid, name or rid, "مصدَّقٌ بلا تغطية"))
        elif cov and certified is False and mode == "surah":
            odd.append((rid, name or rid, "له تغطيةٌ وغيرُ مصدَّق"))

    def dump(title, items, fmt):
        print(f"{'⛔' if items else '✅'} {title}: {len(items)}")
        for it in items[:40]:
            print("   " + fmt(it))
        if len(items) > 40:
            print(f"   … و{len(items) - 40} غيرُها")
        print()

    dump("أسماءٌ فيها حروفٌ لاتينيّة (تُعرض للقارئ العربيّ)", latin,
         lambda x: f"{x[0]:<22} «{x[1]}» · {x[2]} {x[3]}")
    dump("بلا اسمٍ أصلاً", no_name, lambda x: f"{x[0]:<22} · {x[1]}")
    dump("بوضع السورة وبلا مصدرِ صوت (لا يُشغَّل شيء)", no_base,
         lambda x: f"{x[0]:<22} «{x[1]}»")
    dump("تناقضُ تصديقٍ وتغطية", odd, lambda x: f"{x[0]:<22} «{x[1]}» — {x[2]}")

    bad = len(latin) + len(no_name) + len(no_base) + len(odd)
    print(f"{'⛔ عطبٌ ظاهرٌ للمستخدم' if bad else '✅ لا عطبَ ظاهر'}: {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
