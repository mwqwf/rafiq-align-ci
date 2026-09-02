#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""حارس تغطية الآي — يُستدعى قبل كل رفع، ويُرجع 0 للقبول و1 للرفض.

    python tools/cloud/coverage_guard.py --index work/timings_warsh_x.jz

⛔ **لماذا لا تكفي عتبة العدد المطلق:** حارس `MIN_SHIPPED` يقبل أي فهرس فيه
≥5600 مدخلاً، فمرّ `m_sayed_warsh` بـ5906 **وينقصه 330 آية** — لأن 5906 أكبر
من العتبة وكفى. والعدد لا يرى **أين** وقع النقص ولا **أيَّ** آيٍ ضاع.

وقياس github-8e كشف بصمةً سببية: الآيات الغائبة عند `m_sayed_warsh` وسيط
طولها **4 كلمات** ووسيط المصحف 10، و54% منها أربع كلمات أو أقل. أي أن
الغياب **منحازٌ للقصر**: الآية القصيرة داخل مقطعٍ موصول لا تنال حدّاً فتُبتلع
في جارتها. وهذا عطبُ محاذاةٍ لا صمتٌ عارض — ولذلك يُرفض ولو قلّ عدده، بينما
غيابٌ غير منحاز (كـ`basit_warsh`: وسيط 10 كلمات) عِلّتُه أخرى تُحتمل بحدّ.

⚠️ والحارس **سكربتٌ مستقل يُستدعى بعملية جديدة عند كل قارئ**، لا دالةٌ داخل
السائق — فتعديل عتباته أو منطقه يسري عند حدّ القارئ التالي بلا إعادة تشغيل
الأسطول (درس D-064: كل إعادة تشغيل تُسقط السورة الجارية في كل عملية).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "alignment"))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

# تُقرأ من البيئة كي تُضبط من `/root/fleet.env` بلا لمس الشيفرة.
MAX_MISSING_FRAC = float(os.environ.get("GUARD_MAX_MISSING_FRAC", "0.02"))
SHORT_BIAS_RATIO = float(os.environ.get("GUARD_SHORT_BIAS_RATIO", "0.5"))
# ⛔ **حدٌّ أدنى لاختبار الانحياز — وإلا عاقب أنظفَ الفهارس:** الاختبار يقارن
# وسيط طول المفقودة بوسيط المصحف، وفهرسٌ لم يفقد إلا **18 آية** كلُّها فواتحُ
# وقصارٌ (‏42:2 «عٓسٓقٓ» · 37:2 · 52:2 · 90:13) يبدو «منحازاً إلى القصر» وهو
# أنظف ما قِسناه (‏0.5% عطب على 200 حدّ). ولذلك يُشترط قدرٌ من الغياب قبل أن
# يُحكم على شكله: **50 مفقودة أو 1% من المصحف** أيّهما أقلّ.
# (‏github-7e بقرار المشرف 2026-09-02، **بعد** صدور حكم `husary_warsh` لا
# قبله — ويُسجَّل ذلك في `PROMOTIONS.md` كي لا يُقال إن الحارس فُصِّل على
# الحالة التي بُني لها.)
MIN_MISSING_FOR_BIAS = int(os.environ.get("GUARD_MIN_MISSING_FOR_BIAS", "50"))
MIN_MISSING_FRAC_FOR_BIAS = float(
    os.environ.get("GUARD_MIN_MISSING_FRAC_FOR_BIAS", "0.01"))


def bias_testable(n_miss, total):
    """هل الغياب كافٍ ليُحكم على **شكله** لا على عدده وحده؟"""
    return n_miss >= min(MIN_MISSING_FOR_BIAS,
                         max(1, int(total * MIN_MISSING_FRAC_FOR_BIAS)))


