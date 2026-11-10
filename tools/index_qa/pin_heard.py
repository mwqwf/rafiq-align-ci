#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تثبيتُ بدء آياتٍ على **أداءٍ مسموعٍ مقيس** في تسجيلٍ فيه تكرار — أداءٌ واحدٌ متّصلٌ لكلّ آية (fixV · 2026-10-05).

    python tools/index_qa/pin_heard.py --key timings/hafs/asim.jz --sha 0da4de06 --surah 77 \\
        --run 37105755745 --pin 21:95500,22:100600,23:105300,24:114200 --reason "…" --yes

⭐ **سببُه:** تسجيلاتٌ يعيد فيها القارئُ آيةً أو مقطعاً (‏عاصم 77:21–23 تُقرأ مرّتين؛ الجليل 27:64–93
مرّتين؛ المروش 22:5 بتكرارٍ داخلها). المحاذاةُ القسريّة تفرض النصَّ مرّةً واحدةً على صوتٍ فيه مرّتان،
فتردّها حرّاسُ الثقة والمدّة (‏بحقّ)، ويبقى المنشورُ يبتلع الأداءَ الأوّل في مدخلٍ ويُصفّر جارَه (‏77:22 = 200م.ث).
والصوابُ — كما قرّر المنسّق — **أداءٌ واحدٌ متّصلٌ لكلّ آية لا اختلاق**: يبدأ المدخلُ حيث يُسمع أداءُ
الآية فعلاً، وما تكرّر قبله يبقى بلا مدخل (‏فجوةٌ بين مدخلين، لا آيةٌ على صوت غيرها).

**ما يفعله بالضبط:**
1. يقرأ خريطةَ السماع (‏`ctc_heard_map --probe`) من مخرَج التشغيلة `--run` نفسِها (‏لا من نصٍّ يكتبه المُطلِق)،
   ويشترط أن تكون لصوت السورة **نفسِه** في الفهرس: الرابطُ ذاتُه، والبصمةُ = `audioSha256` للسورة.
2. كلُّ بدءٍ في `--pin` يجب أن يقع (‏±150م.ث) على **بدءٍ مقيس** لتلك الآية: مرساتُها العامّة بجودة ≥0.5،
   أو أداءٌ لها بتشابه ≥0.7 — وإلا رُدّ. فالأداةُ **تختار** بين أداءاتٍ مسموعة ولا تُنشئ زمناً.
3. نهايةُ الآية المثبَّتة = بدءُ تاليتها؛ ونهايةُ الآية التي قبل أوّل تثبيتٍ تُقصّ إلى البدء الجديد إن تجاوزته،
   أو إلى قيمة `--trim a:ms` إن أُعطيت، وشرطُها أن تكون **حدّاً مقيساً** في الخريطة (‏بدءَ أداءٍ أو نهايتَه
   للآية نفسِها أو لتاليتها) ودون البدء المثبَّت.
4. ⛔ حُرّاسٌ قبل الرفع: البدءُ لا يتغيّر إلا للمثبَّت · الحدودُ صاعدةٌ بلا تداخل · وحكمُ `heard_gate`
   على السورة بالخريطة نفسِها سليم (‏وإلا لا معنى لرفعه) — ثمّ البوّابةُ الكاملة على المرشّح.
6. ⭐ **مسارُ شاهد Whisper الإضافيّ (`--witness-run`، 2026-11-07):** آيةٌ مرساتُها في الخريطة دون شرط الجودة
   (‏3siri س56: 68 و69 بجودة 0.25 و0.469 ووسيطُ المراسي 0.429) تُقبل **فقط** بشاهدٍ ثانٍ مستقلٍّ
   (‏Whisper float32 على نافذة الآية، من مخرَج `whisper_witness.yml`) باجتماع: تطابقُ أوّلِ كلماتِ الآية
   المرجعيّة وآخرِها كلمةً بكلمة بثقةٍ لكلّ كلمة · اتّفاقُ الشاهدين على الحدّ ≤300م.ث (‏بدءُ Whisper ومرساةُ
   CTC أو أحدُ أداءاتها أيّاً كانت جودتها) · مدّةٌ مثبَّتة 0.5–2× المتوقَّع (‏وسيطُ النظراء) · جارةٌ لا تنكمش
   دون 0.5×. ⛔ إضافيٌّ لا بديل: مسارُ CTC وعتباتُه كما هما حرفاً. والتفريغُ مرشّحٌ للتوقيت وحده:
   لا يُكتب منه نصٌّ في الفهرس، والنصُّ المرجعيُّ من `text_<الرواية>.jz` في المستودع.
5. `engineBySurah[س] = heard-pin-1` ⇒ تطلب الترقيةُ **إحصاءً صوتيّاً شاملاً** (‏Whisper، شاهدٌ مستقلّ عن
   خريطة CTC) لكلّ آيةٍ في السورة، فوق الملوح الأربعة والمطالع و`heard_gate` (‏بخريطةٍ تُقاس من جديد).
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import re
import math
import subprocess
import sys
import time
import zipfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                 # noqa: BLE001
        pass

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import heard_gate                                                    # noqa: E402
import index_fields                                                  # noqa: E402

REPO = "mwqwf/rafiq-align-ci"
ENGINE = "heard-pin-1"
SNAP_MS = 150
MIN_ANCHOR_Q = heard_gate.MIN_Q
MIN_OCC_SIM = heard_gate.REPEAT_SIM


def _key(aid):
    s, a = str(aid).split(":")
    return int(s), int(a)


# ⭐ (‏طلب توريث drop_ayahs · 2026-11-10) نُقلتا حرفاً إلى الوحدة المشتركة `declarations.py` (‏مع drop_surah وdrop_ayahs).
from declarations import declared_absent, inherit_declaration            # noqa: E402,F401


PARTIAL_MARGIN_MS = 1000   # (‏#105) لا يُستعمل من خريطةٍ جزئيّةٍ إلا ما يبدأ بعد بدء نافذتها بهذا القدر على الأقلّ


def usable_map(hmap):
    """(خريطةٌ صالحةٌ للتثبيت، حدُّها الأدنى أو None). الخريطةُ الكاملةُ كما هي حرفاً. والجزئيّة (‏`windowStartMs`)
    تُبقي من كلّ آيةٍ مِرساتَها وأداءاتِها التي تبدأ عند (‏البدء + PARTIAL_MARGIN_MS) أو بعده وحدها، ويُحذف الحقلُ من
    النسخة بعد التصفية (‏فما بقي مقيسٌ داخل النافذة)."""
    ws = hmap.get(heard_gate.PARTIAL_KEY) if isinstance(hmap, dict) else None
    if not ws:
        return hmap, None
    lo = int(ws) + PARTIAL_MARGIN_MS
    out = {k: v for k, v in hmap.items() if k != heard_gate.PARTIAL_KEY}
    hm = {}
    for a, rec in (hmap.get("heardMap") or {}).items():
        r = dict(rec)
        if r.get("anchorMs") and int(r["anchorMs"][0]) < lo:
            r.update(anchorMs=None, anchorQuality=None, windowAnchorMs=None, anchorStartEvidence=None)
        r["occurrences"] = [o for o in (r.get("occurrences") or []) if int(o[0]) >= lo]
        if r.get("heardMs") and int(r["heardMs"][0]) < lo:
            r["heardMs"] = None
        hm[a] = r
    out["heardMap"] = hm
    return out, lo


def parse_pairs(txt):
    out = {}
    for part in (txt or "").replace("،", ",").split(","):
        if part.strip():
            a, ms = part.split(":")
            out[int(a)] = int(ms)
    return out


def measured_starts(hmap, ayah):
    """البدءاتُ المقيسة للآية: [(بدء، نهاية، مصدر)]."""
    rec = (hmap.get("heardMap") or {}).get(str(ayah)) or {}
    out = []
    am, q = rec.get("anchorMs"), rec.get("anchorQuality")
    if am and q is not None and float(q) >= MIN_ANCHOR_Q:
        out.append((int(am[0]), int(am[1]), f"مرساة {q}"))
    for o in rec.get("occurrences") or []:
        if float(o[2]) >= MIN_OCC_SIM:
            out.append((int(o[0]), int(o[1]), f"أداء {o[2]}"))
    return out


