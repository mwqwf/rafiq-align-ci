# -*- coding: utf-8 -*-
"""تجربة العلاج (ب): تطبيعٌ واعٍ برسم الرواية في مطابقة مراسي الصقل.

⛔ **لا يلمس `tools/alignment_v2/refine.py`** (ملك rafiq-words): يستورده كما هو
ويستبدل **دالة المطابقة وحدها** (`nw_align`) بغلافٍ يوحّد صور الرسم على
الطرفين قبل المحاذاة. فإن أثبتت التجربة نفسها فالإدماج بيد صاحب الملف.

**ما يوحَّد** (وكلّه فروق رسمٍ لا فروق تلاوة — قِيس أثرها في REPORT §٥هـ):
  ٱ ٰ  الألف الخنجرية تُسقط بدل أن تُنطق ألفاً  (ذَٰلِك ⇄ ذلك)
  ے    اليه البري ياءً                        (فِے ⇄ في)
  ال   ألف الوصل تُسقط لورش/قالون (النقل)      (اَ۬لَايْكَة ⇄ ليكة)
  همو  صلة ميم الجمع تُختصر                     (هُمُو ⇄ هم)

    python tools/tasmi_bench/refine_variant.py --url … --surah 19 \
        --riwaya warsh --mode rasm --json out.json
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment_v2"))

import refine  # noqa: E402  (ملف rafiq-words — يُستورد ولا يُعدَّل)
from align import nw_align as _nw_align  # noqa: E402


def canon(w, naql=True):
    """صورةٌ قانونية تجعل رسمَي الرواية والإملاء يلتقيان.

    التوحيد يُطبَّق على **الطرفين** (المرجع والمسموع) فلا يُحابي أحدهما،
    ولا يمسّ ألفاً مرسومة (قال/قل) فتبقى أخطاء التلاوة مكشوفة.
    """
    w = w.replace("ٰ", "").replace("ے", "ي")
    if naql:
        if w.startswith("ال") and len(w) > 3:
            w = w[1:]
        w = re.sub(r"(هم|كم)وا?$", r"\1", w)
    return w


def patched(naql=True):
    def wrapper(hyp, ref):
        return _nw_align([canon(x, naql) for x in hyp], [canon(x, naql) for x in ref])
    return wrapper


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--surah", type=int, required=True)
    ap.add_argument("--riwaya", default="warsh")
    # `sabotage` وضعُ تحققٍ من الأداة نفسها: يُبطل المطابقة عمداً، فإن لم
    # تتغيّر النتيجة فالحقن لم يصل أصلاً وكل مقارنةٍ قبله بلا معنى.
    ap.add_argument("--mode", choices=["base", "rasm", "sabotage"], default="base")
    # عتبة VAD نسبية: التسجيل ذو أرضية الضجيج العالية (‏a_majed: أرضيته 20% من
    # مستوى الكلام مقابل 1.7% عند الحصري) لا تنزل طاقته تحت العتبة الثابتة 0.04
    # أبداً ⇒ لا يرى المحرك صمتاً فيقطع اعتباطاً عند السقف. القيمة هنا للتجربة.
    ap.add_argument("--vad-rel", type=float, default=None)
    ap.add_argument("--vad-min", type=int, default=None)
    # نداء «الصمت الدقيق» في الصقل يجب أن يبقى ثابتاً: التكيّف قِيس للتقطيع
    # وحده، وتسرّبه إلى الصقل يجعله يلتقط طاقةً منخفضة داخل الكلام «صمتاً».
    ap.add_argument("--fine-fixed", action="store_true",
                    help="ثبّت عتبة الصمت الدقيق في الصقل (adaptive=False)")
    ap.add_argument("--json", required=True)
    args = ap.parse_args()
    os.environ["ALIGN_REFINE"] = "1"

    captured = {}
    orig = refine.refine_surah

    def spy(d, log=print):
        st = orig(d, log=log)
        captured.update(st or {})
        return st
    refine.refine_surah = spy
    if args.fine_fixed:
        _rs = refine.silences

        def _fixed(path, min_silence_ms=180, rel_threshold=0.04, **kw):
            return _rs(path, min_silence_ms=min_silence_ms,
                       rel_threshold=rel_threshold, adaptive=False)
        refine.silences = _fixed
    if args.mode == "rasm":
        refine.nw_align = patched(args.riwaya != "hafs")
    elif args.mode == "sabotage":
        refine.nw_align = lambda hyp, ref: []

    import urllib.request

    from common import WORK  # noqa: E402
    import pipeline  # noqa: E402
    if args.vad_rel or args.vad_min:
        _orig_sil = pipeline.silences

        def _sil(path, min_silence_ms=180, rel_threshold=0.04):
            return _orig_sil(path,
                             min_silence_ms=args.vad_min or min_silence_ms,
                             rel_threshold=args.vad_rel or rel_threshold)
        pipeline.silences = _sil
    os.makedirs(WORK, exist_ok=True)
    # ⚠️ الاسم من **بصمة الرابط** لا من اسم الملف: كل القراء يسمّون سورتهم
    # `036.mp3`، فالتسمية بالاسم وحده جعلت تجربة حفص تقرأ صوت ورش المخزّن
    # (وقعت فعلاً: أعطت الأرقام نفسها حرفاً بحرف فانكشفت).
    import hashlib
    tag = hashlib.sha1(args.url.encode()).hexdigest()[:8]
    audio = os.path.join(WORK, f"var_s{args.surah:03d}_{tag}_{os.path.basename(args.url)}")
    if not os.path.exists(audio):
        urllib.request.urlretrieve(args.url, audio)
    res = pipeline.run_surah(audio, args.surah, args.riwaya)
    out = {"mode": args.mode, "surah": args.surah, "riwaya": args.riwaya,
           "refineStats": captured, "bands": res.get("bands"),
           "issues": len(res.get("issues", [])),
           "starts": {e["ayahId"]: e["startMs"] for e in res["entries"]}
           if res.get("entries") and "ayahId" in res["entries"][0]
           else {str(i): e.get("startMs") for i, e in enumerate(res["entries"])}}
    json.dump(out, open(args.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"mode": args.mode, "surah": args.surah,
                      "refine": captured, "bands": res.get("bands")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