def _median(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else 0


def assess(ti):
    """مقاييس التغطية لفهرسٍ **مبنيّ في الذاكرة** — بلا حكم.

    فُصلت عن `check` كي يستدعيها كاتب الترويسة (`tools/alignment/validate.py`)
    فتكون **المنطقُ واحداً في موضعين لا نسختين تتباعدان**: الحارس يحكم بالعتبات،
    والترويسة تحمل الأرقام نفسها التي حكم بها. (طلب المشرف github-f4، وباسمٍ
    متّفقٍ عليه مع github-b9 صاحب الملف.)
    """
    from common import load_text, load_index  # noqa: PLC0415

    text = load_text(ti["riwaya"])              # 6236 نصاً بفهرس كوفي موحّد
    words = [len(t.split()) for t in text]
    med_all = _median(words)
    # ⛔ الغياب = **لا مدخل أصلاً**. أما المدخل الموسوم LOW فحدٌّ موجود ضعيف
    # الثقة، لا صوتٌ ضائع — وعدُّه غياباً ضخّم الرفض ثلاثة أضعاف (a_majed:
    # 256 «غياباً» منها 188 LOW). يُبلَّغ رقماً منفصلاً ولا يدخل الحكم.
    present = {e["ayahId"] for e in ti.get("entries", [])}
    low_n = sum(1 for e in ti.get("entries", []) if e.get("confBand") == "LOW")
    idx = load_index()
    missing_lens, missing_ids = [], []
    k = 0
    for s in idx["surahs"]:
        for a in range(1, s["ayahs"] + 1):
            if f"{s['n']}:{a}" not in present:
                missing_lens.append(words[k])
                missing_ids.append(f"{s['n']}:{a}")
            k += 1
    n_miss = len(missing_lens)
    med_miss = _median(missing_lens)
    return {"total": k, "count": n_miss, "frac": (n_miss / k if k else 0.0),
            "medianLen": med_miss, "medianLenAll": med_all,
            "biasedShort": bool(bias_testable(n_miss, k) and med_all
                                and med_miss < SHORT_BIAS_RATIO * med_all),
            "ids": missing_ids}


def check(index_path):
    from common import load_text, read_jz  # noqa: PLC0415

    ti = read_jz(index_path)
    riwaya = ti["riwaya"]
    text = load_text(riwaya)                    # 6236 نصاً بفهرس كوفي موحّد
    words = [len(t.split()) for t in text]
    med_all = _median(words)

    # ⛔ الغياب = **لا مدخل أصلاً**. أما المدخل الموسوم LOW فحدٌّ موجود ضعيف
    # الثقة، لا صوتٌ ضائع — وعدُّه غياباً ضخّم الرفض ثلاثة أضعاف (a_majed:
    # 256 «غياباً» منها 188 LOW). يُبلَّغ رقماً منفصلاً ولا يدخل الحكم.
    present = {e["ayahId"] for e in ti.get("entries", [])}
    low_n = sum(1 for e in ti.get("entries", []) if e.get("confBand") == "LOW")
    # الفهرس الخطّي (0..6235) ⇒ "surah:ayah" عبر حدود السور
    from common import load_index                # noqa: PLC0415
    idx = load_index()
    missing_lens, missing_ids = [], []
    k = 0
    for s in idx["surahs"]:
        for a in range(1, s["ayahs"] + 1):
            if f"{s['n']}:{a}" not in present:
                missing_lens.append(words[k])
                missing_ids.append(f"{s['n']}:{a}")
            k += 1
    total = k
    n_miss = len(missing_lens)
    frac = n_miss / total if total else 0.0
    med_miss = _median(missing_lens)

    if frac > MAX_MISSING_FRAC:
        return 1, (f"غياب حقيقي {n_miss}/{total} ({frac*100:.1f}%) > الحد "
                   f"{MAX_MISSING_FRAC*100:.1f}% (وLOW {low_n} لا تُعدّ) "
                   f"— أمثلة: {', '.join(missing_ids[:6])}")
    # بصمة الابتلاع: الغائب أقصر بكثير من وسيط المصحف
    if bias_testable(n_miss, total) and med_all and med_miss < SHORT_BIAS_RATIO * med_all:
        return 1, (f"⛔ انحياز القصر: وسيط الغائب {med_miss} كلمة مقابل {med_all} للمصحف "
                   f"({n_miss} آية) — بصمة ابتلاعٍ في المحاذاة لا صمتٍ عارض؛ "
                   f"أمثلة: {', '.join(missing_ids[:6])}")
    return 0, (f"تغطية {total-n_miss}/{total} · غياب {n_miss} · "
               f"وسيط الغائب {med_miss}/{med_all} · LOW {low_n} (لا تُعدّ غياباً)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    a = ap.parse_args()
    try:
        rc, why = check(a.index)
    except Exception as ex:  # حارسٌ يسقط لا يمرّر — الفشل مغلق
        print(f"⛔ حارس التغطية أخفق ({ex}) — لا رفع", flush=True)
        return 1
    print(why, flush=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
