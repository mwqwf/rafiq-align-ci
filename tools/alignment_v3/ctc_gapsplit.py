#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""قسمةُ المدخل الذي ابتلع جارتَه — محاذاةٌ قسريّةٌ بـCTC على **نافذة الجارتين وحدها**.

⭐ **سببُه مقيسٌ 2026-09-29** (`tools/index_qa/gap_probe.py` على المنشور كلِّه):
من 120 آيةً غائبةً داخل سورٍ حاضرة **لا واحدةَ لها فجوةٌ بين جارتَيها** (fill=0)،
و**86 فجوتُها صفر**: نهايةُ السابقة = بدايةُ اللاحقة. ⇒ صوتُ الآية الغائبة **داخلَ
مدخل جارتها**، فالجارةُ في المنشور تمتدّ على آيتين (عطبُ توقيتٍ حيّ فوق الغياب).
والمحرّكان عجزا عن الآية **في السورة كلّها**؛ أمّا نافذةٌ نعرف أنّها تحوي النصوصَ
الثلاثة بالترتيب (السابقة · الغائبة · اللاحقة) فمحاذاةُ نصٍّ معلومٍ فيها أيسرُ بكثير.

⛔ **ما لا يفعله:** لا يلمس مدخلاً غيرَ الجارتين، ولا يحرّك بدايةَ السابقة ولا نهايةَ
اللاحقة (حدّا النافذة من الأب نفسِه)، ولا يولّد نصّاً (النصُّ من الرواية).
⛔ **حُرّاسٌ قبل أيّ قبول** — وما لم يجتزها يبقى غائباً ويُسمّى:
   ١. ثقةُ CTC لكلّ آيةٍ جديدة ≥ 0.45 (حدُّ MED في `_conf`).
   ٢. مدّةُ كلّ آيةٍ جديدة بين 0.5× و2.0× المتوقَّع (حروفُها × معدّلُ القارئ في السورة).
   ٣. الجارتان بعد القسمة لا تنكمش إحداهما دون 0.5× متوقَّعها.
   ٤. لا HIGH بلا برهان صمت (D-025): الثقةُ تُسقَف 0.74 ما لم يقع الحدُّ في صمت.
⚖️ والحكمُ الحاسمُ للبوّابة الصوتيّة (مطالع · أربعة ملوح · إحصاءٌ شامل · عتبة 5%).

المخرَج: `s<سورة>.json` بصيغة `batch_run` نفسِها (السورةُ كاملةً: مداخلُ الأب كما هي
إلا الجارتين المقسومتين، والمقسومُ مضاف) ⇒ يدمجه `splice_surah.py` بحرّاسه.

    python tools/alignment_v3/ctc_gapsplit.py --index parent.jz --surahs 55,74 \
        --riwaya warsh --out-dir tools/alignment/work/batch_<id>