def measured_bounds(hmap, ayahs):
    """كلُّ حدٍّ مقيسٍ (بدءٌ أو نهاية) لآياتٍ مسمّاة — من المراسي والأداءات بلا شرط جودة."""
    out = set()
    for a in ayahs:
        rec = (hmap.get("heardMap") or {}).get(str(a)) or {}
        if rec.get("anchorMs"):
            out |= {int(x) for x in rec["anchorMs"][:2]}
        for o in rec.get("occurrences") or []:
            out |= {int(o[0]), int(o[1])}
    return out


# ───────────── شاهد Whisper الإضافيّ (‏2026-11-07) ─────────────
W_K = 3                  # عددُ كلماتِ الطرف (‏أوّلُ الآية وآخرُها) المطلوبُ تطابقُها كلمةً بكلمة
# ⭐ عتبتا الثقة **اختياريّتان بالحذر لا بالقياس** (‏لا يوجد في المستودع تفريغُ float32 مقيسٌ لمعايرتهما):
#    كلمةٌ بين 0.3 و0.5 تُرى عند Whisper في تلاوةٍ سليمةٍ نادراً، وتكثُر في الكلمة المُهلوَسة أو المبتورة،
#    فالأدنى 0.5 لكلّ كلمةٍ طرفيّة. والمتوسّطُ 0.7 على الكلمات الستّ يمنع أن تنجو آيةٌ بكلمةٍ جيّدةٍ
#    وخمسٍ على الحدّ. والتشدّدُ هنا يردّ ولا يقبل خطأً — ويُرخى بعد قياسِ أوّل تشغيلتين لا قبله.
W_MIN_WORD_P = 0.5
W_MEAN_WORD_P = 0.7
W_AGREE_MS = 300         # أقصى فرقٍ بين بدء Whisper ومرساةِ/أداءِ CTC للآية نفسِها
W_DUR_LO, W_DUR_HI = 0.5, 2.0     # مدّةُ الآية المثبَّتة نسبةً إلى المتوقَّع (‏وسيطِ النظراء بعد معايرة الوتيرة)
W_NEIGHBOUR_MIN = 0.5    # الجارةُ السابقة لا تنكمش دون هذه النسبة من مدّتها في الأصل
W_LEN_LO, W_LEN_HI = 0.7, 1.3     # عددُ كلمات Whisper بين الطرفين نسبةً إلى كلمات الآية المرجعيّة
W_MODELS = ("small", "medium")
# ⭐ المسارُ المشابه (‏قرار خيط 2.0 · 2026-11-07، لدورة saad وحدها، خلف `--witness-fuzzy` المطفأ افتراضاً):
#    Whisper يُخطئ حرفاً في كلمةٍ طرفيّة («يعقرون» لـ«يعقلون») فيردّ التطابقُ التامّ آيةً سليمة. فيُقبل بدلَه تشابهُ
#    حروف الكلمات الطرفيّة بعد التطبيع ≥ W_FUZZ_SIM (‏أوّلُها وآخرُها معاً)، بقيدٍ معوِّض: عددُ كلمات Whisper من
#    كلمة البدء إلى كلمة الختام ضمن ±20٪ من كلمات الآية (‏أضيقُ من ±30٪ في التامّ) فلا تنجو آيةٌ مدموجةٌ أو مبتورة.
#    والثقةُ والاتّفاقُ ≤300م.ث والمدّةُ والجارةُ كما هي حرفاً، ومسارُ CTC لا يُمسّ.
W_FUZZ_SIM = 0.8
W_FUZZ_LEN_LO, W_FUZZ_LEN_HI = 0.8, 1.2
_REPO_ROOT = HERE.parent.parent


def all_starts(hmap, ayah):
    """كلُّ بدءٍ مسموعٍ للآية **أيّاً كانت جودتُه**: مرساتُها وأداءاتُها — قاعدةُ اتّفاق الشاهدين لا قاعدةُ التثبيت العاديّ."""
    rec = (hmap.get("heardMap") or {}).get(str(ayah)) or {}
    out = []
    if rec.get("anchorMs"):
        out.append(int(rec["anchorMs"][0]))
    out += [int(o[0]) for o in rec.get("occurrences") or []]
    return out


def ref_words_for(riwaya, surah, ayah):
    """كلماتُ الآية المرجعيّة مطبَّعةً من نصّ المصحف الموثَّق في المستودع (‏`text_<الرواية>.jz`) — لا من التفريغ."""
    sys.path.insert(0, str(_REPO_ROOT / "tools" / "alignment"))
    from common import load_index, load_text, norm, surah_slice          # noqa: PLC0415
    start, _end, info = surah_slice(load_index(), surah)
    if not 1 <= ayah <= int(info["ayahs"]):
        raise SystemExit(f"⛔ {surah}:{ayah} خارج السورة")
    return norm(load_text(riwaya)[start + ayah - 1]).split()


def _norm_words(words):
    """يحوّل كلماتِ Whisper إلى رموزٍ مطبَّعة [(رمز، بدء، ثقة)]؛ الكلمةُ التي تتشظّى ترثها ثقتُها وبدؤها."""
    sys.path.insert(0, str(_REPO_ROOT / "tools" / "alignment"))
    from common import norm                                              # noqa: PLC0415
    out = []
    for w in words or []:
        for t in norm(str(w.get("w", ""))).split():
            out.append((t, int(w["s"]), float(w["p"])))
    return out


def check_witness(wit, surah, hmap, want_sha):
    """يتحقّق من أنّ الشاهدَ لصوت السورة نفسِه ومن نموذجٍ مسموح — وإلا SystemExit."""
    if not isinstance(wit, dict) or int(wit.get("surah") or 0) != surah:
        raise SystemExit(f"⛔ شاهدُ Whisper لسورة {wit.get('surah') if isinstance(wit, dict) else '؟'} لا {surah}")
    if not want_sha:
        raise SystemExit("⛔ لا audioSha256 للسورة في الفهرس — لا يُقبل شاهدٌ بلا بصمةٍ يُقابَل بها")
    for nm, v in (("الخريطة", hmap.get("sha256")), ("الفهرس", want_sha)):
        if wit.get("sha256") != v:
            raise SystemExit(f"⛔ بصمةُ صوت الشاهد {str(wit.get('sha256'))[:8]} غيرُ بصمة {nm} {str(v)[:8]}")
    if wit.get("fileRef") != hmap.get("fileRef"):
        raise SystemExit(f"⛔ الشاهدُ سُمع من {wit.get('fileRef')} والخريطةُ من {hmap.get('fileRef')}")
    if wit.get("model") not in W_MODELS or wit.get("computeType") != "float32":
        raise SystemExit(f"⛔ الشاهدُ يلزمه {W_MODELS} بـfloat32 (‏وجد {wit.get('model')}/{wit.get('computeType')})")


def _sim(a, b):
    """تشابهُ حروف سلسلتين مطبَّعتين (‏difflib) بين 0 و1."""
    import difflib                                                       # noqa: PLC0415
    return difflib.SequenceMatcher(None, " ".join(a), " ".join(b)).ratio()


def whisper_check(wit, hmap, surah, ayah, ref, fuzzy=False):
    """كـ`_whisper_check` بالتطابق التامّ؛ فإن ردّ و`fuzzy` فالمسارُ المشابه (‏W_FUZZ_*) — ويُعلَّم تفصيلُه بـ«~»."""
    c, info = _whisper_check(wit, hmap, surah, ayah, ref, fuzzy=False)
    if c is not None or not fuzzy:
        return c, info
    c2, info2 = _whisper_check(wit, hmap, surah, ayah, ref, fuzzy=True)
    if c2 is None:
        return None, f"{info} · والمشابه: {info2}"
    return c2, "~" + info2


