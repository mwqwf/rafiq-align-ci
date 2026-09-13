#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🗺️ **حارسُ التغطية الروائيّة** — أيُّ أداةٍ تدور على ثلاثٍ والمصحفُ ستّ؟ (‏D-428)

## لِمَ وُجد — ثلاثُ ثغراتِ تغطيةٍ في يومٍ واحد
| اليوم | الثغرة | الأثر |
|---|---|---|
| D-426 | حلقةُ تدقيق المِسطرة (`T=3`) على ثلاث | شعبةُ والدوريُّ والسوسيُّ **لم تُدقَّق قطّ** |
| D-427 | `parity_full.RIWAYAT` ثلاث | رقما **D-416 وD-419** على نصف المصحف روايةً |
| D-401 (سابقاً) | `riwaya_surface.RIWAYAT` ثلاث | «حدُّ الثلاثِ حدُّ أداةٍ لا حدُّ بيانات» — **1968 لا 598** |

⛔ **والنمطُ أخطرُ من أفراده:** في D-401 عولجت الثغرةُ بأداةٍ **موازية** (`riwaya_floor_six.py`)
لا بإصلاح المصدر ⇒ فبقي `riwaya_surface` على ثلاث، **وبقي كلُّ ما يرث `RIWAYAT` منه على ثلاث**
(`riwaya_gate_arms` · `riwaya_second_layer`). فالعلاجُ الموضعيُّ يترك الجذرَ ويُطمئن.

⇒ فهذا يمسح العدّةَ كلَّها مسحاً **آليّاً** ويطبع ما ضاق، كي لا تُكتشف الرابعةُ بالصدفة.

## ما يفعله
يقرأ كلَّ `tools/tasmi_bench/*.py` ويلتقط **أسماءَ الروايات المذكورةَ نصّاً** في كلِّ ملفّ،
ثمّ يصنّفه:
- ✅ **ستّ** — يغطّي المصحفَ كلَّه.
- 📌 **ضيّقٌ بمُدخَله** — يتعلّق بفرضيّاتِ شوطٍ أو عيّنةِ صوتٍ أو خطّةِ حقن ⇒ ضيقُه **حدُّ بيانات**.
- 🧬 **وارث** — يأخذ قائمتَه من ملفٍّ آخر (`RIWAYAT = RS.RIWAYAT`) ⇒ **النظرُ في مصدره لا فيه**.
- 🚨 **نصّيٌّ محضٌ وضيّق** — لا يقرأ إلّا نصَّ المصحف (‏وهو متاحٌ للستِّ) ولا يحدّه مُدخَل
  ⇒ **لا سببَ لضيقه إلّا أنّ أحداً لم يوسّعه**. وهذه قائمةُ النظر.

    python riwaya_coverage_audit.py              # يطبع الضيّقَ وحدَه
    python riwaya_coverage_audit.py --all        # يطبع كلَّ ملفّ

⚠️ **وهذا كشفٌ لا حكم:** الملفُّ الضيّقُ قد يكون ضيقُه صواباً (‏عيّنةُ `g1` ثلاثيّةُ الرواية
بالبناء — D-418). فالمخرَجُ **قائمةُ نظرٍ** لا قائمةَ عطب، ولا يُوسَّع شيءٌ إلّا بعد فحصه.
⛔ ولا يُشحن بهذا شيء.
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SIX = ("hafs", "warsh", "qalun", "shuba", "douri", "sousi")
# 🔎 **المعيارُ ليس «أذكر عذراً في متنك»** — جُرّب ذلك أوّلاً فأعذر كلَّ ملفٍّ تقريباً لورودِ
#    كلمةٍ عابرةٍ في شرحه (‏1 من 35 وحدَه بقي متّهماً) ⇒ حيلةٌ تُطمئن ولا تكشف. والمعيارُ
#    المعتمدُ **يُفحص آليّاً**: أيعتمد الملفُّ على مُدخَلٍ **محصورٍ بطبيعته** (‏فرضيّاتٌ من
#    شوطٍ · عيّنةُ صوتٍ · خطّةُ حقن)؟ فإن كان فضيقُه **حدُّ بيانات**؛ وإن كان يقرأ نصَّ
#    المصحف وحدَه (`load_text`) فـ**لا سببَ لضيقه إلّا أنّ أحداً لم يوسّعه**.
BOUND = ("hyps", "sample.json", "inject_plan", "fetch_audio", ".wav", "--set ",
         "work/emu", "hyps_", "audio")


def scan_file(path):
    src = open(path, encoding="utf-8").read()
    found = {r for r in SIX if re.search(r'["\']%s["\']' % r, src)}
    if not found:
        return None
    # ⚠️ **حدُّ المسح يُقال:** يقرأ **الأسماءَ المكتوبةَ نصّاً**. فملفٌّ يرث قائمتَه من غيره
    #    (`RIWAYAT = RS.RIWAYAT`) يبدو ضيّقاً وهو تابعٌ ⇒ يُوسَم **وارثاً**، والنظرُ في مصدره.
    inherits = bool(re.search(r"(RIWAYAT|SIX|ALL_RIWAYAT)\s*=\s*\w+\.", src))
    # يقرأ نصَّ المصحف (‏متاحٌ للستِّ) ولا يتعلّق بمُدخَلٍ محصور ⇒ ضيقُه حدُّ أداة.
    text_only = ("load_text" in src) and not any(b in src for b in BOUND)
    return found, (not text_only) or inherits, src.count("\n") + 1, inherits


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    rows = []
    for name in sorted(os.listdir(HERE)):
        if not name.endswith(".py") or name == os.path.basename(__file__):
            continue
        r = scan_file(os.path.join(HERE, name))
        if r:
            rows.append((name,) + r)

    six = [r for r in rows if len(r[1]) == 6]
    narrow = [r for r in rows if len(r[1]) < 6]
    bare = [r for r in narrow if not r[2]]
    print(f"ملفّاتٌ تذكر روايةً: **{len(rows)}** · تغطّي الستَّ **{len(six)}** ✅ · "
          f"أضيقُ منها **{len(narrow)}** (‏منها **{len(bare)}** نصّيّةٌ محضةٌ لا يحدّها مُدخَل) "
          f"{'🚨' if bare else '✅'}")
    show = rows if args.all else narrow
    if show:
        print(f"\n{'الملفّ':32s} {'رواياتٌ مذكورة':>14s}  الحال")
        for name, found, excused, _n, inh in sorted(show, key=lambda x: (len(x[1]), x[0])):
            mark = "✅" if len(found) == 6 else ("🧬" if inh else ("📌" if excused else "🚨"))
            miss = " · ".join(r for r in SIX if r not in found) or "—"
            print(f"{mark} {name:30s} {len(found):>6d}/6      ينقصه: {miss}")
    return 1 if bare else 0


if __name__ == "__main__":
    sys.exit(main())