"""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import os
import statistics
import sys
import urllib.request

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "alignment"))
from ctc_seg import BASMALA, SR, _conf, _emissions, _segment  # noqa: E402
from common import load_index, load_text, norm, to_wav16k  # noqa: E402
from vad import read_wav, silences, snap_to_silence  # noqa: E402
from spoken_letters import alignment_text  # noqa: E402

MIN_CONF = 0.45
DUR_LO, DUR_HI = 0.5, 2.0
NEIGH_LO = 0.5
# ⭐ شاهدُ السماع لحدّ المدّة الأعلى وحده (fixS2 · 2026-10-03 — مسوّدةٌ لا تُدفع قبل إذن المالك):
#    آيةٌ تُسمع فعلاً أطولَ من ضعف المتوقَّع بالحروف (‏55:64 «مدهامّتان» عند العفاسي ~7ث والمتوقَّع 3.1ث)
#    يردّها حدُّ 2× وهي صحيحة. تُقبل فوقه **فقط** إن وافق حدّاها خريطةَ السماع المستقلّة
#    (‏ctc_heard_map: فكٌّ جشعٌ بزمن الحرف) بفرقٍ صغيرٍ مقيس، بمِرساةٍ قويّةٍ وأداءٍ منفردٍ لا مكرّر.
#    المعايرة (156 حدّاً قُبلت بالحرّاس كما هي في الموجة الرابعة · fixS2): فرقُ البدء p90=521م.ث،
#    والنهاية p90=928م.ث ⇒ السماحُ 700/1000م.ث. ولا يمسّ: حدَّ 0.5× الأدنى، ولا الثقة 0.45،
#    ولا حارسَ الجارة، ولا عتبة 5%. وسقفٌ مطلقٌ 4× فلا تُقبل مدّةٌ بلا حدّ.
HW_START_TOL, HW_END_TOL = 700, 1000
HW_MIN_Q = 0.85
HW_REPEAT_Q = 0.7
HW_ABS_HI = 4.0
ABSORBED_MS = 400
UA = {"User-Agent": "Mozilla/5.0 (QuranRafiq tools)"}
BAND_CONF = {"HIGH": 0.85, "MED": 0.6, "LOW": 0.4}


def heard_witness_ok(heard: dict | None, k: int, start: int, end: int, exp: float):
    """(مقبول؟، السبب) لآيةٍ مدّتُها فوق DUR_HI× — بشاهد خريطة السماع وحده، وأيُّ نقصٍ فيه ردّ."""
    if not heard:
        return False, "لا شاهدَ سماع"
    x = (heard.get("heardMap") or {}).get(str(k)) or {}
    a = x.get("anchorMs")
    if not x.get("heard") or not a or (x.get("anchorQuality") or 0) < HW_MIN_Q:
        return False, "مِرساةُ السماع ضعيفةٌ أو غائبة"
    strong = [o for o in x.get("occurrences") or [] if o[2] >= HW_REPEAT_Q]
    if len(strong) > 1:
        return False, "أداءٌ مكرّرٌ في الخريطة — لا يُرجَّح أحدُهما"
    if abs(start - a[0]) > HW_START_TOL or abs(end - a[1]) > HW_END_TOL:
        return False, f"الحدّان يخالفان السماع ({start - a[0]:+d}/{end - a[1]:+d}م.ث)"
    if end - start > HW_ABS_HI * exp:
        return False, f"فوق السقف المطلق {HW_ABS_HI}×"
    return True, f"شاهدُ السماع {a[0]}–{a[1]} (جودة {x['anchorQuality']})"


def chars(t: str) -> int:
    return len(norm(t).replace(" ", ""))


def fetch(url: str, dst: str) -> None:
    last = None
    for _ in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90) as r, \
                    open(dst, "wb") as f:
                want = int(r.headers.get("Content-Length") or 0)
                f.write(r.read())
            if not want or os.path.getsize(dst) == want:
                return
            last = RuntimeError(f"مبتور {os.path.getsize(dst)} من {want}")
        except Exception as ex:                        # noqa: BLE001
            last = ex
    raise RuntimeError(f"تعذّر تنزيل {url}: {last}")


def plan_splits(ents: dict, n: int, text_of, rate: float):
    """مواضعُ القسمة في سورة: (الصنف، b0، b1).
    ‏gap: مدىً غائبٌ بين جارتين فجوتُهما صفر (‏الصوتُ في الجارة) ·
    ‏opener: غيابٌ من الآية الأولى وله لاحقة (‏النافذةُ من بدء الملفّ) ·
    ‏tail: غيابٌ حتى آخر السورة وله سابقة (‏النافذةُ حتى نهاية الملفّ)."""
    out, a = [], 1
    while a <= n:
        if a in ents:
            a += 1
            continue
        b0 = a
        while a <= n and a not in ents:
            a += 1
        b1 = a - 1
        p, q = ents.get(b0 - 1), ents.get(b1 + 1)
        if p and q and q["startMs"] - p["endMs"] < ABSORBED_MS:
            out.append(("gap", b0, b1))
        elif b0 == 1 and q:
            out.append(("opener", b0, b1))
        elif b1 == n and p:
            out.append(("tail", b0, b1))
    return out


def split_window(x: np.ndarray, ws: int, we: int, texts: list[str]):
    """يحاذي النصوصَ بالترتيب على [ws، we] م.ث ⇒ [(بدءٌ مطلق، نهايةٌ مطلقة، ثقة)]."""
    clip = x[ws * SR // 1000: we * SR // 1000]
    segs = _segment(_emissions(clip), len(clip), texts)
    return [(ws + int(st * 1000), ws + int(en * 1000), _conf(sc)) for st, en, sc in segs]


NB_FIRST_MAX_MS = 2500   # ‏«لا بسملة» مقيسٌ بخريطة السماع: الآيةُ الأولى تُسمع قبل هذا وإلا رُدّت


def parse_rewindow_spec(spec: str):
    """«س:أ-ب» أو «س:1-ب/nb» ⇒ (س، أ، ب، لا_بسملة). المطلعُ (أ=1) والخاتمةُ (ب=آخرُ السورة)
    جائزان منذ 2026-10-03 (‏fixS1): آيةٌ حاضرةٌ في طرف السورة حدُّها معطوبٌ بلا جارٍ ثابتٍ من جهته
    ⇒ حدُّ تلك الجهة بدءُ الملفّ أو نهايتُه. ‏/nb لا تجوز إلا مع أ=1: الملفُّ يبدأ بالآية الأولى
    بلا بسملة بشاهد خريطة السماع، ويحرسها `NB_FIRST_MAX_MS`."""
    spec = spec.strip()
    nb = spec.endswith("/nb")
    if nb:
        spec = spec[:-3]
    s_, rng = spec.split(":")
    r0, r1 = (int(v) for v in rng.split("-"))
    if r0 < 1 or r1 < r0:
        raise ValueError("المدى مقلوب أو يبدأ قبل الآية الأولى")
    if nb and r0 != 1:
        raise ValueError("‏/nb للمطلع وحده (أ=1)")
    return int(s_), r0, r1, nb


def rewindow_kind(r0: int, r1: int, n: int, ents: dict):
    """(الصنف، سببُ الردّ أو None): rewin بين جارتين · rewhead من بدء الملفّ · rewtail حتى نهايته.
    ⛔ السورةُ كلُّها (1..n) ليست إعادةَ نافذة — بابُها المحاذاةُ الكاملة."""
    if r1 > n:
        return "rewin", "المدى يتجاوز آخر السورة"
    if r0 == 1 and r1 == n:
        return "rewin", "المدى السورةُ كلُّها — ليس إعادةَ نافذة"
    if r0 == 1:
        kind, need = "rewhead", range(1, r1 + 2)
    elif r1 == n:
        kind, need = "rewtail", range(r0 - 1, n + 1)
    else:
        kind, need = "rewin", range(r0 - 1, r1 + 2)
    if any(k not in ents for k in need):
        return kind, "المدى وجاره الثابت يجب أن يكونوا حاضرين في الأب"
    return kind, None


def explicit_gap(ents: dict, n: int, b0: int, b1: int):
    """فجوة مسماة صراحة، ولو فصل الجارتين صمت؛ حراس المحاذاة لا تتغير."""
    if b0 < 2 or b1 < b0 or b1 >= n:
        raise ValueError("مدى الغياب يلزمه جار حاضر قبله وبعده داخل السورة")
    if b0 - 1 not in ents or b1 + 1 not in ents:
        raise ValueError("مرساة الغياب غائبة؛ لا تخمين")
    if any(k in ents for k in range(b0, b1 + 1)):
        raise ValueError("مدى الغياب الصريح يجب أن يكون غائباً كله في الأب")
    return ("gap", b0, b1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--surahs", required=True)
    ap.add_argument("--riwaya", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--context-ayahs", type=int, choices=(1, 2, 3), default=1,
                    help="عدد الجارات الحاضرة للمراسي؛ 1 يحفظ المسار القائم، و2/3 يعيدان نافذة أوسع بحراس الثقة والمدة أنفسهم")
    ap.add_argument("--spoken-openers", action="store_true", help="أسماء الحروف المنطوقة لمدخل المحاذاة وحده، دون تغيير حراس المدة")
    ap.add_argument("--quran-model", action="store_true", help="نموذج تلاوة مرخص مثبت البصمة؛ مدخل الرسم الأصلي ومحرك مستقل وإحصاء كامل")
    ap.add_argument("--starts-with-first-ayah", action="store_true",
                    help="تسجيل مثبت صوتياً يبدأ بالآية الأولى دون بسملة؛ مرساة بدء الملف صفر، لسورة واحدة فقط")
    # ⭐ (2026-09-30 · f_hajry الرحمن): **إعادةُ نافذةٍ** لمدىً حاضرٍ حدودُه معطوبة — «55:41-75» ⇒ تُحاذى
    #    نصوصُ 41..75 بـCTC بين جارتين ثابتتين من الأب (‏40 بدءاً · 76 نهايةً) على نافذتهما وحدها. سببُه مقيس:
    #    الإحصاءُ الشامل 7.7% جسيماً في 41–75 على CTC السورة كاملةً، وWhisper عجز عنها (‏اللازمةُ المتكرّرة
    #    تُضلّ التفريغ) — والمحاذاةُ القسريّةُ لنصٍّ معلومٍ في نافذةٍ ضيّقة لا تُضلّها اللازمة.
    #    ⛔ بالحُرّاس نفسِها (‏ثقة · مدّة · جارة) والإحصاءُ الشاملُ هو الحَكَم.
    ap.add_argument("--rewindow", default="", help="مدى آياتٍ حاضرةٍ يُعاد بنافذته: 55:41-75[,…]")
    ap.add_argument("--heard-witness-dir", default="",
                    help="مجلّدُ heard_sNNN.json من ctc_heard_map: يُقبل به حدُّ المدّة الأعلى وحده بشروطه (fixS2)")
    ap.add_argument("--explicit-gap", default="", help="غياب مسمى بين جارتين حاضرتين ولو فصلتهما فجوة: 26:2-3؛ حراس الثقة والمدة نفسها")
    a = ap.parse_args()
    import ctc_seg as C
    if C._M.get('alignmentModelId') and not a.quran_model:
        ap.error('النموذج المتخصص المحمل يحتاج علم محركه الصريح')
    model_evidence = None
    if a.quran_model:
        if a.spoken_openers:
            ap.error('مدخل الرسم للنموذج المتخصص لا يجتمع مع تهجئة الحروف')
        import quran_ctc_model as Q
        model_evidence = Q.configure()
    requested_surahs = [int(v) for v in a.surahs.split(",") if v.strip()]
    if a.starts_with_first_ayah and len(requested_surahs) != 1:
        ap.error("شاهد بدء الملف يخص سورة واحدة صريحة")
    rewin = {}
    gaps = {}
    for spec in [x for x in a.explicit_gap.split(",") if x.strip()]:
        s_, rng = spec.split(":")
        r0, r1 = (int(v) for v in rng.split("-"))
        if int(s_) not in requested_surahs:
            ap.error("سورة الغياب الصريح يجب أن تكون ضمن السور المطلوبة")
        gaps.setdefault(int(s_), []).append((r0, r1))
    nobasmala = set()
    for spec in [x for x in a.rewindow.split(",") if x.strip()]:
        try:
            s_, r0, r1, nb = parse_rewindow_spec(spec)
        except ValueError as ex:
            raise SystemExit(f"⛔ مدى إعادة النافذة غيرُ صالح: {spec} ({ex})")
        rewin.setdefault(s_, []).append((r0, r1))
        if nb:
            nobasmala.add(s_)
    os.makedirs(a.out_dir, exist_ok=True)
    idx = json.loads(gzip.decompress(open(a.index, "rb").read()).decode("utf-8"))
    qidx = load_index()
    text = load_text(a.riwaya)
    report = []
    _heard_cache = {}

    def heard_of(s):
        if s not in _heard_cache:
            fp = os.path.join(a.heard_witness_dir, f"heard_s{s:03d}.json")
            _heard_cache[s] = json.load(open(fp, encoding="utf-8")) if os.path.exists(fp) else None
        return _heard_cache[s]
    witness_log = {}
    for s in requested_surahs:
        meta = next(m for m in qidx["surahs"] if m["n"] == s)
        st0, n = meta["start"], meta["ayahs"]
        rows = [e for e in idx["entries"] if int(e["ayahId"].split(":")[0]) == s]
        ents = {int(e["ayahId"].split(":")[1]): dict(e) for e in rows
                if e.get("startMs") is not None and e.get("endMs") is not None}
        parent_ents = copy.deepcopy(ents)
        if a.starts_with_first_ayah and (1 in ents or 2 not in ents):
            ap.error("مرساة بدء الملف لاسترجاع الآية الأولى وحدها مع حضور الثانية")
        if not ents:
            report.append(f"س{s}: لا مداخلَ في الأب — ليست من هذا الباب")
            continue
        t_of = lambda k: text[st0 + k - 1]              # noqa: E731
        rates = [(ents[k]["endMs"] - ents[k]["startMs"]) / max(1, chars(t_of(k))) for k in ents]
        rate = statistics.median(rates)
        splits = plan_splits(ents, n, t_of, rate)
        for r0, r1 in gaps.get(s, []):
            try:
                proposed = explicit_gap(ents, n, r0, r1)
            except ValueError as ex:
                ap.error(f"س{s}:{r0}-{r1}: {ex}")
            if proposed not in splits:
                splits.append(proposed)
        for r0, r1 in rewin.get(s, []):
            kind, why = rewindow_kind(r0, r1, n, ents)
            if why:
                report.append(f"س{s}:{r0}-{r1} ({kind}): ⛔ {why}")
                continue
            splits.append((kind, r0, r1))
        if not splits:
            report.append(f"س{s}: لا غيابَ مبتلعاً بين جارتين")
            continue
        refs = {e.get("fileRef") for e in rows}
        if len(refs) != 1:
            report.append(f"س{s}: ⛔ روابطُ صوتٍ متعدّدة في السورة {refs} — لا قسمة")
            continue
        url = refs.pop()
        mp3 = os.path.join(a.out_dir, f"g{s:03d}.mp3")
        fetch(url, mp3)
        sha = hashlib.sha256(open(mp3, "rb").read()).hexdigest()
        wav = to_wav16k(mp3)
        x = read_wav(wav).astype(np.float32)
        sil = silences(wav)
        added = []
        total_ms = int(len(x) * 1000 / SR)
        for kind, b0, b1 in splits:
            miss = list(range(b0, b1 + 1))
            lead = []
            if kind in ("gap", "rewin"):
                left, right = max(1, b0 - a.context_ayahs), min(n, b1 + a.context_ayahs)
                ks = list(range(left, right + 1))
                if any(k not in ents and k not in miss for k in ks):
                    report.append(f"س{s}:{b0}-{b1}: ⛔ مرساة السياق الأوسع غائبة — لا تخمين")
                    continue
                p, q = ents[left], ents[right]
                ws, we, fixed = p["startMs"], q["endMs"], (0, -1)
            elif kind == "rewhead":
                # ⭐ مطلعٌ حاضرٌ حدُّه معطوب: النافذةُ من بدء الملفّ حتى نهاية الجارة اللاحقة الثابتة.
                right = min(n, b1 + a.context_ayahs)
                if any(k not in ents for k in range(1, right + 1)):
                    report.append(f"س{s}:{b0}-{b1}: ⛔ مرساة المطلع غائبة — لا تخمين")
                    continue
                q = ents[right]
                lead = [] if s in (1, 9) or s in nobasmala else [norm(BASMALA)]
                ks, ws, we, fixed = list(range(1, right + 1)), 0, q["endMs"], (-1,)
            elif kind == "rewtail":
                # ⭐ خاتمةٌ حاضرةٌ حدُّها معطوب: النافذةُ من بدء الجارة السابقة الثابتة حتى نهاية الملفّ.
                left = max(1, b0 - a.context_ayahs)
                if any(k not in ents for k in range(left, n + 1)):
                    report.append(f"س{s}:{b0}-{b1}: ⛔ مرساة الخاتمة غائبة — لا تخمين")
                    continue
                p = ents[left]
                ks, ws, we, fixed = list(range(left, n + 1)), p["startMs"], total_ms, (0,)
            elif kind == "opener":
                right = min(n, b1 + a.context_ayahs)
                if any(k not in ents for k in range(b1 + 1, right + 1)):
                    report.append(f"س{s}:{b0}-{b1}: ⛔ مرساة المطلع الأوسع غائبة — لا تخمين")
                    continue
                q = ents[right]
                lead = [] if s in (1, 9) or a.starts_with_first_ayah else [norm(BASMALA)]
                ks, ws, we, fixed = list(range(1, right + 1)), 0, q["endMs"], (-1,)
            else:
                left = max(1, b0 - a.context_ayahs)
                if any(k not in ents for k in range(left, b0)):
                    report.append(f"س{s}:{b0}-{b1}: ⛔ مرساة الخاتمة الأوسع غائبة — لا تخمين")
                    continue
                p = ents[left]
                ks, ws, we, fixed = list(range(left, n + 1)), p["startMs"], total_ms, (0,)
            try:
                references = [Q.reference_text(t_of(k)) if a.quran_model else
                              alignment_text(s, k, t_of(k)) if a.spoken_openers else norm(t_of(k)) for k in ks]
                if a.quran_model and lead:
                    lead = [Q.reference_text('بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ')]
                segs = split_window(x, int(ws), int(we), lead + references)[len(lead):]
            except Exception as ex:                    # noqa: BLE001
                report.append(f"س{s}:{b0}-{b1} ({kind}): تعذّرت المحاذاة — {str(ex)[:80]}")
                continue
            starts = [sg[0] for sg in segs]
            if kind == "opener" and a.starts_with_first_ayah:
                starts[0] = 0  # مرساة الملف المثبتة؛ حراسا الثقة والمدة أدناه باقيان.
            if kind in ("gap", "tail", "rewin", "rewtail"):
                starts[0] = int(p["startMs"])       # بدءُ أول مرساة ثابتٌ من الأب
            ends = starts[1:] + [int(we) if kind not in ("tail", "rewtail") else min(int(segs[-1][1]), total_ms)]
            if kind in ("gap", "opener", "rewin", "rewhead"):
                ends[-1] = int(q["endMs"])            # نهايةُ آخر مرساة ثابتةٌ من الأب
            if kind == "rewhead" and s in nobasmala and starts[0] > NB_FIRST_MAX_MS:
                report.append(f"س{s}:{b0}-{b1} ({kind}): ⛔ رُدّت — شاهدُ «لا بسملة» يخالفه بدءُ {s}:1 عند "
                              f"{starts[0]}م.ث > {NB_FIRST_MAX_MS} (‏بسملةٌ محتملة)")
                continue
            fixed_idx = {i % len(ks) for i in fixed}
            witnessed = []
            why = None
            for i, k in enumerate(ks):
                dur, exp = ends[i] - starts[i], chars(t_of(k)) * rate
                if i in fixed_idx:
                    if dur < NEIGH_LO * exp:
                        why = f"الجارة {s}:{k} تنكمش إلى {dur}م.ث والمتوقَّع {exp:.0f}"
                    elif starts[i] != ents[k]["startMs"] and segs[i][2] < MIN_CONF:
                        why = f"مرساة {s}:{k} تغير بدءها وثقة الحد الجديد {segs[i][2]} < {MIN_CONF}"
                else:
                    if segs[i][2] < MIN_CONF:
                        why = f"{s}:{k} ثقةُ CTC {segs[i][2]} < {MIN_CONF}"
                    elif dur > DUR_HI * exp and a.heard_witness_dir:
                        hw_ok, hw_why = heard_witness_ok(heard_of(s), k, starts[i], ends[i], exp)
                        if hw_ok:
                            witnessed.append(f"{s}:{k} {dur}م.ث > {DUR_HI}×{exp:.0f} · {hw_why}")
                        else:
                            why = f"{s}:{k} مدّتُها {dur}م.ث والمتوقَّع {exp:.0f} (فوق {DUR_HI}×؛ {hw_why})"
                    elif not (DUR_LO * exp <= dur <= DUR_HI * exp):
                        why = f"{s}:{k} مدّتُها {dur}م.ث والمتوقَّع {exp:.0f} (خارج {DUR_LO}–{DUR_HI}×)"
                if why:
                    break
            if why:
                report.append(f"س{s}:{b0}-{b1} ({kind}): ⛔ رُدّت — {why}")
                continue
            for i, k in enumerate(ks):
                if i in fixed_idx:
                    if starts[i] != ents[k]["startMs"]:
                        _, on_sil = snap_to_silence(starts[i], sil, tolerance_ms=300)
                        ents[k]["conf"] = segs[i][2] if on_sil else min(segs[i][2], 0.74)
                        ents[k]["snapped"] = bool(on_sil)
                    ents[k]["startMs"], ents[k]["endMs"] = int(starts[i]), int(ends[i])
                    continue
                _t, on_sil = snap_to_silence(starts[i], sil, tolerance_ms=300)
                conf = segs[i][2] if on_sil else min(segs[i][2], 0.74)
                ents[k] = {"startMs": int(starts[i]), "endMs": int(ends[i]), "conf": conf,
                           "snapped": bool(on_sil)}
            added.append(f"{b0}" if b0 == b1 else f"{b0}-{b1}")
            if witnessed:
                witness_log.setdefault(s, []).extend(witnessed)
                report.append(f"س{s}:{b0}-{b1}: ⭐ مدّةٌ فوق {DUR_HI}× قُبلت بشاهد السماع: " + " · ".join(witnessed))
            report.append(f"س{s}:{b0}-{b1} ({kind}): ✅ قُسمت · " + " · ".join(
                f"{s}:{k} {starts[i]}–{ends[i]}" for i, k in enumerate(ks)))
        if not added:
            continue
        out_rows = []
        for k in range(1, n + 1):
            e = ents.get(k)
            if e is None:
                out_rows.append({"ayahIdx": k - 1, "startMs": None, "endMs": None, "conf": 0.0})
                continue
            conf = e.get("conf")
            if conf is None:
                conf = BAND_CONF.get(e.get("confBand"), 0.6)
            out_rows.append({"ayahIdx": k - 1, "startMs": int(e["startMs"]), "endMs": int(e["endMs"]),
                             "conf": float(conf), "snapped": not e.get("startApprox", False)
                             if "snapped" not in e else bool(e["snapped"]),
                             "inherited": e == parent_ents.get(k),
                             "matched": 0, "total": len(norm(t_of(k)).split())})
        with open(os.path.join(a.out_dir, f"s{s:03d}.json"), "w", encoding="utf-8") as f:
            json.dump({"fileRef": url, "sha256": sha, "surah": s, "engine": Q.ENGINE if a.quran_model else "ctc-gapsplit-1",
                       **({'alignmentModel': model_evidence} if model_evidence else {}),
                       "gapsplit": added, "entries": out_rows,
                       **({"heardWitness": witness_log[s]} if witness_log.get(s) else {}),
                       **({"startsWithFirstAyah": True} if a.starts_with_first_ayah else {})}, f, ensure_ascii=False)
    print("\n".join(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