def _whisper_check(wit, hmap, surah, ayah, ref, fuzzy=False):
    """يُرجع (بدءُ CTC المعتمَد، تفصيل) إن اجتاز الشاهدُ **كلَّ** شروط الآية، وإلا يُرجع (None، سببَ الردّ).

    الشروط: تطابقُ أوّل W_K كلمةً بكلمة وآخرِ W_K (بعد التطبيع) · ثقةٌ لكلّ كلمةٍ طرفيّة ومتوسّطُها ·
    عددُ الكلمات بين الطرفين قريبٌ من المرجع · بدءُ Whisper يوافق CTC ضمن W_AGREE_MS.
    (‏المدّةُ والجارةُ تُفحصان في `pin` بعد حساب الحدود النهائيّة.)"""
    rec = (wit.get("ayahs") or {}).get(str(ayah))
    if not rec:
        return None, "لا تفريغَ لهذه الآية في الشاهد"
    if not ref:
        return None, "لا نصَّ مرجعيَّ للآية"
    toks = _norm_words(rec.get("words"))
    k, n = min(W_K, len(ref)), len(ref)
    head, tail = ref[:k], ref[-k:]
    ctc = all_starts(hmap, ayah)
    if not ctc:
        return None, "لا مرساةَ CTC ولا أداءَ للآية يُقارَن به"
    why = "أوّلُ كلماتِ الآية لا يطابق تفريغَ النافذة"
    best = None
    def same(got, want):
        return _sim(got, want) >= W_FUZZ_SIM if fuzzy else got == want
    lo, hi = ((max(k, math.ceil(W_FUZZ_LEN_LO * n)), math.floor(W_FUZZ_LEN_HI * n)) if fuzzy
              else (max(k, int(W_LEN_LO * n)), int(W_LEN_HI * n) + 1))
    for i in range(len(toks) - k + 1):
        if not same([t[0] for t in toks[i:i + k]], head):
            continue
        ends = [j for j in range(i + k - 1, len(toks)) if same([t[0] for t in toks[j - k + 1:j + 1]], tail)]
        ends = [j for j in ends if lo <= j - i + 1 <= hi]
        if not ends:
            why = "آخرُ كلماتِ الآية لا يطابق التفريغ أو عددُ كلماته خارج المدى"
            continue
        j = min(ends, key=lambda e: abs((e - i + 1) - n))
        edge = toks[i:i + k] + toks[j - k + 1:j + 1]
        low = min(t[2] for t in edge)
        mean = sum(t[2] for t in edge) / len(edge)
        if low < W_MIN_WORD_P or mean < W_MEAN_WORD_P:
            why = f"ثقةُ الكلمات الطرفيّة دون العتبة (أدناها {low:.2f}، متوسّطُها {mean:.2f})"
            continue
        ws = toks[i][1]
        c = min(ctc, key=lambda x: abs(x - ws))
        if abs(c - ws) > W_AGREE_MS:
            why = f"الشاهدان يتعارضان: Whisper {ws} وأقربُ بدءٍ لـCTC {c} (>{W_AGREE_MS}م.ث)"
            continue
        if best is None or abs(c - ws) < best[2]:
            best = (c, ws, abs(c - ws), low, mean)
    if best is None:
        return None, why
    return best[0], f"whisper {best[1]} · CTC {best[0]} · أدنى ثقة {best[3]:.2f} · متوسّطها {best[4]:.2f}"


# ───────────── حدُّ القصّ من شاهدَي Whisper (‏2026-11-10 · الكردي 55:29/30 · مسودّة لا تُدمج) ─────────────
# ⭐ `--trim` كان لا يقبل إلا حدّاً في `measured_bounds`، وحالةُ 55:29/30 لا حدَّ مقيساً فيها بين نهاية «شأنٍ»
#    وبدء الأداء الأوّل لـ«فبأي»: أداءُ CTC السماعيّ لـ29 ينتهي 183585 (‏قبل «شأنٍ» نفسِها) ومرساتُه القسريّة
#    تنتهي 187988 (‏داخل «فبأي»). فيُقبل حدٌّ غيرُ مقيسٍ بـCTC **بشروطٍ كلّها مجتمعةً ولا يُرخى منها شيء**:
#    1) شاهدان على الأقلّ من تشغيلتَين متمايزتَين، وكلُّ شاهدٍ يُمرَّر يجب أن يجتاز (‏لا انتقاءَ لشاهدٍ موافق)؛
#    2) بصمةُ كلّ شاهدٍ = بصمةُ الفهرس = بصمةُ الخريطة، ومن float32 بنموذجٍ مسموح (‏`check_witness`)؛
#    3) في التفريغ: آخرُ W_K كلماتٍ من الآية السابقة **متّصلةً** بأوّل W_K من التالية، كلمةً بكلمةٍ بعد التطبيع —
#       فآخرُ كلمةٍ للسابقة مسموعةٌ قبل الحدّ (‏لا تُقطع)، والحدُّ بدءُ أوّل كلمةٍ للتالية في **أوّل** أداءٍ لها؛
#    4) ثقةُ كلّ كلمةٍ من الستّ ≥ W_MIN_WORD_P ومتوسّطُها ≥ W_MEAN_WORD_P، ولا كلمةَ منها ملصوقةٌ بطرف النافذة
#       (‏Whisper يُلصق أوّلَ كلمةٍ ببدء النافذة فلا يُعدّ بدؤها قياساً)؛
#    5) الشاهدان يتّفقان على الحدّ ضمن W_AGREE_MS، والقيمةُ المطلوبة ضمن SNAP_MS من كلٍّ منهما،
#       ويُعتمد **أبكرُهما** (‏فلا يدخل صوتُ التالية في السابقة)؛
#    6) الحدُّ بعد آخر نهايةِ أداءٍ سماعيٍّ مقيسٍ للسابقة (‏occurrences) وقبل التثبيت التالي.
W_TRIM_MIN_WITNESSES = 2


def _junction(wit, ref_prev, ref_next):
    """يبحث في نوافذ الشاهد عن أوّل موضعٍ تتّصل فيه خاتمةُ السابقة بمطلع التالية؛ يُرجع (الحدّ، تفصيل) أو (None، سبب)."""
    k = min(W_K, len(ref_prev), len(ref_next))
    tail, head = ref_prev[-k:], ref_next[:k]
    why = "لا موضعَ في التفريغ تتّصل فيه آخرُ كلمات السابقة بأوّل كلمات التالية"
    found = []
    for ay, rec in sorted((wit.get("ayahs") or {}).items(), key=lambda kv: int(kv[0])):
        win = rec.get("windowMs") or [None, None]
        raw = []
        for w in rec.get("words") or []:
            for t in _norm_words([w]):
                raw.append((t[0], t[1], int(w.get("e", t[1])), t[2]))
        for i in range(k, len(raw) - k + 1):
            if [x[0] for x in raw[i - k:i]] != tail or [x[0] for x in raw[i:i + k]] != head:
                continue
            edge = raw[i - k:i + k]
            if win[0] is not None and any(x[1] <= int(win[0]) for x in edge):
                why = f"كلمةٌ طرفيّةٌ ملصوقةٌ ببدء النافذة {win[0]} (‏بدؤها ليس قياساً)"
                continue
            if win[1] is not None and any(x[2] >= int(win[1]) for x in edge):
                why = f"كلمةٌ طرفيّةٌ ملصوقةٌ بنهاية النافذة {win[1]}"
                continue
            low = min(x[3] for x in edge)
            mean = sum(x[3] for x in edge) / len(edge)
            if low < W_MIN_WORD_P or mean < W_MEAN_WORD_P:
                why = f"ثقةُ الكلمات عند الحدّ دون العتبة (أدناها {low:.2f}، متوسّطُها {mean:.2f})"
                continue
            found.append((raw[i][1], raw[i - 1][2], low, mean, ay))
            break
    if not found:
        return None, why
    b = min(found)
    return b[0], {"boundaryMs": b[0], "prevLastWordEndMs": b[1], "minP": round(b[2], 4),
                  "meanP": round(b[3], 4), "window": b[4]}


def trim_from_witnesses(wits, hmap, surah, ayah, want_ms, ref_prev, ref_next, next_start, want_sha, prev_start=None):
    """حدُّ قصّ `ayah` من شاهدَي Whisper أو SystemExit بالسبب. `wits` = {تشغيلة: شاهد}."""
    if len(wits) < W_TRIM_MIN_WITNESSES:
        raise SystemExit(f"⛔ حدُّ القصّ من Whisper يلزمه {W_TRIM_MIN_WITNESSES} شاهدان من تشغيلتَين (‏وجد {len(wits)})")
    got = {}
    for run, w in sorted(wits.items()):
        check_witness(w, surah, hmap, want_sha)
        b, info = _junction(w, ref_prev, ref_next)
        if b is None:
            raise SystemExit(f"⛔ قصُّ {surah}:{ayah}: الشاهد {run} لا يُثبت الحدّ — {info}")
        got[run] = info
    bs = sorted(v["boundaryMs"] for v in got.values())
    if bs[-1] - bs[0] > W_AGREE_MS:
        raise SystemExit(f"⛔ قصُّ {surah}:{ayah}: الشاهدان يختلفان في الحدّ {bs} (>{W_AGREE_MS}م.ث)")
    far = [b for b in bs if abs(b - want_ms) > SNAP_MS]
    if far:
        raise SystemExit(f"⛔ قصُّ {surah}:{ayah} إلى {want_ms} بعيدٌ عن حدّ الشاهدَين {bs} (>{SNAP_MS}م.ث)")
    b = bs[0]
    rec = (hmap.get("heardMap") or {}).get(str(ayah)) or {}
    # أداءُ السابقة المقصود هو الذي يبدأ عند بدء مدخلها أو بعده وقبل الحدّ (‏لا تكرارُها بعد الحدّ)
    lo = -1 if prev_start is None else int(prev_start) - SNAP_MS
    occ_end = max([int(o[1]) for o in rec.get("occurrences") or [] if lo <= int(o[0]) < b], default=None)
    if occ_end is None:
        raise SystemExit(f"⛔ قصُّ {surah}:{ayah}: لا أداءَ سماعيّاً مقيساً للسابقة يُحدّ به")
    if not occ_end <= b < int(next_start):
        raise SystemExit(f"⛔ قصُّ {surah}:{ayah} إلى {b} خارج ({occ_end}، {next_start}): "
                         "بين آخر نهايةِ أداءٍ مقيسٍ للسابقة والتثبيت التالي")
    return b, {"ms": b, "witnesses": got, "prevHeardEndMs": occ_end, "nextPinMs": int(next_start)}


