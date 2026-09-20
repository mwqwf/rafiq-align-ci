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


def main():
    cl, bucket = s3()
    raw = cl.get_object(Bucket=bucket, Key="catalog/reciters.json")["Body"].read()
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