# ───────────── مطلعُ الحروف المقطّعة: «حدٌّ بلا قياسٍ للحروف» (‏قرار القائد 2026-11-10 · خيار أ) ─────────────
# ⭐ Whisper لا يكتب أسماءَ الحروف (‏«حميم» · «قاسم» · «موسيقى» في شواهد الكردي وa_ahmed وmhsny الحقيقيّة)، والشاهدان
#    إن سمعاها اختلفا 600–1000م.ث، فبدءُ الحروف **لا يُقاس**. والمقيسُ بدءُ الآية الثانية (‏CTC + Whisper). فالقاعدة:
#    ١) السورةُ من قائمةٍ **مشتقّةٍ من نصّ المصحف الموثَّق للرواية** (‏`letters_opener_surahs`) لا مكتوبةٍ باليد:
#       آيتُها الأولى كلمةٌ واحدةٌ من حروف الفواتح الأربعة عشر عليها مدٌّ لازمٌ (‏ٓ) على حرفٍ غير الألف، أو حرفان وحدهما
#       بلا ألفٍ ولا سكون (‏«طه»: لا مدَّ لازمَ فيها، و«ما»/«لم» ليستا منها)؛ و**تُستثنى** كلُّ سورةٍ آيتُها الثانية حروفٌ أيضاً (‏42:2 «عسق»: تثبيتُ الثانية فيها غيرُ مقيس)؛
#    ٢) تُثبَّت الآيةُ الثانية بالمسار المقيس (‏CTC) **ويشهد لها شاهدان** محمَّلان من مصدرهما (‏`load_witness`):
#       أوّلُ W_K كلماتٍ منها كلمةً بكلمة، بالثقة (‏W_MIN_WORD_P/W_MEAN_WORD_P)، بلا التصاقٍ بطرف النافذة، وبدؤها ضمن
#       W_AGREE_MS من التثبيت؛
#    ٣) يُمَدّ بدءُ الآية الأولى **إلى الوراء وحده** إلى أبكر: بدئها المنشور، وأبكرِ كلمةٍ مسموعةٍ قبل مطلع الثانية في
#       الشاهدين (‏بعد البسملة إن سُمعت، وبلا كلمةٍ ملصوقةٍ ببدء النافذة) — فلا يُقصّ من الحروف شيء؛ ونهايتُها بدءُ الثانية؛
#    ٤) لا يُمَدّ قبل بدء الملفّ (‏0)، ولا أبعدَ من OPENER_MAX_EXTEND_MS قبل بدئها المنشور، وإلا رُدّت السورة؛
#    ٥) الدليلُ في `transform.openerLetters` وسطرٌ في `pins`؛ و`openers.yml` و`lateConfirmed` يُشغَّلان على المرشّح كما هو.
OPENER_VERSION = "opener-letters-1"
OPENER_MAX_EXTEND_MS = 3000
OPENER_MIN_WITNESSES = 2
_MUQ_LETTERS = frozenset("المصركهيعطسحقن")
_MUQ_MADDA = re.compile("[لمصركهيعطسحقن][\u064b-\u0652\u0670\u06df-\u06ed\u065c]*\u0653")
_BASMALA = ("بسم", "الله", "الرحمن", "الرحيم")


def is_letters_ayah(raw):
    """آيةٌ هي حروفٌ مقطّعةٌ وحدها في نصّ المصحف (‏انظر الشرط ١)."""
    sys.path.insert(0, str(_REPO_ROOT / "tools" / "alignment"))
    from common import norm                                              # noqa: PLC0415
    w = norm(str(raw or "")).split()
    return (len(w) == 1 and set(w[0]) <= _MUQ_LETTERS
            and (bool(_MUQ_MADDA.search(str(raw)))
                 or (len(w[0]) == 2 and "ا" not in w[0] and "\u0652" not in str(raw))))


def letters_opener_surahs(riwaya):
    """السورُ التي آيتُها الأولى حروفٌ وحدها والثانيةُ ليست حروفاً — من `text_<الرواية>.jz` نفسِه."""
    sys.path.insert(0, str(_REPO_ROOT / "tools" / "alignment"))
    from common import load_index, load_text, surah_slice                # noqa: PLC0415
    text, index = load_text(riwaya or "hafs"), load_index()
    out = []
    for s in range(1, 115):
        start, _end, info = surah_slice(index, s)
        if int(info["ayahs"]) >= 2 and is_letters_ayah(text[start]) and not is_letters_ayah(text[start + 1]):
            out.append(s)
    return out


def _opener_witness(wit, head2, pin2):
    """(تفصيلٌ، None) أو (None، سبب): مطلعُ الثانية عند `pin2` وأبكرُ كلمةٍ قبله (‏بعد البسملة · بلا التصاق)."""
    k = len(head2)
    why = "لا يُسمع مطلعُ الآية الثانية كلمةً بكلمة"
    for ay, rec in sorted((wit.get("ayahs") or {}).items(), key=lambda kv: int(kv[0])):
        win = rec.get("windowMs") or [None, None]
        raw = []
        for w in rec.get("words") or []:
            # ⭐ المقارِنُ الإملائيُّ الضيّق نفسُه في #101 (‏ٰ ء ٱ ← ا): «الكتاب» (‏Whisper) = «ٱلْكِتَٰبِ» (‏المصحف)
            for t in heard_gate.disputed_norm_words(str(w.get("w", ""))):
                raw.append((t, int(w["s"]), int(w.get("e", w["s"])), float(w["p"])))
        for i in range(len(raw) - k + 1):
            if [x[0] for x in raw[i:i + k]] != head2:
                continue
            edge = raw[i:i + k]
            if win[0] is not None and any(x[1] <= int(win[0]) for x in edge):
                why = f"مطلعُ الثانية ملصوقٌ ببدء النافذة {win[0]}"
                continue
            if win[1] is not None and any(x[2] >= int(win[1]) for x in edge):
                why = f"مطلعُ الثانية ملصوقٌ بنهاية النافذة {win[1]}"
                continue
            low = min(x[3] for x in edge)
            mean = sum(x[3] for x in edge) / len(edge)
            if low < W_MIN_WORD_P or mean < W_MEAN_WORD_P:
                why = f"ثقةُ مطلع الثانية دون العتبة (أدناها {low:.2f}، متوسّطُها {mean:.2f})"
                continue
            if abs(raw[i][1] - int(pin2)) > W_AGREE_MS:
                why = f"مطلعُ الثانية عند Whisper {raw[i][1]} بعيدٌ عن التثبيت {pin2} (>{W_AGREE_MS}م.ث)"
                continue
            before = raw[:i]
            cut = max([j for j, x in enumerate(before) if x[0] in _BASMALA], default=-1)
            pre = [x for x in before[cut + 1:]
                   if re.search("[\u0621-\u064a]", x[0]) and (win[0] is None or x[1] > int(win[0]))]
            return {"window": ay, "ayah2HeadMs": raw[i][1], "minP": round(low, 4), "meanP": round(mean, 4),
                    "lettersWords": [[x[0], x[1], round(x[3], 4)] for x in pre],
                    "earliestMs": min((x[1] for x in pre), default=None)}, None
    return None, why


def opener_letters_start(wits, surah, riwaya, hmap, want_sha, published_start, pin2, ref2=None):
    """بدءُ الآية الأولى الجديد ودليلُه، أو SystemExit بالسبب (‏الشروط ١–٤ أعلاه)."""
    if surah not in letters_opener_surahs(riwaya):
        raise SystemExit(f"⛔ س{surah} ليست في قائمة المطالع المقطّعة المشتقّة من نصّ {riwaya} "
                         "(‏آيتُها الأولى ليست حروفاً وحدها، أو الثانيةُ حروفٌ أيضاً)")
    if len(wits or {}) < OPENER_MIN_WITNESSES:
        raise SystemExit(f"⛔ مطلعُ الحروف يلزمه {OPENER_MIN_WITNESSES} شاهدان من تشغيلتين (‏وجد {len(wits or {})})")
    ref2 = ref2 if ref2 is not None else heard_gate.disputed_ref_words(riwaya, surah, 2)
    head2 = list(ref2[:min(W_K, len(ref2))])
    got = {}
    for run, w in sorted(wits.items()):
        check_witness(w, surah, hmap, want_sha)
        d, why = _opener_witness(w, head2, pin2)
        if d is None:
            raise SystemExit(f"⛔ مطلعُ {surah}:1: الشاهد {run} — {why}")
        got[str(run)] = d
    cands = [int(published_start)] + [d["earliestMs"] for d in got.values() if d["earliestMs"] is not None]
    new = min(cands)
    if new < 0:
        raise SystemExit(f"⛔ مطلعُ {surah}:1 يُمَدّ إلى {new} قبل بدء الملفّ")
    if int(published_start) - new > OPENER_MAX_EXTEND_MS:
        raise SystemExit(f"⛔ مطلعُ {surah}:1 يُمَدّ {int(published_start) - new}م.ث قبل بدئه المنشور {published_start} "
                         f"(>{OPENER_MAX_EXTEND_MS}م.ث) — تُردّ السورة")
    if not new < int(pin2):
        raise SystemExit(f"⛔ مطلعُ {surah}:1 عند {new} ليس قبل تثبيت الثانية {pin2}")
    return new, {"version": OPENER_VERSION, "publishedStartMs": int(published_start), "startMs": new,
                 "ayah2PinMs": int(pin2), "maxExtendMs": OPENER_MAX_EXTEND_MS, "witnesses": got}


def expected_from_peers(own_durs, peer_med, skip=()):
    """المتوقَّعُ لكلّ آيةٍ = وسيطُ مدّتها عند النظراء × وتيرةُ هذا القارئ.

    الوتيرةُ = وسيطُ (مدّتِه ÷ وسيطِ النظراء) على آياتِ السورة التي ليست في `skip` (‏المثبَّتة وما التهمها)،
    فتُغني عن مقارنةِ قارئٍ بطيءٍ بنظيرٍ سريع."""
    ratios = sorted(own_durs[a] / peer_med[a] for a in own_durs
                    if a in peer_med and a not in skip and peer_med[a] > 0 and own_durs[a] > 0)
    if not ratios:
        return {}
    pace = ratios[len(ratios) // 2]
    return {a: m * pace for a, m in peer_med.items()}


def pin(idx, surah, hmap, pins, trims=None, last_end=None, witness=None, ref_words=None,
        expected=None, evidence=None, witness_fuzzy=False, trim_witnesses=None, trim_evidence=None,
        opener_witnesses=None, opener_evidence=None):
    """يُعيد (فهرساً جديداً، تقريراً) أو يرفع SystemExit بالسبب.

    `last_end`: نهايةٌ مقيسةٌ لآخر آيةٍ في السورة (‏الفخفاخ 33:73 · 2026-10-05: قُصّت عند مدّةٍ قدّرها ffprobe
    من ترويسة VBR بـ1792.6ث والفكُّ الكامل أطول، فسُمع منها 2.6ث). شرطُها: الآيةُ آخرُ السورة ومثبَّتة،
    والقيمةُ نهايةُ **الأداء نفسِه** الذي ثُبّت عليه بدؤها (‏±150م.ث) — والخريطةُ لا تُقيس إلا صوتاً مفكوكاً.

    `witness` (‏اختياريّ · 2026-11-07): شاهدُ Whisper الإضافيّ (‏مخرَجُ whisper_witness)؛ يُجرَّب **بعد** فشل مسار CTC وحدَه.
    `ref_words(surah, ayah)` ⇐ كلماتُ الآية المرجعيّة مطبَّعة؛ `expected` {آية: مدّةٌ متوقَّعةٌ م.ث}؛
    `evidence` قاموسٌ يُملأ بـ{آية: "ctc" | "ctc+whisper"}. بلا `witness` السلوكُ القديمُ حرفاً."""
    trims = trims or {}
    wpinned = {}
    # ⭐ (2026-11-10 · الكردي س55) الأصلُ الذي يحمل إعلانَ إسقاطٍ يُبنى عليه، والإعلانُ يُورَّث حرفاً (‏`inherit_declaration`)؛
    #    وكان الرفضُ هنا لأنّ التحويلَ الجديد كان يمحوه. ويُردّ تثبيتُ سورةٍ معلَنةِ الغياب أو إعلانٌ لا يتّسق.
    declared_absent(idx, surah)
    if not pins:
        raise SystemExit("⛔ لا تثبيت")
    hmap, part_lo = usable_map(hmap)
    if part_lo is not None:
        early = sorted(a for a, ms in (pins or {}).items() if int(ms) < part_lo)
        early += sorted(a for a, ms in (trims or {}).items() if int(ms) < part_lo)
        if early:
            raise SystemExit(f"⛔ خريطةٌ جزئيّة: لا تثبيتَ ولا قصَّ قبل {part_lo}م.ث (‏بدءُ النافذة + {PARTIAL_MARGIN_MS}) — "
                             f"الآيات {early}")
    if int(hmap.get("surah") or 0) != surah:
        raise SystemExit(f"⛔ الخريطةُ لسورة {hmap.get('surah')} لا {surah}")
    ents = list(idx.get("entries") or [])
    mine = {_key(e["ayahId"])[1]: e for e in ents if _key(e["ayahId"])[0] == surah}
    if not mine:
        raise SystemExit(f"⛔ لا مداخل للسورة {surah}")
    refs = {e.get("fileRef") for e in mine.values()}
    if len(refs) != 1 or hmap.get("fileRef") not in refs:
        raise SystemExit(f"⛔ الخريطةُ سُمعت من {hmap.get('fileRef')} والفهرسُ يشير إلى {sorted(refs)[:2]}")
    present = sorted({_key(e["ayahId"])[0] for e in ents})
    # ⛔ كان الفحصُ يُتخطّى صامتاً إن لم يساوِ طولُ القائمة عدد السور الحاضرة (114 موضعاً وسورةٌ محذوفة) أو جاءت نصّاً.
    try:
        want = index_fields.sha_by_surah(idx, present).get(surah)
    except index_fields.IndexFieldError as exc:
        raise SystemExit(f"⛔ audioSha256 في الفهرس لا تُقرأ ({exc}) — لا تثبيتَ بلا بصمةٍ صالحة")
    if want and want != hmap.get("sha256"):
        raise SystemExit(f"⛔ بصمةُ الصوت المسموع {str(hmap.get('sha256'))[:8]} غيرُ بصمة الفهرس {str(want)[:8]}")
    report = []
    for a, ms in sorted(pins.items()):
        if a not in mine:
            raise SystemExit(f"⛔ {surah}:{a} لا مدخلَ لها")
        hit = [m for m in measured_starts(hmap, a) if abs(m[0] - ms) <= SNAP_MS]
        if not hit and witness is not None:
            # مسارُ الشاهد الإضافيّ: لا يُجرَّب إلا بعد أن يفشل مسارُ CTC بعتباته كما هي.
            if ref_words is None:
                raise SystemExit("⛔ مسارُ Whisper يلزمه نصٌّ مرجعيّ")
            check_witness(witness, surah, hmap, want)
            c, info = whisper_check(witness, hmap, surah, a, ref_words(surah, a), fuzzy=witness_fuzzy)
            if c is None:
                raise SystemExit(f"⛔ {surah}:{a} بدءٌ {ms} لا يقع على أداءٍ مقيس ولم يُثبته شاهدُ Whisper: {info}")
            if abs(c - ms) > SNAP_MS:
                raise SystemExit(f"⛔ {surah}:{a} بدءٌ {ms} بعيدٌ عن البدء المعتمَد بالشاهدين {c} (>{SNAP_MS}م.ث)")
            hit = [(c, c, "")]
            wpinned[a] = info
            report.append(f"{surah}:{a} ⇐ {c} (CTC بلا شرط الجودة + شاهدُ Whisper: {info})")
            if evidence is not None:
                evidence[a] = "ctc+whisper~" if info.startswith("~") else "ctc+whisper"
        elif not hit:
            raise SystemExit(f"⛔ {surah}:{a} بدءٌ {ms} لا يقع على أداءٍ مقيس (المقيس: "
                             f"{[(m[0], m[2]) for m in measured_starts(hmap, a)]})")
        else:
            report.append(f"{surah}:{a} ⇐ {hit[0][0]} ({hit[0][2]})")
            if evidence is not None:
                evidence[a] = "ctc"
        pins[a] = hit[0][0]
    new = {a: dict(e) for a, e in mine.items()}
    for a in sorted(pins):
        new[a]["startMs"] = pins[a]
    order = sorted(new)
    if trims and not trim_witnesses:
        # ⛔ (‏قرار القائد 2026-11-10 · #99) كلُّ `--trim` يلزمه شاهدا Whisper بلا استثناء: الحدُّ المقيسُ بـCTC وحده
        #    قُبل في 55:29 مرّتين خطأً (‏183585 يقطع «شأنٍ» · 187988 يُدخل «فبأي»).
        raise SystemExit("⛔ --trim بلا شاهدَي Whisper (‏--trim-witness-runs) مردود — الحدُّ المقيسُ بـCTC وحده لا يكفي")
    for a in trims:
        if a not in new or (a + 1) not in new or ((a + 1) not in pins and a not in pins):
            raise SystemExit(f"⛔ --trim {a}: يُقصّ آخرُ آيةٍ قبل تثبيتٍ أو آيةٌ مثبَّتة وحدهما")
        bounds = measured_bounds(hmap, [a, a + 1])
        hit = [b for b in bounds if abs(trims[a] - b) <= SNAP_MS]
        if trim_witnesses:
            # ⭐ مسارُ شاهدَي Whisper لحدّ القصّ (‏انظر `trim_from_witnesses`) — إلزاميٌّ لكلّ قصٍّ ولو كان حدّاً مقيساً بـCTC.
            if ref_words is None or (a + 1) not in pins:
                raise SystemExit(f"⛔ قصُّ {surah}:{a} بشاهد Whisper يلزمه نصٌّ مرجعيّ وتثبيتٌ لـ{surah}:{a + 1}")
            b, ev = trim_from_witnesses(trim_witnesses, hmap, surah, a, trims[a], ref_words(surah, a),
                                        ref_words(surah, a + 1), pins[a + 1], want,
                                        prev_start=int(new[a]["startMs"]))
            if b <= int(new[a]["startMs"]):
                raise SystemExit(f"⛔ قصُّ {surah}:{a} إلى {b} قبل بدئها {new[a]['startMs']}")
            if trim_evidence is not None:
                trim_evidence[a] = ev
            trims[a] = b
            continue
        if not hit:
            raise SystemExit(f"⛔ قصُّ {surah}:{a} إلى {trims[a]} ليس حدّاً مقيساً")
        trims[a] = min(hit, key=lambda b: abs(trims[a] - b))
    for i, a in enumerate(order):
        nxt = order[i + 1] if i + 1 < len(order) else None
        if nxt is None or (a not in pins and nxt not in pins):
            continue
        if a in trims:
            new[a]["endMs"] = trims[a]
            how = "حدُّ شاهدَي Whisper" if trim_evidence and a in trim_evidence else "حدٌّ مقيس"
            report.append(f"{surah}:{a} نهايتُها ⇐ {trims[a]} ({how}؛ ما بعده تكرارٌ بلا مدخل)")
        elif mine[a].get("endMs") is not None and int(mine[a]["endMs"]) == int(mine[nxt]["startMs"]):
            new[a]["endMs"] = new[nxt]["startMs"]            # كان متّصلاً بتاليه فيبقى متّصلاً
        else:
            new[a]["endMs"] = min(int(mine[a]["endMs"] or 0) or new[nxt]["startMs"], new[nxt]["startMs"])
    if last_end is not None:
        last = order[-1]
        if last != heard_gate_n_ayahs(surah) or last not in pins:
            raise SystemExit(f"⛔ --last-end لآخر آيةٍ في السورة مثبَّتةً وحدها (‏آخرُ الحاضر {surah}:{last})")
        perf = [m for m in measured_starts(hmap, last) if m[0] == pins[last]]
        hit = [m[1] for m in perf if abs(m[1] - last_end) <= SNAP_MS]
        if not hit:
            raise SystemExit(f"⛔ --last-end {last_end} ليس نهايةَ الأداء المثبَّت لـ{surah}:{last} "
                             f"(‏{[(m[0], m[1]) for m in perf]})")
        new[last]["endMs"] = hit[0]
        report.append(f"{surah}:{last} نهايتُها ⇐ {hit[0]} (نهايةُ أدائها المقيس)")
    if opener_witnesses is not None:
        # ⭐ مطلعُ الحروف المقطّعة (‏`opener_letters_start`): الثانيةُ مثبَّتةٌ بالمسار المقيس، والأولى تُمَدّ إلى الوراء وحده.
        if 2 not in pins or 1 in pins or 1 not in new or order[0] != 1:
            raise SystemExit(f"⛔ مطلعُ الحروف: يلزمه تثبيتُ {surah}:2 وحدها ومدخلٌ لـ{surah}:1 غيرُ مثبَّت")
        st1, ev1 = opener_letters_start(opener_witnesses, surah, idx.get("riwaya") or "hafs", hmap, want,
                                        int(mine[1]["startMs"]), pins[2])
        new[1]["startMs"], new[1]["endMs"] = st1, pins[2]
        report.append(f"{surah}:1 بدؤها ⇐ {st1} (حدٌّ بلا قياسٍ للحروف {OPENER_VERSION}: المنشور {mine[1]['startMs']} · "
                      f"أبكرُ كلمةٍ قبل مطلع الثانية · نهايتُها تثبيتُ الثانية {pins[2]} · شاهدان {sorted(ev1['witnesses'])})")
        if opener_evidence is not None:
            opener_evidence.update(ev1)
    prev_end = -1
    for a in order:
        e = new[a]
        st, en = int(e["startMs"]), int(e["endMs"])
        if not (0 <= st < en) or st < prev_end:
            raise SystemExit(f"⛔ {surah}:{a}: حدودٌ غيرُ صاعدة ({st}→{en}، والسابقة تنتهي {prev_end})")
        prev_end = en
        if a not in pins and int(e["startMs"]) != int(mine[a]["startMs"]) and not (a == 1 and opener_witnesses is not None):
            raise SystemExit(f"⛔ {surah}:{a}: تغيّر بدءُ آيةٍ غيرِ مثبَّتة")
    for a in sorted(wpinned):
        # ⛔ مدّةُ الآية المثبَّتة بالشاهد 0.5–2× المتوقَّع، والجارةُ السابقة لا تنكمش دون 0.5× مدّتها الأصليّة.
        exp = (expected or {}).get(a)
        if not exp or exp <= 0:
            raise SystemExit(f"⛔ {surah}:{a} لا مدّةَ متوقَّعةَ (نظراء) تُقاس بها — لا يُقبل شاهدُ Whisper بلا مقياس")
        dur = int(new[a]["endMs"]) - int(new[a]["startMs"])
        if not (W_DUR_LO * exp <= dur <= W_DUR_HI * exp):
            raise SystemExit(f"⛔ {surah}:{a} مدّتُها المثبَّتة {dur}م.ث خارج {W_DUR_LO}–{W_DUR_HI}× المتوقَّع {int(exp)}")
        p = a - 1
        if p in new and p not in pins:
            was = int(mine[p]["endMs"]) - int(mine[p]["startMs"])
            now = int(new[p]["endMs"]) - int(new[p]["startMs"])
            if was > 0 and now < W_NEIGHBOUR_MIN * was:
                raise SystemExit(f"⛔ الجارةُ {surah}:{p} تنكمش من {was} إلى {now}م.ث (دون {W_NEIGHBOUR_MIN}×) بتثبيت {a}")
    rows = heard_gate.surah_rows({a: new[a]["startMs"] for a in order}, heard_gate.compact_map(hmap))
    why = heard_gate.surah_verdict(rows)
    if why:
        raise SystemExit(f"⛔ حكمُ السماع على السورة بعد التثبيت: {why}")
    out = dict(idx)
    out["entries"] = [new[_key(e["ayahId"])[1]] if _key(e["ayahId"])[0] == surah else e for e in ents]
    ebs = dict(idx.get("engineBySurah") or {})
    ebs[str(surah)] = ENGINE
    out["engineBySurah"] = ebs
    out["lowCount"] = sum(1 for e in out["entries"] if e.get("confBand") == "LOW")
    changed = [a for a in order if new[a] != mine[a]]
    return out, report, changed


def heard_gate_n_ayahs(surah):
    from drop_surah import SURAH_AYAHS
    return SURAH_AYAHS[surah - 1]


def load_map(run_id, surah):
    def gh(path, raw=False):
        r = subprocess.run(["gh", "api", path], capture_output=True)
        if r.returncode:
            raise SystemExit(f"⛔ gh api {path}: {r.stderr.decode('utf-8', 'replace')[:200]}")
        return r.stdout if raw else json.loads(r.stdout)
    arts = gh(f"repos/{REPO}/actions/runs/{run_id}/artifacts").get("artifacts", [])
    part = re.compile(rf"heardpart_s{surah:03d}_from(\d+)\.json$")
    for art in arts:
        zf = zipfile.ZipFile(io.BytesIO(gh(f"repos/{REPO}/actions/artifacts/{art['id']}/zip", raw=True)))
        for nm in zf.namelist():
            if nm.endswith(f"heard_s{surah:03d}.json"):
                m = json.loads(zf.read(nm))
                if heard_gate.partial_map_error(m):
                    raise SystemExit(f"⛔ {nm} يحمل {heard_gate.PARTIAL_KEY} باسم الخريطة الكاملة — مردود")
                return m
            g = part.search(nm)
            if g:
                m = json.loads(zf.read(nm))
                if int(m.get(heard_gate.PARTIAL_KEY) or 0) != int(g.group(1)):
                    raise SystemExit(f"⛔ {nm}: بدءُ النافذة في الاسم غيرُ {heard_gate.PARTIAL_KEY} في الخريطة")
                return m
    raise SystemExit(f"⛔ لا خريطةَ سماعٍ للسورة {surah} في مخرَج التشغيلة {run_id}")


WITNESS_WORKFLOW = ".github/workflows/whisper_witness.yml"


def witness_run_error(run_id, run):
    """⛔ (‏قرار القائد 2026-11-10 · #101) الشاهدُ يُقبل من تشغيلةٍ **ناجحةٍ لسير العمل `whisper_witness.yml`** في هذا المستودع
    على `main` بإطلاقٍ يدويّ — لا من أيّ تشغيلةٍ تحمل ملفّاً بالاسم نفسِه. يُرجع سببَ الردّ أو None."""
    if not re.fullmatch(r"\d{6,15}", str(run_id)):
        return f"معرّفُ التشغيلة {run_id!r} ليس رقماً"
    if not isinstance(run, dict) or str(run.get("id")) != str(run_id):
        return f"لا تشغيلةَ {run_id} في {REPO}"
    if run.get("path") != WITNESS_WORKFLOW:
        return f"التشغيلة {run_id} من {run.get('path')} لا من {WITNESS_WORKFLOW}"
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        return f"التشغيلة {run_id} لم تنجح ({run.get('status')}/{run.get('conclusion')})"
    if (run.get("repository") or {}).get("full_name") != REPO or (run.get("head_repository") or {}).get("full_name") != REPO:
        return f"التشغيلة {run_id} ليست من {REPO} نفسِه"
    if run.get("head_branch") != "main" or run.get("event") != "workflow_dispatch":
        return f"التشغيلة {run_id} على {run.get('head_branch')}/{run.get('event')} لا على main بإطلاقٍ يدويّ"
    return None


def load_witness(run_id, surah):
    """شاهدُ Whisper من مخرَج تشغيلة `whisper_witness.yml` على GitHub (‏كما تُقرأ خريطةُ السماع) لا من ملفٍّ يكتبه المُطلِق.
    ⛔ وتُفحص التشغيلةُ نفسُها أوّلاً (‏`witness_run_error`) ثمّ يُقرأ مخرَجُها المسمّى باسمها وحده."""
    def gh(path, raw=False):
        r = subprocess.run(["gh", "api", path], capture_output=True)
        if r.returncode:
            raise SystemExit(f"⛔ gh api {path}: {r.stderr.decode('utf-8', 'replace')[:200]}")
        return r.stdout if raw else json.loads(r.stdout)
    why = witness_run_error(run_id, None if not re.fullmatch(r"\d{6,15}", str(run_id))
                            else gh(f"repos/{REPO}/actions/runs/{run_id}"))
    if why:
        raise SystemExit(f"⛔ شاهدٌ مردود: {why}")
    want = f"whisper-witness-s{int(surah)}-{run_id}"
    for art in gh(f"repos/{REPO}/actions/runs/{run_id}/artifacts").get("artifacts", []):
        if art.get("name") != want or art.get("expired"):
            continue
        zf = zipfile.ZipFile(io.BytesIO(gh(f"repos/{REPO}/actions/artifacts/{art['id']}/zip", raw=True)))
        for nm in zf.namelist():
            if nm.endswith(f"whisper_s{int(surah):03d}.json"):
                return json.loads(zf.read(nm))
    raise SystemExit(f"⛔ لا شاهدَ Whisper للسورة {surah} في مخرَج التشغيلة {run_id} ({want})")


def peer_medians(cl, bucket, riwaya, surah, own_key, cap=40):
    """وسيطُ مدّة كلّ آيةٍ من السورة عند النظراء المنشورين في الرواية (‏حتى `cap` فهرساً بترتيبٍ ثابت)."""
    keys, tok = [], None
    while True:
        kw = {"Bucket": bucket, "Prefix": f"timings/{riwaya}/"}
        if tok:
            kw["ContinuationToken"] = tok
        r = cl.list_objects_v2(**kw)
        keys += [o["Key"] for o in r.get("Contents", []) if o["Key"].endswith(".jz") and o["Key"] != own_key]
        tok = r.get("NextContinuationToken")
        if not tok:
            break
    durs = {}
    for k in sorted(keys)[:cap]:
        try:
            ix = json.loads(gzip.decompress(cl.get_object(Bucket=bucket, Key=k)["Body"].read()).decode("utf-8"))
        except Exception:                                                # noqa: BLE001
            continue
        for e in ix.get("entries") or []:
            sa, a = _key(e["ayahId"])
            if sa == surah and e.get("endMs") is not None and int(e["endMs"]) > int(e["startMs"]):
                durs.setdefault(a, []).append(int(e["endMs"]) - int(e["startMs"]))
    return {a: sorted(v)[len(v) // 2] for a, v in durs.items() if len(v) >= 3}


def disputed_claims(out, surah, hmap, claims, runs_txt, wits=None):
    """{سورة: {آية: {otherAyah, witnesses}}} لـ`transform.disputedAnchors` — يُحكم عليها هنا بـ`heard_gate.disputed_verdict`
    نفسِها قبل الرفع فلا يُرفع ادّعاءٌ تردّه البوّابة. `wits` {تشغيلة: شاهد} للاختبار، وإلا تُقرأ من مخرَج التشغيلات."""
    import heard_gate as HG                                              # noqa: PLC0415
    if HG.partial_map_error(hmap):
        raise SystemExit(f"⛔ --disputed: {HG.partial_map_error(hmap)}")
    runs = [r.strip() for r in str(runs_txt or "").split(",") if r.strip()]
    if wits is None:
        if len(set(runs)) != len(runs) or len(runs) < HG.DISPUTED_MIN_WITNESSES:
            raise SystemExit(f"⛔ --disputed يلزمه {HG.DISPUTED_MIN_WITNESSES} تشغيلتان متمايزتان في --disputed-runs")
        wits = {r: load_witness(r, surah) for r in runs}
    keep = ("surah", "riwaya", "fileRef", "sha256", "model", "computeType", "ayahs")
    rec = {str(a): {"otherAyah": int(o), "witnesses": {str(r): {k: w.get(k) for k in keep} for r, w in wits.items()}}
           for a, o in sorted(claims.items())}
    present = sorted({_key(e["ayahId"])[0] for e in out["entries"]})
    want = index_fields.sha_by_surah(out, present).get(surah)
    starts = {_key(e["ayahId"])[1]: int(e["startMs"]) for e in out["entries"] if _key(e["ayahId"])[0] == surah}
    cmap = HG.compact_map(hmap)
    rows = HG.surah_rows(starts, cmap)
    probe = dict(out)
    probe["transform"] = {**(out.get("transform") or {}), "disputedAnchors": {str(surah): rec}}
    why, ev = HG.disputed_verdict(surah, rows, cmap, want, probe,
                                 sources={str(r): HG.disputed_src_rec(w) for r, w in wits.items()})
    if why:
        raise SystemExit(f"⛔ المراسي المتنازَعُ عليها لا تجتاز heard_gate: {why}")
    rest = HG.surah_verdict(rows)
    if rest:
        print(f"  ⚠️ بعد قبول المتنازَع عليه تبقى السورةُ مردودةً عند البوّابة: {rest}")
    return {str(surah): rec}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--key", required=True)
    ap.add_argument("--sha", required=True)
    ap.add_argument("--surah", type=int, required=True)
    ap.add_argument("--run", required=True, help="تشغيلةُ ctc_heard_probe (‏build=false) على صوت السورة نفسِه")
    ap.add_argument("--pin", required=True, help="آية:بدءٌ بالم.ث، مفصولةً بفواصل")
    ap.add_argument("--trim", default="", help="آية:نهايةٌ لما قبل أوّل تثبيت — ⛔ يلزمه --trim-witness-runs (‏#99)")
    ap.add_argument("--last-end", type=int, default=None,
                    help="نهايةٌ مقيسةٌ لآخر آيةٍ في السورة (‏نهايةُ أدائها المثبَّت)")
    ap.add_argument("--witness-run", default="",
                    help="تشغيلةُ whisper_witness: شاهدٌ إضافيٌّ لآياتٍ مرساتُها دون شرط الجودة (‏بلا شرطٍ يُرخى)")
    ap.add_argument("--witness-fuzzy", action="store_true",
                    help="المسارُ المشابه (‏قرار خيط 2.0 2026-11-07 لدورة saad): تشابهُ الكلمات الطرفيّة ≥0.8 بقيد ±20٪")
    ap.add_argument("--trim-witness-runs", default="",
                    help="تشغيلتا whisper_witness (‏أو أكثر) مفصولتين بفواصل: حدُّ --trim من بدء أوّل كلمةٍ للتالية")
    ap.add_argument("--disputed", default="",
                    help="آية:الآيةُ الأخرى المسموعةُ عند مرساتها، بفواصل (‏heard_gate.disputed_verdict) — مثل 82:81,93:92")
    ap.add_argument("--disputed-runs", default="", help="تشغيلتا whisper_witness (‏أو أكثر) تُضمَّنان دليلاً لكلّ متنازَع")
    ap.add_argument("--opener-runs", default="",
                    help="تشغيلتا whisper_witness (‏أو أكثر): مطلعُ الحروف المقطّعة — يُثبَّت 2 بـ--pin وتُمَدّ 1 إلى الوراء "
                         f"({OPENER_VERSION})")
    ap.add_argument("--reason", required=True)
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    if a.witness_fuzzy and not a.witness_run:
        raise SystemExit("⛔ --witness-fuzzy لا يعمل إلا مع --witness-run")
    import promote
    cl, bucket = promote.s3()
    body = cl.get_object(Bucket=bucket, Key=a.key)["Body"].read()
    live = hashlib.sha256(body).hexdigest()
    if not live.startswith(a.sha):
        raise SystemExit(f"⛔ البصمة لا تطابق: الحيّة {live[:16]} والمطلوبة {a.sha}")
    idx = json.loads(gzip.decompress(body).decode("utf-8"))
    hmap = load_map(a.run, a.surah)
    wit = ref = expected = None
    evidence = {}
    if a.witness_run:
        wit = load_witness(a.witness_run, a.surah)
        riw = idx.get("riwaya") or "hafs"
        ref = lambda s, ay: ref_words_for(riw, s, ay)                    # noqa: E731
        med = peer_medians(cl, bucket, riw, a.surah, a.key)
        own = {_key(e["ayahId"])[1]: int(e["endMs"]) - int(e["startMs"]) for e in idx["entries"]
               if _key(e["ayahId"])[0] == a.surah and e.get("endMs") is not None}
        pins0 = parse_pairs(a.pin)
        expected = expected_from_peers(own, med, skip=set(pins0) | {x - 1 for x in pins0})
    twits, tev = None, {}
    if a.trim_witness_runs:
        runs = [r.strip() for r in a.trim_witness_runs.split(",") if r.strip()]
        if len(set(runs)) != len(runs):
            raise SystemExit("⛔ --trim-witness-runs: تشغيلةٌ مكرّرة")
        twits = {r: load_witness(r, a.surah) for r in runs}
        if ref is None:
            riw = idx.get("riwaya") or "hafs"
            ref = lambda s, ay: ref_words_for(riw, s, ay)                # noqa: E731
    owits, oev = None, {}
    if a.opener_runs:
        runs = [r.strip() for r in a.opener_runs.split(",") if r.strip()]
        if len(set(runs)) != len(runs):
            raise SystemExit("⛔ --opener-runs: تشغيلةٌ مكرّرة")
        owits = {r: load_witness(r, a.surah) for r in runs}
        if ref is None:
            riw = idx.get("riwaya") or "hafs"
            ref = lambda s, ay: ref_words_for(riw, s, ay)                # noqa: E731
    out, report, changed = pin(idx, a.surah, hmap, parse_pairs(a.pin), parse_pairs(a.trim),
                               a.last_end, witness=wit, ref_words=ref, expected=expected,
                               evidence=evidence, witness_fuzzy=a.witness_fuzzy,
                               trim_witnesses=twits, trim_evidence=tev,
                               opener_witnesses=owits, opener_evidence=oev)
    out["transform"] = {
        **({"truncatedTail": idx["transform"]["truncatedTail"]}
           if isinstance(idx.get("transform"), dict) and idx["transform"].get("truncatedTail") else {}),
        "op": f"heard_pin:{a.surah}", **inherit_declaration(idx, a.key, live),
        "evidenceRun": str(a.run), "evidenceAudioSha256": hmap.get("sha256"),
        **({"evidenceWindowStartMs": int(hmap[heard_gate.PARTIAL_KEY])} if hmap.get(heard_gate.PARTIAL_KEY) else {}),
        "pins": report, "changedAyahs": changed, "reason": a.reason,
        "at": int(time.time() * 1000), "by": "pin_heard",
        "note": "بدءُ كلّ آيةٍ مثبَّتةٍ أداءٌ مسموعٌ مقيس؛ ما تكرّر قبله بلا مدخل؛ يلزمه الإحصاءُ الشامل.",
    }
    if oev:
        out["transform"]["openerLetters"] = {str(a.surah): oev}
    if tev:
        out["transform"]["trimWitness"] = {str(k): v for k, v in sorted(tev.items())}
    if a.witness_run:
        out["transform"]["witnessRun"] = str(a.witness_run)
        out["transform"]["pinEvidence"] = {str(k): v for k, v in sorted(evidence.items())}
        if a.witness_fuzzy:
            out["transform"]["witnessFuzzy"] = {"sim": W_FUZZ_SIM, "lenBand": [W_FUZZ_LEN_LO, W_FUZZ_LEN_HI],
                                                "decision": "خيط 2.0 · 2026-11-07 · دورة saad"}
    if a.disputed:
        out["transform"]["disputedAnchors"] = disputed_claims(out, a.surah, hmap, parse_pairs(a.disputed),
                                                              a.disputed_runs)
    blob = gzip.compress(json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), 9)
    new_sha = hashlib.sha256(blob).hexdigest()
    target = f"timings-staging/{idx.get('riwaya')}/{idx.get('reciterId')}.{new_sha[:8]}.jz"
    print(f"من {a.key} ({live[:12]}) · س{a.surah} · الخريطة {a.run} ({str(hmap.get('sha256'))[:8]})")
    for r in report:
        print("  📌", r)
    print(f"  آياتٌ تغيّرت حدودُها: {changed}")
    print(f"إلى {target} ({len(blob)} بايت · بصمة {new_sha[:12]})")
    if not a.yes:
        print("(عرضٌ فقط — أضف --yes للرفع)")
        return
    cl.put_object(Bucket=bucket, Key=target, Body=blob, ContentType="application/gzip")
    got = cl.head_object(Bucket=bucket, Key=target)["ContentLength"]
    print(f"↑ رُفع · الدلو {got} · المحلّي {len(blob)} → {'✅' if got == len(blob) else '❌'}")


if __name__ == "__main__":
    main()
