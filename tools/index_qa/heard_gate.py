#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""بوّابةُ السماع (‏fixT · 2026-10-03): **بدءُ كلّ آيةٍ منشورة يطابق موضعَها المسموع.**

⭐ سببُها مقيسٌ (‏`ops/out/audit-r2-20261003.md` البند 3): في 5155 سورةً على 152 فهرساً
يُكبس توقيتُ أواخر السورة (‏وأحياناً كلِّها) قبل موضعه المسموع، وثبت بالسماع في 18 من 20.
والأحكامُ القائمة كلُّها عمياءُ عنه: ملوحُ العيّنة (‏`husary_warsh` 0/800 وفيه 41 آيةً منحرفة)،
و`full_audit` (‏معدّلُه وسيطُ السورة نفسِها فالمكبوسةُ كلُّها «متّسقة»)، والإحصاءُ الشامل
(‏يسمع نافذةَ المدخل لا موضعَ الآية في الملفّ).

## القاعدة (‏طريقةُ التدقيق نفسُها حرفاً، ثوابتُ لا تُقرأ من البيئة)
لكلّ آيةٍ حاضرةٍ في سورةٍ مفحوصة: المِرساةُ العامّةُ المسموعة من `ctc_heard_map --probe`
(‏أوّلُ حرفٍ مسموعٍ من الآية في محاذاةٍ رتيبةٍ للملفّ كلِّه بنصّ السورة).
- جودةُ المِرساة < 0.5 ⇒ «غير مقيسة» (‏لا يُحكم بها ولا لها).
- |البدءُ المنشور − المِرساة| > 1500م.ث ⇒ **انحراف**، إلا أن يكون للآية أداءٌ آخرُ مسموعٌ
  (‏تشابه ≥ 0.7) يبدأ على بُعد ≤ 2000م.ث من البدء المنشور **وهو منفصلٌ عن المِرساة** (‏قبل بدئها بأكثر
  من 1500م.ث أو عند نهايتها وبعدها؛ لا داخلَ مداها — `genuine_repeat`) ⇒ «تكرار» (‏التسجيلُ أعاد الآية).
- **السورةُ تُردّ** إن: (١) فيها انحرافٌ واحد؛ أو (٢) المقيسُ أقلُّ من نصف الحاضر
  (‏«ما لم يُحسم لم يُسمع» — كحارس الإحصاء)؛ أو (٣) **ذيلُها غيرُ مقيس**: آخرُ ثلاث آياتٍ
  حاضرةٍ فأكثر بلا مِرساةٍ مقيسة (‏آياتٌ منشورةٌ بلا صوتٍ يقابلها — noah 3:154–200).
- ⛔ **(٤) مِرساةٌ ضعيفةٌ في آيةٍ مسّها التحويل** (‏تشديد 2026-11-10): في سورةٍ معدّلة، كلُّ آيةٍ تخالف حدودُها
  (‏بدءٌ أو نهايةٌ أو ملفّ أو حضور) حدودَ المنشور وجودةُ مرساتها < 0.5 تردّ السورة، إلا أن يشهد لها شاهدُ Whisper
  بنصّها في موضعها بشروط `pin_heard._whisper_check` نفسِها (‏الطرفان · الثقة · بدءٌ ≤300م.ث من **بدء المرشّح**).
  سببُها مقيس: `kurdi.e8a49589` مرّ بمراسي 4:125–127 (‏0.254·0.262·0.318) وشاهدُ Whisper (‏التشغيلة 42734080787)
  سمع 125 ثمّ 126 ثمّ 128، فمدخلُ 4:127 (‏4133047–4166440) صوتُ آيتين أخريين — والقاعدةُ القديمة كانت «لا يُحكم بها
  ولا لها» فتتجاهلها. ⛔ لا يرخيه شيء: لا عتبةٌ ولا `--allow`، والشاهدُ يُعاد حكمُه من ملفّه في كلّ ترقية.
- والمرشّحُ يُردّ إن رُدّت **سورةٌ واحدةٌ معدّلةٌ عن المنشور** (‏كلُّ معدّلةٍ تُفحص، بلا انحرافٍ
  فوق 1.5ث ⇒ لا آيةَ فيها أسوأَ من المنشور).
- ⚖️ **والعيّنةُ للتقرير وحده** (‏قرارُ المنسّق 2026-10-03): 4 سورٍ غيرُ معدّلة، بذرتُها بصمةُ
  المرشّح، تُقاس وتُسجَّل انحرافاتُها في `sampleFindings` ولا تردّ المرشّح — فهي مطابقةٌ للمنشور
  حرفاً ولا تُدخل خطأً جديداً، وردُّ المرشّح بها كان يحجب تحسيناً حقيقيّاً. والتالفُ الذي تكشفه
  يُضاف إلى طابور الإصلاح التالي.

## الإثبات
`heard_gate.yml` يكتب `state-heard/<المفتاح مسطّحاً>.json` فيه لكلّ سورةٍ خريطتَها المختصرة
(‏المراسي والأداءات) وبصمةَ الصوت الذي سُمع. ⛔ و`promote.heard_gate` **لا يثق بحكمٍ مكتوب**:
يعيد حسابَ الصفوف والحكم من الخرائط ومداخل المرشّح نفسِه، ويشترط أن تكون بصمةُ الملفّ
الذي سُمع = `audioSha256` للسورة في المرشّح، وأن تغطّي الخرائطُ المعدّلَ كلَّه والعيّنة.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import sys
from pathlib import Path

TOL_MS = 1500          # أقصى انحرافٍ مقبولٍ لبدء آيةٍ عن موضعها المسموع
MIN_Q = 0.5            # أدنى جودةِ مِرساةٍ يُقاس بها
REPEAT_SIM = 0.7       # أداءٌ آخرُ للآية يُعدّ «تكراراً» بهذا التشابه فأعلى
REPEAT_NEAR_MS = 2000  # … إن بدأ قريباً من البدء المنشور بهذا القدر
TAIL_UNMEASURED = 3    # ذيلٌ من هذا العدد من آياتٍ غيرِ مقيسةٍ متتالية ⇒ ردّ
SAMPLE_K = 4           # سورٌ غيرُ معدّلةٍ تُفحص معها
STATE_PREFIX = "state-heard/"
VERSION = "heard-gate-1"


def state_key(src: str) -> str:
    return STATE_PREFIX + src.replace("/", "_") + ".json"


def by_surah(entries) -> dict:
    """{سورة: {آية: (بدء، نهاية، fileRef)}} للمداخل الحاضرة."""
    out: dict = {}
    for e in entries or []:
        if e.get("startMs") is None:
            continue
        s, a = (int(x) for x in str(e["ayahId"]).split(":"))
        out.setdefault(s, {})[a] = (int(e["startMs"]), e.get("endMs"), e.get("fileRef"))
    return out


def modified_surahs(cand_entries, pub_entries) -> list[int]:
    """سورُ المرشّح التي تخالف المنشورَ في مدخلٍ واحد (‏بدءٌ · نهايةٌ · ملفّ · حضور)."""
    c, p = by_surah(cand_entries), by_surah(pub_entries)
    return sorted(s for s in c if c[s] != p.get(s))


def sample_surahs(cand_sha: str, pool, k: int = SAMPLE_K) -> list[int]:
    """عيّنةٌ حتميّةٌ من `pool` بذرتُها بصمةُ المرشّح — يعيدها كلُّ قارئٍ ولا يختارها الصانع."""
    pool = sorted(set(int(s) for s in pool))
    seed = int(hashlib.sha256(f"{cand_sha}:heard-gate-sample".encode()).hexdigest()[:16], 16)
    return sorted(random.Random(seed).sample(pool, min(k, len(pool))))


PARTIAL_KEY = "windowStartMs"


def partial_map_error(heard) -> str | None:
    """⛔ (‏#105) خريطةٌ سُبرت من نافذةٍ جزئيّة (‏`ctc_heard_map --start-ms`) لم تسمع ما قبل بدئها، فلا تُعدّ خريطةً للملفّ كلِّه."""
    if isinstance(heard, dict) and heard.get(PARTIAL_KEY):
        return (f"خريطةٌ جزئيّةٌ من {heard.get(PARTIAL_KEY)}م.ث (‏{PARTIAL_KEY}) — لم تسمع ما قبلها فلا تدخل حكماً")
    return None


def compact_map(heard: dict) -> dict:
    """ما يلزم الحكمَ من مخرَج `ctc_heard_map` (‏يُحفظ في state ويُعاد منه الحساب).
    ⛔ الخريطةُ الجزئيّة تُردّ هنا، وكلُّ حكمٍ يمرّ من هنا (‏البوّابة · الباب المزدوج · الظلّ · المتنازَع)."""
    why = partial_map_error(heard)
    if why:
        raise ValueError(f"⛔ {why}")
    hm = heard.get("heardMap") or {}
    out = {"surah": heard.get("surah"), "sha256": heard.get("sha256"), "fileRef": heard.get("fileRef"),
           "totalMs": heard.get("totalMs"), "engine": heard.get("engine"),
           "anchors": {k: [v.get("anchorMs"), v.get("anchorQuality"),
                           [o[:3] for o in (v.get("occurrences") or [])]]
                       for k, v in hm.items()}}
    if heard.get("quranModel"):          # خريطةُ نموذج التلاوة (‏الباب الثاني) وحدَها؛ والعامّةُ بلا هذا الحقل حرفاً
        out["quranModel"] = heard["quranModel"]
    return out


def genuine_repeat(start: int, am, o) -> bool:
    """⭐ هل الأداءُ `o` تكرارٌ حقيقيٌّ يبرّر بدءاً منحرفاً عن المِرساة `am=[بدء، نهاية]`؟ (‏تشديد 2026-10-23)
    كان يكفي أيَّ أداءٍ بتشابه ≥0.7 يبدأ ≤2ث من البدء المنشور — فيمرّ مدخلٌ يبدأ وسط آيته أو بعد
    نهايتها لأنّ أداءً جزئيّاً **داخل مدى المِرساة نفسِها** يقع قربه (‏تحقّقٌ مستقلّ: نحو 70٪ من 2120 حالةَ
    بدءٍ متأخّرٍ ≥2.5ث داخل المِرساة معيبةٌ فعلاً: 3:45 · 2:185 · 40:14).
    ⇒ لا يُعدّ تكراراً إلا أداءٌ **منفصلٌ**: يبدأ قبل المِرساة بأكثر من TOL_MS (‏أداءٌ سابق)
    أو عند نهايتها وبعدها (‏`o[0] ≥ am[1] − TOL_MS`)؛ ويُرفض ما بينهما (‏داخل المِرساة، ويشمل
    أداءً يطابق بدءها نفسَه فهو المِرساةُ لا تكرارٌ). ومَدى مِرساةٍ بلا نهايةٍ صالحة يُعامَل كلَّه داخلاً.
    وما ارتدّ بهذا من سليمٍ (‏~30٪) لا يُرخى له شيء: طريقُ قبوله شاهدٌ ثانٍ (‏`ctc_opener_probe`)."""
    try:
        if float(o[2]) < REPEAT_SIM or abs(start - int(o[0])) > REPEAT_NEAR_MS:
            return False
        o0 = int(o[0])
        a0, a1 = int(am[0]), int(am[1])
    except (TypeError, ValueError, IndexError):
        return False
    if a1 <= a0:
        return False
    return o0 < a0 - TOL_MS or o0 >= a1 - TOL_MS


def surah_rows(starts: dict, cmap: dict) -> list[dict]:
    """صفٌّ لكلّ آيةٍ حاضرة: {ayah, startMs, anchorMs, q, devMs, status} — status ∈ ok·dev·repeat·unmeasured."""
    anc = cmap.get("anchors") or {}
    rows = []
    for a in sorted(starts):
        st = int(starts[a])
        rec = anc.get(str(a))
        am, q, occ = (rec + [None, None, []])[:3] if isinstance(rec, list) else (None, None, [])
        if not am or q is None or float(q) < MIN_Q:
            rows.append({"ayah": a, "startMs": st, "anchorMs": am[0] if am else None, "q": q,
                         "devMs": None, "status": "unmeasured"})
            continue
        d = st - int(am[0])
        status = "ok"
        if abs(d) > TOL_MS:
            alt = any(genuine_repeat(st, am, o) for o in occ or [])
            status = "repeat" if alt else "dev"
        rows.append({"ayah": a, "startMs": st, "anchorMs": int(am[0]), "q": q, "devMs": d, "status": status})
    return rows


def surah_verdict(rows: list[dict]) -> str | None:
    """سببُ ردّ السورة أو None."""
    if not rows:
        return "لا آيةَ حاضرة"
    dev = [r for r in rows if r["status"] == "dev"]
    if dev:
        w = max(dev, key=lambda r: abs(r["devMs"]))
        return (f"{len(dev)} آيةً تنحرف عن موضعها المسموع > {TOL_MS / 1000:.1f}ث "
                f"(أقصاها الآية {w['ayah']}: {w['devMs'] / 1000:+.1f}ث) · "
                f"الآيات {','.join(str(r['ayah']) for r in dev[:30])}")
    meas = sum(1 for r in rows if r["status"] != "unmeasured")
    if meas * 2 < len(rows):
        return f"المقيسُ {meas}/{len(rows)} أقلُّ من النصف — ما لم يُحسم لم يُسمع"
    tail = 0
    for r in reversed(rows):
        if r["status"] != "unmeasured":
            break
        tail += 1
    if tail >= TAIL_UNMEASURED:
        return (f"ذيلٌ غيرُ مقيس: آخرُ {tail} آياتٍ حاضرةٍ بلا مِرساةٍ مسموعة "
                f"(من {rows[-tail]['ayah']}) — آياتٌ منشورةٌ قد لا يقابلها صوت")
    return None


WEAK_VERSION = "heard-weak-1"


def weak_touched(cand_s: dict, pub_s, rows: list[dict]) -> list[int]:
    """آياتُ سورةٍ معدّلة مسّها التحويل ومرساتُها غيرُ مقيسة (‏جودة < MIN_Q أو بلا مِرساة) — يلزم كلاً منها شاهد.
    `cand_s`/`pub_s`: {آية: (بدء، نهاية، fileRef)} من `by_surah`؛ وسورةٌ غائبةٌ من المنشور (‏None) ⇒ كلُّ آياتها ممسوسة."""
    pub_s = pub_s or {}
    return sorted(r["ayah"] for r in rows
                  if r["status"] == "unmeasured" and tuple(pub_s.get(r["ayah"]) or ()) != tuple(cand_s.get(r["ayah"]) or ()))


def weak_plan(cand_ends: dict, pub_ends, cmap: dict) -> list[int]:
    """آياتُ الشاهد لقاعدة المِرساة الضعيفة من خريطةٍ قِيست للتوّ (‏يستعملها سيرُ العمل؛ والحكمُ يعيد الحساب).
    `cand_ends`/`pub_ends`: {آية: [بدء، نهاية]} (‏pub_ends=None ⇒ السورةُ غائبةٌ من المنشور)."""
    c = {int(a): tuple(v[:2]) for a, v in cand_ends.items()}
    p = None if pub_ends is None else {int(a): tuple(v[:2]) for a, v in pub_ends.items()}
    rows = surah_rows({a: v[0] for a, v in c.items()}, cmap)
    return weak_touched(c, p, rows)


def weak_verdict(s: int, cand_s: dict, pub_s, rows: list[dict], g_map: dict, wit, want: str, riwaya,
                 ref_words=None, cand_idx=None, sources=None):
    """(سببُ الردّ أو None، دليل) لقاعدة المِرساة الضعيفة في سورةٍ معدّلة. الشاهدُ يُعاد حكمُه هنا ولا يُقرأ حكمٌ مكتوب.
    `cand_idx`/`sources` اختياريّان: بهما يُعرض مطلعُ الحروف المقطّعة على `opener_letters_verdict` للآية الأولى وحدها،
    وبدونهما (‏أو بلا `transform.openerLetters` للسورة) يبقى السلوكُ القديمُ حرفاً."""
    weak = weak_touched(cand_s, pub_s, rows)
    ev = {"version": WEAK_VERSION, "weak": weak, "witnessed": [], "missing": [], "witnessInvalid": None}
    if not weak:
        return None, ev
    res, bad = ({}, "لا شاهدَ Whisper لهذه السورة")
    if wit:
        res, bad = _witness_eval(wit, s, g_map, want, riwaya, {a: v[0] for a, v in cand_s.items()}, weak, ref_words)
    ok = [a for a in weak if (res.get(a) or (False,))[0]]
    miss = [a for a in weak if a not in ok]
    ev.update({"witnessed": ok, "missing": miss, "witnessInvalid": bad,
               "detail": {str(a): (res[a][1] or "")[:200] for a in weak if a in res}})
    opener_why = None
    if 1 in miss and cand_idx is not None and opener_claim(cand_idx, s) is not None:
        good, info = opener_letters_verdict(s, 1, cand_s, pub_s, rows, g_map, want, cand_idx, sources, riwaya)
        if good:
            miss = [a for a in miss if a != 1]
            ev.update({"missing": miss, "openerAccepted": [1], "openerLetters": {"1": info}})
        else:
            opener_why = info
            ev["openerRefused"] = {"1": info}
    if not miss:
        return None, ev
    return (f"{len(miss)} آيةً مسّها التحويل ومرساتُها دون {MIN_Q} بلا شاهد Whisper يشهد لنصّها في موضعها "
            f"(الآيات {','.join(str(a) for a in miss[:30])})" + (f" — {bad}" if bad and not res else "")
            + (f" · مطلعُ الحروف {s}:1 مردود: {opener_why}" if opener_why else "")), ev


# ───────────── مطلعُ الحروف المقطّعة: مِرساةٌ ضعيفةٌ للآية الأولى وحدها (‏قرار القائد 2026-11-10) ─────────────
# ⭐ Whisper لا يفرّغ أسماءَ الحروف («حميم» · «قاسم»)، فآيةٌ أولى هي حروفٌ مقطّعةٌ وحدها تبني حدَّها `pin_heard`
#    بنصّ `opener-letters-1` (‏ويحفظ دليلَه في `transform.openerLetters`) ولا يجد لها هذا الحارسُ شاهداً فيردّ السورة
#    (‏الكردي س40 · المرشّح cd85eecc · التشغيلة 42807865400 · «أوّلُ كلماتِ الآية لا يطابق تفريغَ النافذة»).
#    ⇒ مسارٌ **ضيّقٌ** يقبل الآيةَ الأولى وحدها إذا اجتمعت كلُّها (‏ومنها كلُّ ما يشترطه الباني نفسُه، يُعاد حسابُه من
#    مصدر الشاهدَين لا من المكتوب):
#    ١) السورةُ من `OPENER_LETTER_SURAHS` (‏قائمةٌ مغلقةٌ مسمّاة بـ29 سورة) والآيةُ هي الأولى؛
#    ٢) `transform.openerLetters[س]` بنسخة الباني، وفيه شاهدان لتشغيلتين متمايزتين (‏معرّفان مختلفان بعد توحيد الأرقام)،
#       كلٌّ منهما يُحمَّل من مصدره (‏`disputed_sources`) فيجتاز `check_witness` (‏float32 · نموذجٌ مسموح · بصمةُ الصوت)؛
#    ٣) بصمةُ الشاهدين = `audioSha256[س-1]` للمرشّح (‏وهي `want`)؛
#    ٤) بدءُ الآية الثانية في المرشّح مقيسٌ بـCTC (‏صفٌّ «ok») ويشهد له كلٌّ من الشاهدين في موضعه بقاعدة الباني نفسِها
#       (‏`pin_heard._opener_witness`: W_K كلماتٍ بالثقة وبلا التصاقٍ بطرف النافذة وضمن `W_AGREE_MS` من التثبيت) —
#       فاتّفاقُ الشاهدين هو `W_AGREE_MS` نفسُه (‏300م.ث لكلٍّ من التثبيت) لا أرخى منه؛ والمكتوبُ في الدليل يطابق المحسوبَ حرفاً؛
#    ٥) طرفا الآية الأولى محدودان: بدؤها = min(بدئها المنشور، أبكرِ كلمةٍ مسموعةٍ قبل مطلع الثانية) ولا يسبق الملفَّ (‏0)
#       ولا يبعد عن المنشور أكثر من `OPENER_MAX_EXTEND_MS`، ونهايتُها = بدءُ الثانية، في الملفّ نفسِه؛
#    ٦) مدّتُها بين `OPENER_DUR_MIN_MS` و`OPENER_DUR_MAX_MS`.
#    ⛔ لا يخفّض عتبةً ولا يغيّر مساراً قائماً، ولا يمسّ غيرَ الآية الأولى ولا غيرَ هذه السور.
OPENER_GATE_VERSION = "heard-opener-letters-1"
OPENER_KEY = "openerLetters"
OPENER_LETTER_SURAHS = frozenset({2, 3, 7, 10, 11, 12, 13, 14, 15, 19, 20, 26, 27, 28, 29, 30, 31, 32, 36, 38,
                                  40, 41, 42, 43, 44, 45, 46, 50, 68})
# ⭐ مدّةُ الآية الأولى = بدءُ الثانية − بدؤها المعتمد (‏أبكرُ كلمةٍ مسموعةٌ بعد البسملة). الحدّان من المنشور لا من الذوق:
#    فُحصت مداخلُ الحروف المقطّعة (‏آيتا س40–46 عدا 42: «حم») في 122 فهرساً منشوراً لحفص (‏timings/hafs/*.jz · 2026-11-10 ·
#    728 آيةً بنهايتُها = بدءُ الثانية): الأدنى 98م.ث والمئينُ الخامسُ 1119 (‏الفرقُ: 5٪ من المنشور مبتورة)،
#    وفي النطاق العالي الثقة (‏HIGH، 434) المئينُ الخامس 2193 والأقصى 7410. فالأدنى 1000م.ث (‏دون المئين الخامس لكلّ الفئات:
#    مدٌّ لازمٌ على حرفٍ بنطقٍ سريعٍ لا ينزل دونه) والأقصى 8000م.ث (‏فوق أقصى العالي الثقة) — ومن خرج عنهما رُدّ.
#    وحرصاً على أن لا يُرخى: ما يتجاوز 8000م.ث (‏سورٌ بحروفٍ أكثر كمريم) يُردّ ولا يُقبل، وتُرفع القائمةُ بدليلٍ لا بتوسيعٍ هنا.
OPENER_DUR_MIN_MS = 1000
OPENER_DUR_MAX_MS = 8000
# ⭐ ٧) (‏مراجعة القائد 2026-11-10) القائمةُ بالسورة لا تكفي: في عشرٍ من الـ29 (‏10–15 · 27 · 38 · 50 · 68) آيتُها الأولى عند حفص فيها كلامٌ
#    بعد الحروف («الر تلك آيات…» · «ص والقرآن» · «ن والقلم»). فيُشترط أن تكون السورةُ في `pin_heard.letters_opener_surahs(الرواية)`
#    — الدالّةُ نفسُها التي يبني بها الباني (‏`is_letters_ayah` على نصّ `text_<الرواية>.jz` الخامّ: آيتُها الأولى كلمةٌ واحدةٌ من حروف
#    الفواتح بمدٍّ لازمٍ أو حرفان وحدهما، وثانيتُها ليست حروفاً) — فيتّسق الباني والحارس. ما لم يتحقّق ذلك رُدّ المسار وبقي السلوكُ القديم.
# ⭐ ٨) أبكرُ كلمةٍ مسموعةٍ لا تقع داخل البسملة المسموعة: كان الباني يقصّ عند آخر كلمةٍ **مطابقةٍ تماماً** لكلمات البسملة فقط، فبسملةٌ
#    فرّغها Whisper محرَّفةً («الرحم») تُعدّ حروفاً ويبدأ الحدُّ في وسطها. فكلُّ كلمةٍ تشبه كلمةً من البسملة (‏تشابه ≥ OPENER_BASMALA_SIM)
#    قبل مطلع الثانية يجب أن تنتهي عند بدء الآية الأولى أو قبله، وإلا رُدّ المسار.
OPENER_BASMALA_SIM = 0.75
# ⭐ ٩) (‏قرار القائد 2026-11-10) المسارُ لحفص وحده حتى يوجد نصٌّ بالعدّ المدنيّ: فهارسُ ورش وقالون بعدٍّ كوفيٍّ موحَّد
#    (‏`ayahCounting=KUFI` ونصُّهما 6236 آية)، وصوتُ 2:1 عندهم يمتدّ إلى ما بعد الحروف (‏asali_warsh 4100→11930 · fakhfakh_qalun 8060→16850).
OPENER_RIWAYAT = frozenset({"hafs"})


def opener_claim(cand_idx: dict, s: int):
    """`transform.openerLetters[س]` أو None إن لم يدّعِ المرشّحُ مطلعَ حروفٍ لهذه السورة."""
    tr = cand_idx.get("transform") if isinstance(cand_idx, dict) else None
    ol = tr.get(OPENER_KEY) if isinstance(tr, dict) else None
    ev = ol.get(str(s)) if isinstance(ol, dict) else None
    return ev if isinstance(ev, dict) else None


def _basmala_inside(src, start1, pin2):
    """(كلمة، بدء، نهاية) لأوّل كلمةٍ تشبه كلمةً من البسملة قبل مطلع الثانية وتنتهي بعد `start1`، أو None."""
    import difflib  # noqa: PLC0415
    import pin_heard as PH  # noqa: PLC0415
    for rec in (src.get("ayahs") or {}).values():
        for w in rec.get("words") or []:
            if int(w["s"]) >= int(pin2):
                continue
            for t in disputed_norm_words(str(w.get("w", ""))):
                if any(difflib.SequenceMatcher(None, t, b).ratio() >= OPENER_BASMALA_SIM for b in PH._BASMALA) \
                        and int(w.get("e", w["s"])) > int(start1):
                    return t, int(w["s"]), int(w.get("e", w["s"]))
    return None


def opener_letters_verdict(s, ayah, cand_s, pub_s, rows, g_map, want, cand_idx, sources, riwaya, ref2=None):
    """(True، دليل) إن اجتمعت الشروط ١–٦ أعلاه، وإلا (False، سببُ الردّ بالعربية). الشواهدُ تُحكم من `sources` المحمَّلة لا من المكتوب."""
    import pin_heard as PH  # noqa: PLC0415
    if s not in OPENER_LETTER_SURAHS:
        return False, f"س{s} ليست في قائمة سور الحروف المقطّعة ({len(OPENER_LETTER_SURAHS)} سورة)"
    if ayah != 1:
        return False, f"الآية {ayah} ليست الأولى — المسارُ للآية الأولى وحدها"
    if (riwaya or "hafs") not in OPENER_RIWAYAT:
        return False, f"الرواية {riwaya} ليست في OPENER_RIWAYAT {sorted(OPENER_RIWAYAT)} — المسارُ لحفص وحده"
    try:
        letters = PH.letters_opener_surahs(riwaya or "hafs")
    except (SystemExit, Exception) as e:                      # noqa: BLE001
        return False, f"نصُّ الرواية {riwaya}: {e}"
    if s not in letters:
        return False, (f"الآية {s}:1 في نصّ {riwaya or 'hafs'} ليست حروفاً مقطّعةً وحدها "
                       "(‏فيها كلامٌ بعد الحروف، أو ثانيتُها حروفٌ أيضاً) — ليست في pin_heard.letters_opener_surahs")
    oev = opener_claim(cand_idx, s)
    if oev is None:
        return False, f"لا transform.{OPENER_KEY} للسورة {s}"
    if oev.get("version") != PH.OPENER_VERSION:
        return False, f"نسخةُ الدليل {oev.get('version')} لا {PH.OPENER_VERSION}"
    written = oev.get("witnesses") if isinstance(oev.get("witnesses"), dict) else {}
    ids = {}
    for r in written:
        if not re.fullmatch(r"\d{6,15}", str(r)):
            return False, f"معرّفُ التشغيلة {r!r} ليس رقماً صالحاً"
        ids.setdefault(int(r), str(r))
    if len(ids) != len(written):
        return False, "تشغيلتان بالمعرّف نفسه — يلزم تشغيلتان متمايزتان"
    if len(ids) < PH.OPENER_MIN_WITNESSES:
        return False, f"يلزم {PH.OPENER_MIN_WITNESSES} شاهدان من تشغيلتين متمايزتين (‏وجد {len(ids)})"
    c1, c2 = (cand_s or {}).get(1), (cand_s or {}).get(2)
    if not c1 or not c2:
        return False, "الآيتان الأولى والثانية غيرُ حاضرتين في المرشّح"
    st1, end1, st2 = int(c1[0]), c1[1], int(c2[0])
    row2 = next((r for r in rows if r["ayah"] == 2), None)
    if not row2 or row2["status"] != "ok":
        return False, "بدءُ الآية الثانية غيرُ مقيسٍ بـCTC (‏ليس صفّاً سليماً)"
    try:
        ref2 = ref2 if ref2 is not None else disputed_ref_words(riwaya or "hafs", s, 2)
    except (SystemExit, Exception) as e:                      # noqa: BLE001
        return False, f"نصُّ الآية الثانية: {e}"
    head2 = list(ref2[:min(PH.W_K, len(ref2))])
    got = {}
    for r in sorted(written):
        src = (sources or {}).get(str(r))
        if not isinstance(src, dict) or src.get("error") or not src.get("ayahs"):
            return False, f"الشاهد {r} لم يُحمَّل من مصدره" + (f" ({src.get('error')})" if isinstance(src, dict) and src.get("error") else "")
        try:
            PH.check_witness(src, s, g_map, want)
        except SystemExit as e:
            return False, f"الشاهد {r}: {e}"
        d, why = PH._opener_witness(src, head2, st2)
        if d is None:
            return False, f"الآية الثانية بلا شاهد في موضعها — الشاهد {r}: {why}"
        if _canon(d) != _canon(written[r]):
            return False, f"دليلُ الشاهد {r} المكتوب لا يطابق المحسوبَ من مصدره"
        got[str(r)] = d
    pub1 = (pub_s or {}).get(1)
    if not pub1:
        return False, "لا بدءَ منشورَ للآية الأولى يُقاس به التمديد"
    pub_start = int(pub1[0])
    cands = [pub_start] + [d["earliestMs"] for d in got.values() if d["earliestMs"] is not None]
    new = min(cands)
    if st1 != new:
        return False, f"بدءُ الآية الأولى {st1} ليس أبكرَ بدءٍ مشهود ({new})"
    for r in sorted(written):
        inside = _basmala_inside(sources[str(r)], st1, st2)
        if inside:
            return False, f"بدءُ الآية الأولى {st1} داخل البسملة المسموعة في الشاهد {r} («{inside[0]}» حتى {inside[2]})"
    if st1 < 0:
        return False, f"بدءُ الآية الأولى {st1} قبل بدء الملفّ"
    if pub_start - st1 > PH.OPENER_MAX_EXTEND_MS:
        return False, f"تمديدُ بدء الآية الأولى {pub_start - st1}م.ث (>{PH.OPENER_MAX_EXTEND_MS}م.ث)"
    if end1 is None or int(end1) != st2:
        return False, f"نهايةُ الآية الأولى {end1} ليست بدءَ الثانية {st2}"
    if c1[2] != c2[2]:
        return False, "الآيتان في ملفّين مختلفين"
    dur = st2 - st1                           # ‏سالبةٌ أو ضئيلةٌ إن لم يسبق بدؤها بدءَ الثانية ⇒ يردّها حدُّ الأدنى
    if not OPENER_DUR_MIN_MS <= dur <= OPENER_DUR_MAX_MS:
        return False, f"مدّةُ الآية الأولى {dur}م.ث خارج [{OPENER_DUR_MIN_MS}، {OPENER_DUR_MAX_MS}]"
    for k, want_v in (("startMs", st1), ("ayah2PinMs", st2), ("publishedStartMs", pub_start)):
        if oev.get(k) != want_v:
            return False, f"الدليلُ المكتوب {k}={oev.get(k)} يخالف المحسوب {want_v}"
    return True, {"version": OPENER_GATE_VERSION, "surah": s, "ayah": 1, "startMs": st1, "ayah2StartMs": st2,
                  "durationMs": dur, "publishedStartMs": pub_start, "agreeMs": PH.W_AGREE_MS,
                  "runs": sorted(got), "witnesses": got}


# ───────────── الباب الثاني: مرجعٌ مزدوجٌ (‏قرار القائد 1 · 2026-11-07 · إذنُ المالك 19:22Z) ─────────────
# ⭐ **إضافيٌّ لا بديل ويُغلق عند الشكّ.** للقرّاء المسمَّين في `heard_dual.txt` (‏سطرٌ لكلّ قارئٍ وسورةٍ بقياسه وسببه) وفي
#    **سورةٍ معدّلةٍ** وحدَها: تُحسب خريطتان على الصوت نفسِه (‏العامّةُ G ونموذجُ التلاوة المثبَّتُ R) ويحكم كلٌّ منهما فيما قاسه
#    بالقاعدة نفسِها حرفاً (‏1500م.ث · `genuine_repeat` · جودة 0.5). ومن ليس في القائمة فحكمُه القديمُ حرفاً (‏لا يمرّ بهذا الباب).
#    • آيةٌ تنحرف عند كلِّ خريطةٍ قاستها ⇒ منحرفة (‏لا يحسمها شاهد). • آيةٌ توافق خريطةً وتنحرف عن أخرى ⇒ **متنازَعة**: لا تمرّ إلا بشاهد
#      Whisper حاسمٍ بشروط `pin_heard._whisper_check` نفسِها (‏تطابقُ الطرفين · الثقة · اتّفاقٌ ≤300م.ث مع **البدء المنشور**).
#    • التغطية: مقيسُ العامّة ≥ نصف الآيات ⇒ قاعدةُ النصف كما هي؛ وإلا فيلزم ≥ 90٪ من الحاضر مقيساً بإحدى الخريطتين أو مشهوداً بالشاهد.
#      (‏دليلٌ أكثر لا عتبةٌ أدنى.) والذيلُ (‏3 آيات) غيرُ المقيس بالخريطتين معاً يردّ السورة كما هو ولا يُسدّ بشاهد.
#    • عيّنةُ استقلال: 4 آياتٍ (‏بذرتُها بصمةُ المرشّح) من المقيس بالتلاوة وحدَها تُسمَع بالشاهد؛ **يلزم أن يحسم الشاهدُ كلاً منها**،
#      وخلافُه بأكثر من 1.5ث (‏أو غيابُ شاهدٍ حاسمٍ) يردّ السورة — فالمرشّحُ مُحاذىً بنموذج التلاوة نفسِه فلا يُترك الحكمُ عليه به وحدَه.
#    ⛔ الثوابتُ هنا في الشيفرة لا في البيئة، ولا `--allow`، ولا شيءٌ منها يُخفَّض.
DUAL_VERSION = "heard-dual-1"
DUAL_COVER_PCT = 90          # تغطيةُ سورةٍ عامّتُها دون النصف: ≥ 90٪ بإحدى الخريطتين أو بالشاهد
DUAL_SAMPLE_K = 4            # عيّنةُ الاستقلال من المقيس بالتلاوة وحدها
WIT_PAD_MS = 3000            # حشوُ نافذة الشاهد حول الآية المنشورة (‏نافذةٌ لا عتبة؛ والحكمُ لا يقرأها)
WIT_MAX_WINDOW_MS = 120_000  # سقفُ whisper_witness.parse_windows
DUAL_FILE = Path(__file__).resolve().with_name("heard_dual.txt")


def load_dual(path=None) -> dict:
    """{‏«رواية/قارئ»: {سور}} من `heard_dual.txt`. سطرٌ = `رواية/قارئ سورة | قياسٌ فيه أرقام | سبب`. ملفٌّ معطوبٌ يرفع ValueError."""
    p = Path(path) if path else DUAL_FILE
    out: dict = {}
    if not p.exists():
        return out
    for n, raw in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        ln = raw.strip()
        if not ln or ln.startswith("#"):
            continue
        parts = [x.strip() for x in ln.split("|")]
        m = re.fullmatch(r"([a-z]+)/([A-Za-z0-9_]+)\s+(\d{1,3})", parts[0])
        if not m or len(parts) != 3 or not parts[1] or not parts[2] or not re.search(r"\d", parts[1]) \
                or not 1 <= int(m.group(3)) <= 114:
            raise ValueError(f"{p.name}:{n}: سطرٌ معطوب (‏المطلوب «رواية/قارئ سورة | قياسٌ بأرقام | سبب»): {ln[:80]}")
        key, s = f"{m.group(1)}/{m.group(2)}", int(m.group(3))
        if s in out.get(key, set()):
            raise ValueError(f"{p.name}:{n}: تكرارٌ لـ{key} {s}")
        out.setdefault(key, set()).add(s)
    return out


def dual_surahs(cand_idx: dict, dual: dict | None = None) -> set:
    """سورُ هذا القارئ في القائمة. المفتاحُ من رأس المرشّح نفسِه (‏riwaya/reciterId) لا من حكمٍ مكتوب؛ ورأسٌ بلا مفتاحٍ ⇒ لا شيء."""
    riw, rec = (cand_idx or {}).get("riwaya"), (cand_idx or {}).get("reciterId")
    if not isinstance(riw, str) or not isinstance(rec, str) or not riw or not rec:
        return set()
    return set((load_dual() if dual is None else dual).get(f"{riw}/{rec}", ()))


def pinned_quran_model() -> dict:
    """نسبُ نموذج التلاوة المثبَّت (‏من `quran_ctc_model` نفسِه: مصدرٌ واحد)."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "alignment_v3"))
    import quran_ctc_model as Q  # noqa: PLC0415
    return {"id": Q.MODEL_ID, "revision": Q.REVISION, "weightsSha256": Q.WEIGHTS_SHA256}


def dual_classify(starts: dict, g_map: dict, r_map: dict) -> list[dict]:
    """صفٌّ لكلّ آيةٍ حاضرة بحكم الخريطتين: status ∈ ok · dev · contested · unmeasured (‏قبل الشاهد)."""
    out = []
    for g, r in zip(surah_rows(starts, g_map), surah_rows(starts, r_map)):
        gs, rs = g["status"], r["status"]
        meas = [x for x in (gs, rs) if x != "unmeasured"]
        if not meas:
            st = "unmeasured"
        elif all(x == "dev" for x in meas):
            st = "dev"
        elif any(x == "dev" for x in meas):
            st = "contested"
        else:
            st = "ok"
        dev = r["devMs"] if rs == "dev" else g["devMs"] if gs == "dev" else None
        out.append({"ayah": g["ayah"], "startMs": g["startMs"], "status": st, "gStatus": gs, "rStatus": rs,
                    "gDevMs": g["devMs"], "rDevMs": r["devMs"], "devMs": dev, "gQ": g["q"], "rQ": r["q"]})
    return out


def dual_sample(cand_sha: str, surah: int, pool, k: int = DUAL_SAMPLE_K) -> list[int]:
    """عيّنةُ الاستقلال: حتميّةٌ، بذرتُها بصمةُ المرشّح والسورة — يعيدها كلُّ قارئٍ ولا يختارها الصانع."""
    pool = sorted(set(int(a) for a in pool))
    seed = int(hashlib.sha256(f"{cand_sha}:{surah}:heard-dual-sample".encode()).hexdigest()[:16], 16)
    return sorted(random.Random(seed).sample(pool, min(k, len(pool))))


def dual_needs(rows: list[dict], cand_sha: str, surah: int) -> dict:
    """الآياتُ التي يلزمها شاهدٌ: المتنازَعة · غيرُ المقيسة (‏حين تقصر التغطية) · عيّنةُ الاستقلال."""
    n = len(rows)
    g_meas = sum(1 for r in rows if r["gStatus"] != "unmeasured")
    covered = sum(1 for r in rows if r["status"] != "unmeasured")
    need_cover = g_meas * 2 < n and covered * 100 < DUAL_COVER_PCT * n
    pool = [r["ayah"] for r in rows if r["gStatus"] == "unmeasured" and r["rStatus"] in ("ok", "repeat")]
    return {"contested": [r["ayah"] for r in rows if r["status"] == "contested"],
            "cover": [r["ayah"] for r in rows if r["status"] == "unmeasured"] if need_cover else [],
            "sample": dual_sample(cand_sha, surah, pool)}


def dual_witness_plan(starts: dict, g_map: dict, r_map: dict, cand_sha: str, surah: int) -> list[int]:
    """آياتُ السورة التي يُشغَّل لها شاهدُ Whisper (‏تُحسب من الخريطتين بعد قياسهما — يستعملها سيرُ العمل)."""
    rows = dual_classify(starts, g_map, r_map)
    nd = dual_needs(rows, cand_sha, surah)
    # (2026-11-10) وما لم تقسه خريطةٌ قطّ يلزمه شاهدٌ لقاعدة المِرساة الضعيفة (‏فائضٌ لا يضرّ في غير الممسوس)
    unm = {r["ayah"] for r in rows if r["status"] == "unmeasured"}
    return sorted(set(nd["contested"]) | set(nd["cover"]) | set(nd["sample"]) | unm)


def witness_windows(ends: dict, ayahs) -> str:
    """نوافذُ `whisper_witness --ayahs` (‏آية:بدء-نهاية) من بدء/نهاية المنشور ± الحشو، بسقف 120ث."""
    parts = []
    for a in sorted(ayahs):
        st, en = ends[a]
        lo = max(0, int(st) - WIT_PAD_MS)
        hi = int(en if en is not None else st + 20000) + WIT_PAD_MS
        parts.append(f"{a}:{lo}-{min(hi, lo + WIT_MAX_WINDOW_MS)}")
    return ",".join(parts)


# ───────────── مقارِنُ الشاهد في بوّابة السماع: رسمٌ مسمّى + امتدادُ آخر كلمةٍ مقطوعة (‏قرار القائد 2026-11-10 · nasser 6:72/73) ─────────────
# ⭐ حالةُ nasser_almajed.a70a43a0 س6: 6:72 «وأن أقيموا الصلاة» مسموعةٌ صحيحة، لكنّ المصحف «الصلوه» (‏بعد norm) وWhisper «الصلاه»
#    فسقط التطابقُ الحرفيّ؛ و6:73 قصّت نافذةُ البوّابة آخرَ كلمةٍ فخرجت «الخبي» بينما نافذةٌ أطول أعطتها «الخبير» بثقة 0.99.
# ⛔ قيودُ القائد (‏ملزمةٌ حرفاً): (أ) الرسمُ بقائمةٍ **مغلقةٍ مسمّاةٍ كلمةً كلمة** لا قاعدةٍ عامّة، وفي هذا المقارِن وحدِه
#    (‏لا `common.norm` ولا `pin_heard._whisper_check` ولا مقارِنُ المتنازَع/المرساة)؛ (ب) لا تُمدّ آخرُ كلمةٍ إلا بشروطٍ مجتمعة
#    (‏E1–E5 أدناه)؛ (ج) `fuzzy=False` ثابتٌ. ولا عتبةَ تنخفض ولا ثقةَ تُرخى.
# ⭐ القائمةُ بعد `norm` (‏ة←ه): الكلمةُ الحديثة ⇒ كلمةُ المصحف. وهي كلماتٌ كاملةٌ بعينها (‏بسابقاتها المسمّاة) لا أنماط:
RASM_FORMS = {
    "الصلاه": "الصلوه", "والصلاه": "والصلوه", "بالصلاه": "بالصلوه",
    "الزكاه": "الزكوه", "والزكاه": "والزكوه", "بالزكاه": "بالزكوه",
    "الحياه": "الحيوه", "والحياه": "والحيوه", "بالحياه": "بالحيوه",
    "مشكاه": "مشكوه",
    "النجاه": "النجوه",
    "الغداه": "الغدوه", "بالغداه": "بالغدوه",
    "مناه": "منوه",
    "الربا": "الربوا", "والربا": "والربوا",
}
# ⭐ (2026-11-10 · قرار القائد · على نسق #110) أزواجُ رواية قالون: ما يكتبه Whisper بالإملاء الحديث ⇒ ما في نصّ قالون بعد norm.
#    ⛔ مفتاحٌ بالرواية: لا تسري على غير قالون (‏ولو اشترك الرسمُ مع حفص في الموضع، فلم يُقَس لحفصٍ شاهدٌ بعد).
#    ⛔ قائمةٌ مغلقةٌ كلمةً كلمة؛ كلُّ زوجٍ مقيسٌ من تفريغٍ حقيقيٍّ في المستودع (‏ops/out/1700_hd24_art_10A · art_10B ·
#    ops/evidence/timing-fakhfakh_qalun-5bad920f.json وغيرها) ومثبتٌ بموضعٍ مقروءٍ من `text_qalun.jz`
#    (‏`QALUN_RASM_WITNESS` أدناه، ويتحقّق منه الاختبار آلياً). لا قاعدةَ عامّة (‏لا «احذف كلَّ ألف») ولا مسافةَ تحرير.
RASM_FORMS_BY_RIWAYA = {
    "qalun": {
        "وجاوزنا": "وجوزنا",
        "اسراييل": "اسرايل",
        "الانسان": "الانسن",
        "البلاغ": "البلغ",
        "ارسلناك": "ارسلنك",
        "الكتاب": "الكتب",
        "يغشاهم": "يغشيهم",
        "العاملين": "العملين",
    },
}
# الشاهدُ النصّيّ: كلُّ شكلٍ قالونيٍّ ⇒ (سورة، آية) موجودٌ فيه في `text_qalun.jz` (‏يقرؤه `pin_heard.ref_words_for`).
QALUN_RASM_WITNESS = {
    "وجوزنا": (10, 90), "اسرايل": (10, 90), "الانسن": (42, 48), "البلغ": (42, 48),
    "ارسلنك": (42, 48), "الكتب": (29, 51), "يغشيهم": (29, 55), "العملين": (29, 58),
}


def rasm_forms(riwaya=None) -> dict:
    """القائمةُ الفعّالة لرواية: العامّةُ `RASM_FORMS` + أزواجُ تلك الرواية وحدَها (‏رواية مجهولةٌ أو None ⇒ العامّة فقط)."""
    return {**RASM_FORMS, **RASM_FORMS_BY_RIWAYA.get(riwaya or "", {})}


EXT_EDGE_MS = 100         # E2: آخرُ كلمةٍ ملاصقةٌ لحدّ النافذة (‏نهايتُها ≥ حدّ النافذة − هذا)
EXT_CAP_MS = 1000         # E3: سقفُ الامتداد وراء حدّ النافذة
EXT_SAME_START_MS = 150   # الكلمةُ الممتدّةُ هي نفسُها المقطوعة: بدؤها قريبٌ من بدء المقطوعة


def _ncommon(text: str) -> list[str]:
    import pin_heard as PH  # noqa: PLC0415
    sys.path.insert(0, str(PH._REPO_ROOT / "tools" / "alignment"))
    from common import norm  # noqa: PLC0415
    return norm(str(text)).split()


def rasm_unify_ref(ref, riwaya=None):
    """كلماتُ المرجع (‏المطبَّعة) بعد توحيد الرسم المسمّى؛ كلمةٌ خارج القائمة تبقى حرفاً."""
    forms = rasm_forms(riwaya)
    return None if ref is None else [forms.get(w, w) for w in ref]


def rasm_unify_wit(wit, riwaya=None):
    """نسخةٌ من الشاهد تُوحَّد فيها كلماتُ التفريغ المسمّاةُ بتمامها في `RASM_FORMS` (‏الكلمةُ الواحدةُ بعد norm فقط)."""
    forms = rasm_forms(riwaya)
    out = dict(wit)
    out["ayahs"] = {}
    for a, rec in ((wit or {}).get("ayahs") or {}).items():
        r2 = dict(rec)
        ws = []
        for w in rec.get("words") or []:
            toks = _ncommon(w.get("w", ""))
            if len(toks) == 1 and toks[0] in forms:                                       # [شرط R1: الكلمةُ كلُّها في القائمة]
                w = dict(w, w=forms[toks[0]])
            ws.append(w)
        r2["words"] = ws
        out["ayahs"][a] = r2
    return out


def _wtok1(w, riwaya=None):
    t = _ncommon(w.get("w", ""))
    return rasm_forms(riwaya).get(t[0], t[0]) if len(t) == 1 else None


def extend_cut_last_word(wit, ayah, ref, riwaya=None):
    """يُرجع كلماتِ نافذة الآية، وقد استُبدلت آخرُ كلمةٍ مقطوعةٌ بقراءتها التامّة من نافذةٍ أطول لآيةٍ أخرى في **الشاهد نفسِه**
    (‏صلاحيتُه فُحصت: البصمةُ والملفُّ والنموذج) — بشروطٍ مجتمعة، وإلا تُرجَع الكلماتُ كما هي:
      E1 آخرُ كلمةٍ مفرَّغةٍ بادئةٌ حرفيّةٌ **أقصرُ** من الكلمة المرجعيّة الأخيرة المنتظرة؛
      E2 ملاصقةٌ لحدّ النافذة (‏نهايتُها ≥ الحدّ − EXT_EDGE_MS)؛
      E3 والقراءةُ الأطولُ تنتهي في سقف الامتداد (‏≤ الحدّ + EXT_CAP_MS)، وبدؤها كبدء المقطوعة (‏EXT_SAME_START_MS)؛
      E4 وتطابق الكلمةَ المرجعيّة **مطابقةً حرفيّةً كاملة** (‏لا تشابهَ ولا fuzzy)؛
      E5 وثقتُها ≥ W_MIN_WORD_P (‏وما بعده من عتبة المتوسّط يفحصه `_whisper_check` على الطرف كما هو)."""
    import pin_heard as PH  # noqa: PLC0415
    rec = ((wit or {}).get("ayahs") or {}).get(str(ayah)) or {}
    words = list(rec.get("words") or [])
    win = rec.get("windowMs")
    if not words or not ref or not win or len(win) < 2:
        return words
    last, want = words[-1], ref[-1]
    t = _wtok1(last, riwaya)
    if not t or not want.startswith(t) or len(t) >= len(want):                               # [شرط E1: بادئةٌ حرفيّةٌ أقصر]
        return words
    if int(last["e"]) < int(win[1]) - EXT_EDGE_MS:                                            # [شرط E2: ملاصقةٌ للحدّ]
        return words
    for k, other in ((wit or {}).get("ayahs") or {}).items():
        ow = other.get("windowMs") or []
        if k == str(ayah) or len(ow) < 2 or int(ow[1]) <= int(win[1]):
            continue
        for cand in other.get("words") or []:
            if abs(int(cand["s"]) - int(last["s"])) > EXT_SAME_START_MS:
                continue
            if int(cand.get("e", cand["s"])) > int(win[1]) + EXT_CAP_MS:                      # [شرط E3: سقفُ ثانية]
                continue
            if _wtok1(cand, riwaya) != want:                                                           # [شرط E4: مطابقةٌ كاملة]
                continue
            if float(cand["p"]) < PH.W_MIN_WORD_P:                                             # [شرط E5: الثقةُ نفسُها]
                continue
            return words[:-1] + [dict(cand)]
    return words


def _witness_eval(wit, surah, g_map, want_sha, riwaya, starts, ayahs, ref_words=None):
    """{آية: (حاسمٌ؟, تفصيل)} بشروط `pin_heard._whisper_check` نفسِها، والبدءُ المقابَل هو **البدءُ المنشور**. الشاهدُ غيرُ الصالح ⇒ لا شيء.
    قبل المقابلة: توحيدُ الرسم المسمّى (‏`RASM_FORMS`) وامتدادُ آخرِ كلمةٍ مقطوعةٍ (‏`extend_cut_last_word`) — وfuzzy=False دائماً."""
    import pin_heard as PH  # noqa: PLC0415  (‏استيرادٌ كسول: pin_heard نفسُه يستورد هذا الملفّ)
    try:
        PH.check_witness(wit, surah, g_map, want_sha)
    except SystemExit as e:
        return {}, str(e)
    ref_words = ref_words or PH.ref_words_for
    wit_u = rasm_unify_wit(wit, riwaya)
    res = {}
    for a in ayahs:
        if str(a) not in ((wit or {}).get("ayahs") or {}):
            res[a] = (False, "لا تفريغَ لهذه الآية في الشاهد")
            continue
        try:
            ref = rasm_unify_ref(ref_words(riwaya, surah, a), riwaya)
        except (SystemExit, Exception):                    # noqa: BLE001
            ref = None
        w_a = wit_u
        ext = extend_cut_last_word(wit_u, a, ref, riwaya)
        if ext != (wit_u["ayahs"][str(a)].get("words") or []):
            w_a = dict(wit_u, ayahs=dict(wit_u["ayahs"], **{str(a): dict(wit_u["ayahs"][str(a)], words=ext)}))
        hm = {"heardMap": {str(a): {"anchorMs": [int(starts[a]), int(starts[a]) + 1]}}}
        c, info = PH._whisper_check(w_a, hm, surah, a, ref, fuzzy=False)
        res[a] = (c is not None, info)
    return res, None


def dual_surah(s: int, cs_s: dict, g_map: dict, r_map, wit, want: str, cand_sha: str, riwaya, ref_words=None):
    """حكمُ سورةٍ في القائمة: (سببُ الردّ أو None، دليل {rows, evidence})."""
    pinned = pinned_quran_model()
    ev = {"version": DUAL_VERSION, "model": pinned}
    if not isinstance(r_map, dict) or not r_map:
        return "لا خريطةَ سماعٍ بنموذج التلاوة (R) — الباب المزدوج يلزمه الاثنتان", {"rows": [], "evidence": ev}
    if r_map.get("sha256") != want:
        return (f"خريطةُ التلاوة على صوتٍ آخر ({str(r_map.get('sha256'))[:8]}) لا صوتِ المرشّح ({str(want)[:8]})",
                {"rows": [], "evidence": ev})
    if r_map.get("fileRef") != g_map.get("fileRef"):
        return "خريطتا السماع من ملفَّين مختلفَين", {"rows": [], "evidence": ev}
    if g_map.get("quranModel"):
        return "الخريطةُ العامّة تحمل نسبَ نموذج التلاوة — مرجعان مختلطان", {"rows": [], "evidence": ev}
    got = r_map.get("quranModel") or {}
    if {k: got.get(k) for k in pinned} != pinned:
        return "خريطةُ التلاوة بلا نسبِ النموذج المثبَّت (‏المعرّف والمراجعة وبصمةُ الأوزان)", {"rows": [], "evidence": ev}
    starts = {a: v[0] for a, v in cs_s.items()}
    ends = {a: (v[0], v[1]) for a, v in cs_s.items()}
    rows = dual_classify(starts, g_map, r_map)
    nd = dual_needs(rows, cand_sha, s)
    unm = {r["ayah"] for r in rows if r["status"] == "unmeasured"}
    asked = sorted(set(nd["contested"]) | set(nd["cover"]) | set(nd["sample"]) | unm)
    res, bad_wit = ({}, None)
    if asked and wit:
        res, bad_wit = _witness_eval(wit, s, g_map, want, riwaya, starts, asked, ref_words)
    ok_wit = {a for a, (c, _i) in res.items() if c}
    n = len(rows)
    g_meas = sum(1 for r in rows if r["gStatus"] != "unmeasured")
    r_meas = sum(1 for r in rows if r["rStatus"] != "unmeasured")
    resolved = []
    for r in rows:
        a = r["ayah"]
        if r["status"] == "contested":
            if a in ok_wit:
                r["status"], r["witness"] = "ok", res[a][1]
                resolved.append(a)
            else:
                r["status"], r["contested"] = "dev", True
        elif r["status"] == "unmeasured" and a in ok_wit:
            # ما في `cover` يسدّ التغطية؛ وما سواه لا يُحتاج للتغطية (‏العامّةُ بلغت النصف) فلا يغيّر حكمَها،
            # ويُسجَّل شاهدُه لقاعدة المِرساة الضعيفة وحدها.
            r["status"], r["witness"] = "witness", res[a][1]
    covered = sum(1 for r in rows if r["status"] != "unmeasured")
    ev.update({"n": n, "gMeasured": g_meas, "rMeasured": r_meas, "covered": covered,
               "contested": nd["contested"], "contestedResolved": resolved,
               "coverWitnessed": [r["ayah"] for r in rows if r["status"] == "witness" and r["ayah"] in nd["cover"]],
               "weakWitnessed": [r["ayah"] for r in rows if r["status"] == "witness" and r["ayah"] not in nd["cover"]],
               "sample": nd["sample"], "sampleOk": [a for a in nd["sample"] if a in ok_wit],
               "witness": {str(a): res[a][1][:200] for a in sorted(res) if a in set(resolved) | set(nd["sample"]) | set(nd["cover"]) | unm},
               "witnessModel": (wit or {}).get("model"), "witnessInvalid": bad_wit, "engine": r_map.get("engine")})
    out = {"rows": rows, "evidence": ev}
    dev = [r for r in rows if r["status"] == "dev"]
    if dev:
        w = max(dev, key=lambda r: abs(r["devMs"] if r["devMs"] is not None else 0))
        nc = sum(1 for r in dev if r.get("contested"))
        return (f"{len(dev)} آيةً تنحرف عن موضعها المسموع > {TOL_MS / 1000:.1f}ث "
                f"(أقصاها الآية {w['ayah']}: {(w['devMs'] or 0) / 1000:+.1f}ث"
                + (f" · منها {nc} متنازَعةٌ بين الخريطتين بلا شاهدٍ حاسم" if nc else "") + ") · "
                f"الآيات {','.join(str(r['ayah']) for r in dev[:30])}"), out
    if g_meas * 2 < n and covered * 100 < DUAL_COVER_PCT * n:
        return (f"التغطيةُ {covered}/{n} دون {DUAL_COVER_PCT}٪ والعامّةُ تقيس {g_meas}/{n} دون النصف — "
                "ما نقص يُستكمل بشاهدٍ لآياتٍ بعينها لا بخفض النسبة"), out
    tail = 0
    for r in reversed(rows):
        if r["gStatus"] != "unmeasured" or r["rStatus"] != "unmeasured":
            break
        tail += 1
    if tail >= TAIL_UNMEASURED:
        return (f"ذيلٌ غيرُ مقيسٍ بالخريطتين معاً: آخرُ {tail} آياتٍ حاضرةٍ بلا مِرساةٍ مسموعة "
                f"(من {rows[-tail]['ayah']}) — آياتٌ منشورةٌ قد لا يقابلها صوت"), out
    miss = [a for a in nd["sample"] if a not in ok_wit]
    if miss:
        return ("عيّنةُ الاستقلال لم يحسمها الشاهد في الآيات " + ",".join(str(a) for a in miss)
                + (f" ({bad_wit})" if bad_wit else "") + " — مقيسةٌ بنموذج التلاوة وحدَه"), out
    return None, out


# ───────────── المرساةُ المتنازَعُ عليها (‏قرار القائد 2026-11-10 · سندُه موافقةُ المالك 11-07 على المرجع المزدوج) ─────────────
# ⭐ «التنازعُ لا يمرّ إلا بشاهد Whisper، ولا عتبةَ تنخفض». مرساةٌ قويّةٌ (‏جودة ≥ MIN_Q) قد تقع في **آيةٍ أخرى**
#    (‏3siri 10:50 · 10:55 · 10:70 · 9:82 · 9:93: المرساةُ في ذيل السابقة والمنشورُ على مطلع الآية نفسِها)، فتردّ البوّابةُ
#    منشوراً صحيحاً — وتثبيتُه على المرساة تحريف. فآيةٌ «منحرفة» (‏dev) تُعدّ «متنازَعاً عليها» لا تردّ **بشروطٍ مجتمعة**:
#    ١) شاهدان على الأقلّ من تشغيلتين متمايزتين، بصمةُ كلٍّ = بصمةُ المرشّح للسورة = بصمةُ الخريطة، والملفُّ نفسُه، float32؛
#    ٢) كلُّ شاهدٍ يضع أوّلَ W_K كلماتٍ من الآية (‏نصّ المصحف) متّصلةً، وبدءُ أولاها ضمن 300م.ث من **البدء المنشور**،
#       بثقة `pin_heard` (‏كلُّ كلمةٍ ≥ W_MIN_WORD_P والمتوسّط ≥ W_MEAN_WORD_P)، ولا كلمةَ منها ملصوقةٌ بطرف النافذة؛
#    ٣) كلُّ شاهدٍ يسمع **عند المرساة** نصَّ آيةٍ أخرى مسمّاةٍ بعينها: W_K كلماتٍ متّصلةً منها كلمةً بكلمة تغطّي زمنَ
#       المرساة، بالثقة نفسِها وبلا التصاقٍ بطرف النافذة، وليست هذه الكلماتُ نصّاً من الآية نفسِها (‏فالتكرارُ لا يُعدّ تنازعاً)؛
#    ٤) المتنازَعُ عليه في السورة ≤ 10٪ من آياتها، وإلا رُدّت السورةُ كلُّها؛
#    ٥) الدليلُ (‏الشاهدان بكلماتهما) مكتوبٌ في `transform.disputedAnchors` ويُعاد حسابُه هنا ولا يُقرأ حكمٌ مكتوب (‏وانظر ٦)؛
#    وأيُّ ادّعاءٍ مكتوبٍ لا يستوفي الشروط يردّ السورة (‏لا يُترك صامتاً).
# ⭐ (‏قرار القائد 2026-11-11 · سندُه موافقةُ المالك 11-07) تدقيقٌ لمطابقة الكلمات **داخل هذا المسار وحدَه**، لا عتبةَ فيه
#    (‏حالتا nufais 20:106 وa_abdl 23:22). ⛔ حدُّ المطلع يبقى `W_AGREE_MS` (300م.ث) كما هو؛ وما يبعد منشورُه عن شاهدَيه المتّفقَين
#    أكثرَ من ذلك يُثبَّت بدؤه على مطلعهما بمسار التثبيت القائم لا بتوسيع الحدّ. وهو تعديلٌ على الشرطين ٢ و٣ لا على غيرهما:
#    ٢ب) المطلعُ يُثبَت بكلمات الآية نفسِها: أوّلُ W_K كلماتٍ متتاليةً، أو الآيةُ كلُّها إن قصرت عن W_K.
#    ٣أ) ما يُسمع عند المرساة: نافذةٌ **كلُّها** من كلمات الآية الأخرى متتاليةً (‏W_K كلماتٍ، أو الآيةُ الأخرى كلُّها إن قصرت)
#        تغطّي زمنَ المرساة ولا تعبر حدَّ تلك الآية؛ فنافذةٌ فيها كلمةٌ من غيرها لا تُحسب (‏وتُجرَّب كلُّ النوافذ المغطّية).
#    ٣ب) تطبيعٌ لصيغتَي وقفٍ مسمّاتين **وعلى آخر كلمةٍ من الآية وحدَها** في مطلعها: (‏١) التنوينُ المنصوب يُقرأ ألفاً (‏الكلمةُ
#        المكتوبةُ بفتحتين ولا ألفَ في رسمها المطبَّع، وتُسمع بألفٍ زائدة)، (‏٢) هاءُ السكت (‏هاءٌ زائدةٌ في آخر الكلمة المسموعة).
#        ولا تطبيعَ لكلمةٍ أخرى ولا لصيغةٍ أخرى (‏20:106: «قاع» وسطَ الآية ليست آخرَ كلمةٍ فتبقى مردودةً — وهو الصواب).
#    ولا قاعدةَ خاصّةً للتكرار، ولا تتغيّر عتبةٌ، ولا يُرخى مسارٌ قائم. والإصدارُ `DISPUTED_VERSION` لم يُرفع
#    فلا يكسر الأدلّةَ المكتوبةَ القائمة (‏حقولُ الدليل نفسُها).
DISPUTED_VERSION = "heard-disputed-1"
DISPUTED_MAX_PCT = 10
DISPUTED_MIN_WITNESSES = 2
_FATHATAN = ("\u064b", "\u08f0", "\u08e4")   # فتحتان (‏عاديّتان ومفتوحتان) في الرسم العثمانيّ
# ⛔ ٦) (‏قرار القائد 2026-11-10 · ثغرةٌ سُدّت قبل الدمج) الشاهدُ المكتوبُ في المرشّح **لا يُصدَّق وحده**: من يبني المرشّح
#    يقدر أن يكتب كلماتٍ لم تُسمع وينسبها إلى تشغيلتين لا وجود لهما. فتُحمَّل الشواهدُ بمعرّفات تشغيلاتها من مصدرها
#    (‏`pin_heard.load_witness`: تشغيلةٌ ناجحةٌ لـ`whisper_witness.yml` على main ومخرَجُها المسمّى باسمها) في خطوة الحكم،
#    وتُحفظ في `state-heard` (‏`disputedSource`) فيعيد `gate_error` الحكمَ منها؛ والمكتوبُ يجب أن يطابق المحمَّلَ **حرفاً**
#    في حقول `DISPUTED_SRC_KEYS`، وإلا رُدّت السورة. ويُحكم بالمحمَّل لا بالمكتوب.
DISPUTED_SRC_KEYS = ("surah", "riwaya", "fileRef", "sha256", "model", "computeType", "ayahs")


def disputed_src_rec(w):
    return {k: w.get(k) for k in DISPUTED_SRC_KEYS} if isinstance(w, dict) else None


def _canon(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def disputed_sources(cand_idx, loader=None):
    """{سورة: {تشغيلة: سجلُّ الشاهد من مصدره أو {"error": سبب}}} لكلّ تشغيلةٍ مسمّاةٍ في `transform.disputedAnchors`.
    `loader(run, surah)` للاختبار؛ وإلا `pin_heard.load_witness` (‏GitHub). خطأُ التحميل يُكتب ولا يُبتلع: يردّ السورةَ في الحكم."""
    tr = cand_idx.get("transform") if isinstance(cand_idx.get("transform"), dict) else {}
    # ⭐ (‏#107) تشغيلاتُ قاعدة «المرساة المزاحة داخل نصّ الآية» (‏`ownTextAnchors`) تُحمَّل من المصدر نفسِه وبالطريقة نفسِها.
    per = {}
    for key in ("disputedAnchors", OWNTEXT_KEY, WITNESSED_KEY):
        da = tr.get(key)
        if not isinstance(da, dict):
            continue
        for s, claims in da.items():
            for c in (claims.values() if isinstance(claims, dict) else []):
                if isinstance(c, dict) and isinstance(c.get("witnesses"), dict):
                    per.setdefault(str(s), set()).update(str(r) for r in c["witnesses"])
    # ⭐ مطلعُ الحروف المقطّعة (‏`openerLetters[س].witnesses` = {تشغيلة: تفصيل}) يُحمَّل شاهداه من المصدر نفسِه وبالطريقة نفسِها.
    ol = tr.get(OPENER_KEY)
    for s, ev in (ol.items() if isinstance(ol, dict) else []):
        if isinstance(ev, dict) and isinstance(ev.get("witnesses"), dict):
            per.setdefault(str(s), set()).update(str(r) for r in ev["witnesses"])
    if not per:
        return {}
    if loader is None:
        import pin_heard as PH  # noqa: PLC0415
        loader = PH.load_witness
    out = {}
    for s, runs in sorted(per.items()):
        for r in sorted(runs):
            try:
                out.setdefault(str(s), {})[r] = disputed_src_rec(loader(r, int(s)))
            except (SystemExit, Exception) as e:                     # noqa: BLE001
                out.setdefault(str(s), {})[r] = {"error": str(e)[:300]}
    return out


# ⭐ تطبيعٌ إملائيٌّ ضيّق (‏قرار القائد 2026-11-10) **لمقارِن هذا الباب وحده** لا لـ`common.norm`: كان `norm` يحذف الألفَ
#    الخنجريّة والهمزةَ المفردة، فـ«أرأيتم» (‏Whisper) تصير ارايتم و«أرءيتم» (‏المصحف) اريتم، و«متاع»/«متٰع» متاع/متع.
#    ثلاثةُ تحويلاتٍ لا غير، تُطبَّق على الطرفين **قبل** `norm`، حرفاً بحرف (‏لا يتغيّر عددُ الكلمات): ٰ ← ا · ء ← ا · ٱ ← ا.
#    ولا تُحذف بها حروف، فألفٌ حقيقيّةٌ غائبةٌ لا تُصنع (‏قال ≠ قل · مالك ≠ ملك · كتاب ≠ كتب).
_DISPUTED_ORTHO = str.maketrans({"\u0670": "\u0627", "\u0621": "\u0627", "\u0671": "\u0627"})
# ⭐ (‏قرار القائد 2026-11-10 · #104) «ءا» في المصحف (‏«ءَايَٰتُ» · «ءَامَنُوا۟») هي «آ» عند Whisper، فتصير بالتحويل ألفين
#    («اايات» ≠ «ايات»). فتُدمج ألفان متتاليتان **إذا نتجت إحداهما على الأقلّ عن أحد التحويلات الثلاثة**، والألفُ الأصليّةُ
#    المكرّرة لا تُمسّ. يُعلَّم الناتجُ من التحويل بحرفٍ حارسٍ (‏ػ U+063B: داخل مدى `norm` ولا يقع في نصٍّ قرآنيّ)،
#    ثمّ `norm`، ثمّ الدمجُ، ثمّ يعود الحارسُ ألفاً.
_ORTHO_MARK = "\u063b"
_DISPUTED_MARK = str.maketrans({"\u0670": _ORTHO_MARK, "\u0621": _ORTHO_MARK, "\u0671": _ORTHO_MARK})
_MARK_MERGE = re.compile(f"{_ORTHO_MARK}(?=[\u0627{_ORTHO_MARK}])|(?<=\u0627){_ORTHO_MARK}")


def disputed_norm_words(text: str) -> list[str]:
    """كلماتُ نصٍّ خامٍ بتطبيع هذا الباب: التحويلاتُ الثلاثة ثمّ `common.norm` كما هو."""
    import pin_heard as PH  # noqa: PLC0415
    sys.path.insert(0, str(PH._REPO_ROOT / "tools" / "alignment"))
    from common import norm  # noqa: PLC0415
    t = norm(str(text).replace(_ORTHO_MARK, "").translate(_DISPUTED_MARK))
    return _MARK_MERGE.sub("", t).replace(_ORTHO_MARK, "\u0627").split()


def disputed_ref_words(riwaya, surah, ayah):
    """نصُّ الآية من المصحف الموثَّق في المستودع بتطبيع هذا الباب (‏لا من التفريغ)."""
    import pin_heard as PH  # noqa: PLC0415
    sys.path.insert(0, str(PH._REPO_ROOT / "tools" / "alignment"))
    from common import load_index, load_text, surah_slice  # noqa: PLC0415
    start, _end, info = surah_slice(load_index(), surah)
    if not 1 <= ayah <= int(info["ayahs"]):
        raise SystemExit(f"⛔ {surah}:{ayah} خارج السورة")
    return disputed_norm_words(load_text(riwaya or "hafs")[start + ayah - 1])


def _wtoks(rec):
    """كلماتُ نافذة الشاهد بتطبيع هذا الباب [(رمز، بدء، نهاية، ثقة)] بترتيبها؛ الكلمةُ التي تتشظّى ترثها ثقتُها وزمنُها."""
    out = []
    for w in (rec or {}).get("words") or []:
        for t in disputed_norm_words(w.get("w", "")):
            out.append((t, int(w["s"]), int(w.get("e", w["s"])), float(w["p"])))
    return out


def _span_ok(span, win):
    import pin_heard as PH  # noqa: PLC0415
    low = min(x[3] for x in span)
    mean = sum(x[3] for x in span) / len(span)
    if low < PH.W_MIN_WORD_P or mean < PH.W_MEAN_WORD_P:
        return f"ثقةٌ دون العتبة (أدناها {low:.2f}، متوسّطُها {mean:.2f})"
    if win and win[0] is not None and any(x[1] <= int(win[0]) for x in span):
        return f"كلمةٌ ملصوقةٌ ببدء النافذة {win[0]}"
    if win and len(win) > 1 and win[1] is not None and any(x[2] >= int(win[1]) for x in span):
        return f"كلمةٌ ملصوقةٌ بنهاية النافذة {win[1]}"
    return None


def disputed_raw_last(riwaya, surah, ayah):
    """آخرُ كلمةٍ من الآية **خامّاً** (‏بتشكيلها) من المصحف الموثَّق — لمعرفة أنّ تنوينَها نصبٌ؛ لا تُحكم بها إلا صيغتا الوقف."""
    import pin_heard as PH  # noqa: PLC0415
    sys.path.insert(0, str(PH._REPO_ROOT / "tools" / "alignment"))
    from common import load_index, load_text, surah_slice  # noqa: PLC0415
    start, _end, info = surah_slice(load_index(), surah)
    if not 1 <= ayah <= int(info["ayahs"]):
        raise SystemExit(f"⛔ {surah}:{ayah} خارج السورة")
    return str(load_text(riwaya or "hafs")[start + ayah - 1]).split()[-1]


def _stop_equal(h, w, raw_last):
    """هل الكلمةُ المسموعة h هي آخرُ كلمةٍ من الآية w (‏مطبَّعةً) بإحدى صيغتَي الوقف المسمّاتين وحدَهما؟
    (‏١) التنوينُ المنصوب يُقرأ ألفاً: الرسمُ المكتوبُ بفتحتين بلا ألفٍ في آخره وتُسمع بألفٍ زائدة.
    (‏٢) هاءُ السكت: هاءٌ زائدةٌ في آخر الكلمة المسموعة. ولا ثالثةَ."""
    if h == w:
        return True
    if h == w + "\u0647":                                                   # هاء السكت
        return True
    if raw_last and any(f in raw_last for f in _FATHATAN) and not w.endswith("\u0627") and h == w + "\u0627":
        return True                                                         # التنوين المنصوب ألفاً
    return False


def _head_equal(words, own, whole, raw_last):
    """مطابقةُ نافذةٍ مسموعةٍ لمطلع الآية كلمةً بكلمة؛ والتطبيعُ لآخر كلمةٍ من الآية وحدَها (‏حين تكون النافذةُ الآيةَ كلَّها)."""
    if len(words) != len(own):
        return False
    if not whole:
        return words == own
    return words[:-1] == own[:-1] and _stop_equal(words[-1], own[-1], raw_last)


def _in_other(words, oth):
    """النافذةُ كلُّها متتاليةً من كلمات الآية الأخرى وحدَها (‏لا تعبر حدَّها إلى غيرها)."""
    n = len(words)
    return any(words == oth[j:j + n] for j in range(len(oth) - n + 1))


def disputed_raw_last_safe(riwaya, surah, ayah):
    """كـ`disputed_raw_last` وبلا تعثّرٍ إن غاب المصحفُ (‏لا صيغةَ تنوينٍ حينئذٍ: الأضيقُ)."""
    try:
        return disputed_raw_last(riwaya, surah, ayah)
    except (SystemExit, Exception):  # noqa: BLE001
        return None


def disputed_one(wit, surah, ayah, start, anchor, other, ref_words, g_map, want_sha, raw_last=None):
    """(None، تفصيل) إن أثبت الشاهدُ الواحد الشرطين ٢ و٣ للآية، وإلا (سببُ الردّ، None).
    `raw_last`: آخرُ كلمةٍ من الآية خامّاً لصيغة التنوين."""
    import pin_heard as PH  # noqa: PLC0415
    try:
        PH.check_witness(wit, surah, g_map, want_sha)
    except SystemExit as e:
        return str(e), None
    own, oth = ref_words(surah, ayah), ref_words(surah, other)
    k = PH.W_K
    if not own or not oth:
        return "نصُّ الآية أو الآية الأخرى فارغ", None
    kh, ko = min(k, len(own)), min(k, len(oth))      # ثلاثٌ على الأقلّ، أو الآيةُ كلُّها إن قصرت
    tol = PH.W_AGREE_MS
    own_grams = {tuple(own[i:i + ko]) for i in range(len(own) - ko + 1)}
    head = why2 = why3 = None
    hit3 = None
    for rec in (wit.get("ayahs") or {}).values():
        win = rec.get("windowMs") or [None, None]
        tk = _wtoks(rec)
        for i in range(len(tk) - kh + 1):
            span = tk[i:i + kh]
            if head is None and _head_equal([x[0] for x in span], own[:kh], kh == len(own), raw_last):
                if abs(span[0][1] - int(start)) > tol:
                    why2 = f"مطلعُ الآية عند {span[0][1]} بعيدٌ عن المنشور {start} (>{tol}م.ث)"
                else:
                    bad = _span_ok(span, win)
                    if bad:
                        why2 = f"مطلعُ الآية: {bad}"
                    else:
                        head = span[0][1]
        for i in range(len(tk) - ko + 1):
            span = tk[i:i + ko]
            words = [x[0] for x in span]
            if hit3 is None and span[0][1] <= int(anchor) < span[-1][2]:
                if tuple(words) in own_grams:
                    why3 = "ما سُمع عند المرساة من نصّ الآية نفسِها (‏تكرارٌ لا تنازع)"
                elif not _in_other(words, oth):
                    why3 = why3 or f"ما سُمع عند المرساة «{' '.join(words)}» ليس من نصّ {surah}:{other}"
                else:
                    bad = _span_ok(span, win)
                    if bad:
                        why3 = f"عند المرساة: {bad}"
                    else:
                        hit3 = (span[0][1], " ".join(words))
    if head is None:
        return why2 or "لا يُسمع مطلعُ الآية كلمةً بكلمة", None
    if hit3 is None:
        return why3 or f"لا يُسمع عند المرساة {anchor} نصُّ {surah}:{other}", None
    return None, {"headMs": head, "anchorText": hit3[1], "anchorSpanMs": hit3[0]}


def disputed_verdict(s, rows, g_map, want, cand_idx, ref_words=None, n_ayahs=None, sources=None, raw_last=None):
    """يُحوّل كلَّ صفٍّ «dev» مدّعىً في `transform.disputedAnchors[س]` ومُثبَتٍ بالشروط إلى «disputed».
    يُرجع (سببُ ردّ السورة أو None، الدليل). بلا ادّعاءٍ للسورة لا يتغيّر شيءٌ حرفاً."""
    tr = cand_idx.get("transform") if isinstance(cand_idx.get("transform"), dict) else {}
    claims = ((tr.get("disputedAnchors") or {}).get(str(s))) if isinstance(tr.get("disputedAnchors"), dict) else None
    if not claims:
        return None, None
    import pin_heard as PH  # noqa: PLC0415
    ref_words = ref_words or (lambda ss, a: disputed_ref_words(cand_idx.get("riwaya") or "hafs", ss, a))
    raw_last = raw_last or (lambda ss, a: disputed_raw_last_safe(cand_idx.get("riwaya") or "hafs", ss, a))
    byayah = {r["ayah"]: r for r in rows}
    ev = {"version": DISPUTED_VERSION, "accepted": {}, "refused": {}}
    bad = []
    for a_s, c in sorted(claims.items(), key=lambda kv: int(kv[0])):
        a = int(a_s)
        r = byayah.get(a)
        if r is None or r["status"] != "dev":
            bad.append(f"{s}:{a}: ادّعاءُ تنازعٍ على آيةٍ ليست منحرفة")
            continue
        try:
            other = int(c.get("otherAyah"))
        except (TypeError, ValueError, AttributeError):
            bad.append(f"{s}:{a}: لا آيةَ أخرى مسمّاة")
            continue
        wits = c.get("witnesses") if isinstance(c, dict) else None
        if other == a or not isinstance(wits, dict) or len(wits) < DISPUTED_MIN_WITNESSES:
            bad.append(f"{s}:{a}: يلزم {DISPUTED_MIN_WITNESSES} شاهدان من تشغيلتين وآيةٌ أخرى غيرُها")
            continue
        det, why = {}, None
        for run, w in sorted(wits.items()):
            src = (sources or {}).get(str(run))
            if not isinstance(src, dict):
                why = "لا مصدرَ محمَّلٌ له من تشغيلة whisper_witness — المكتوبُ في المرشّح لا يُصدَّق وحده"
            elif "error" in src:
                why = f"تعذّر تحميلُه من مصدره: {src['error']}"
            elif _canon(disputed_src_rec(w)) != _canon(src):
                why = "المكتوبُ في المرشّح يخالف مصدرَه (‏مخرَج تشغيلته) حرفاً"
            else:
                why, d = disputed_one(src, s, a, r["startMs"], r["anchorMs"], other, ref_words, g_map, want,
                                      raw_last=raw_last(s, a))
            if why:
                why = f"الشاهد {run}: {why}"
                break
            det[str(run)] = d
        if why:
            ev["refused"][str(a)] = why
            bad.append(f"{s}:{a}: {why}")
            continue
        r["status"] = "disputed"
        ev["accepted"][str(a)] = {"otherAyah": other, "witnesses": det}
    n = n_ayahs or PH.heard_gate_n_ayahs(int(s))
    ev["nAyahs"] = n
    if len(ev["accepted"]) * 100 > DISPUTED_MAX_PCT * n:
        bad.append(f"المراسي المتنازَعُ عليها {len(ev['accepted'])} تتجاوز {DISPUTED_MAX_PCT}٪ من {n} آية — تُردّ السورةُ كلُّها")
    return (" · ".join(bad) if bad else None), ev


# ───────────── المرساةُ المزاحةُ داخلَ نصّ الآية نفسِها (‏#107 · قرار القائد 2026-11-10) ─────────────
# ⭐ الحالةُ: خريطةُ السماع تضع مرساةَ الآية **متأخّرةً عن بدئها** لأنّها التقطت كلمةً وسط نصّ الآية نفسِها (‏3siri 10:51 · 10:62 ·
#    10:14: مطلعُ «أثم» · «ألا» · «ثم» مسموعٌ عند المنشور والمرساةُ على «إذا ما وقع» · «أولياء»)، فيحكم الحارسُ بانحرافٍ > 1.5ث
#    والفهرسُ صواب. و#101 يردّها «تكرارٌ لا تنازع» لأنّ المرساةَ لا تسمع آيةً أخرى. فتُعدّ الآيةُ المنحرفةُ «owntext» لا تردّ
#    بشروطٍ **مجتمعةٍ** تُعاد كلُّها هنا من المصدر والخريطة لا من المكتوب:
#    ١) شاهدان على الأقلّ من تشغيلتين متمايزتين، يُحمَّلان من مصدر التشغيلة ويطابقان المكتوبَ حرفاً (‏كـ`disputed_src_rec`)،
#       بصمةُ كلٍّ = بصمةُ المرشّح = بصمةُ الخريطة، والملفُّ نفسُه، float32 (‏`pin_heard.check_witness`)؛
#    ٢) كلُّ شاهدٍ يسمع **مطلعَ الآية نفسِها** (‏أوّلَ W_K كلماتٍ من نصّ المصحف متّصلةً) وبدءُ أولاها ضمن W_AGREE_MS (‏300م.ث) من
#       **البدء المنشور**، بثقة `pin_heard` ولا التصاقَ بطرف النافذة؛
#    ٣) المرساةُ المزاحةُ تقع **من الخريطة** داخلَ مدى الآية نفسِها: بعد البدء المنشور بأكثر من TOL_MS، ومدى أدائها في الخريطة
#       `[بدء، نهاية]` ضمن نافذتها المنشورة (‏النهايةُ ≤ نهايةِ المنشور) ولا يتقاطع مع مدى أيّ آيةٍ أخرى في الخريطة نفسِها؛
#    ٤) السقفُ **مشتركٌ مع #101**: مجموعُ المتنازَع (‏`disputed`) و`owntext` ≤ DISPUTED_MAX_PCT٪ من آيات السورة، وإلا رُدّت السورةُ كلُّها؛
#    ٥) الدليلُ (‏الشاهدان + مدى الخريطة) مكتوبٌ في `transform.ownTextAnchors` باسمٍ مستقلّ وإصدارٍ `heard-owntext-1`،
#       ولا يدخل في أيّ عتبةٍ أخرى؛ وأيُّ ادّعاءٍ لا يستوفي الشروطَ يردّ السورة (‏لا يُترك صامتاً).
#    ⛔ لا عتبةَ تنخفض (‏1.5ث · 300م.ث · 10٪ · 5٪)، ولا يُرخى مسارٌ قائم؛ والخريطةُ الجزئيّةُ تُردّ في `compact_map` كما في #101.
OWNTEXT_VERSION = "heard-owntext-1"
OWNTEXT_KEY = "ownTextAnchors"


def own_text_map_check(a, row, cmap, pub_end):
    """(None، تفصيل) إن ثبت **من الخريطة** أنّ مرساةَ الآية `a` المزاحةَ داخلَ مداها هي لا في آيةٍ أخرى، وإلا (السبب، None)."""
    anc = cmap.get("anchors") or {}
    rec = anc.get(str(a))
    am = rec[0] if isinstance(rec, list) and rec else None
    try:
        a0, a1 = int(am[0]), int(am[1])
        st = int(row["startMs"])
        end = int(pub_end)
    except (TypeError, ValueError, IndexError, KeyError):
        return "لا مدى صالحٌ للمرساة في الخريطة أو لا نهايةَ منشورةَ للآية", None
    if a1 <= a0:
        return "مدى المرساة في الخريطة بلا نهايةٍ صالحة", None
    if a0 - st <= TOL_MS:
        return f"المرساةُ {a0} ليست متأخّرةً عن البدء المنشور {st} بأكثر من {TOL_MS}م.ث", None
    if a1 > end:
        return f"مدى المرساة [{a0}، {a1}] يخرج من نافذة الآية المنشورة (‏تنتهي {end})", None
    for b_s, brec in anc.items():
        if str(b_s) == str(a):
            continue
        bm = brec[0] if isinstance(brec, list) and brec else None
        try:
            b0, b1 = int(bm[0]), int(bm[1])
        except (TypeError, ValueError, IndexError):
            continue
        if b0 < a1 and a0 < b1:
            return f"مدى المرساة [{a0}، {a1}] يتقاطع في الخريطة مع مدى الآية {b_s} [{b0}، {b1}] — ليست وحدَها في موضعها", None
    return None, {"mapSpanMs": [a0, a1], "startMs": st, "shiftMs": a0 - st, "pubEndMs": end}


def own_text_head(wit, surah, ayah, start, ref_words, g_map, want_sha):
    """(None، تفصيل) إن أثبت الشاهدُ الواحدُ الشرطَ ٢ (‏مطلعُ الآية نفسِها ضمن W_AGREE_MS من المنشور)، وإلا (السبب، None)."""
    import pin_heard as PH  # noqa: PLC0415
    try:
        PH.check_witness(wit, surah, g_map, want_sha)
    except SystemExit as e:
        return str(e), None
    own = ref_words(surah, ayah)
    k = PH.W_K
    if len(own) < k:
        return "نصُّ الآية أقصرُ من W_K", None
    why = None
    for rec in (wit.get("ayahs") or {}).values():
        win = rec.get("windowMs") or [None, None]
        tk = _wtoks(rec)
        for i in range(len(tk) - k + 1):
            span = tk[i:i + k]
            if [x[0] for x in span] != own[:k]:
                continue
            if abs(span[0][1] - int(start)) > PH.W_AGREE_MS:
                why = f"مطلعُ الآية عند {span[0][1]} بعيدٌ عن المنشور {start} (>{PH.W_AGREE_MS}م.ث)"
                continue
            bad = _span_ok(span, win)
            if bad:
                why = f"مطلعُ الآية: {bad}"
                continue
            return None, {"headMs": span[0][1]}
    return why or "لا يُسمع مطلعُ الآية كلمةً بكلمة", None


def own_text_verdict(s, rows, g_map, want, cand_idx, ref_words=None, n_ayahs=None, sources=None, already=0):
    """يُحوّل كلَّ صفٍّ «dev» مدّعىً في `transform.ownTextAnchors[س]` ومُثبَتٍ بالشروط إلى «owntext».
    `already`: عددُ المتنازَع (‏#101) المقبول في السورة نفسِها — السقفُ مشتركٌ. يُرجع (سببُ ردّ السورة أو None، الدليل).
    بلا ادّعاءٍ للسورة لا يتغيّر شيءٌ حرفاً."""
    tr = cand_idx.get("transform") if isinstance(cand_idx.get("transform"), dict) else {}
    allc = tr.get(OWNTEXT_KEY)
    claims = allc.get(str(s)) if isinstance(allc, dict) else None
    if not claims or not isinstance(claims, dict):
        return None, None
    import pin_heard as PH  # noqa: PLC0415
    ref_words = ref_words or (lambda ss, a: disputed_ref_words(cand_idx.get("riwaya") or "hafs", ss, a))
    cs_s = by_surah(cand_idx.get("entries") or []).get(int(s)) or {}
    byayah = {r["ayah"]: r for r in rows}
    ev = {"version": OWNTEXT_VERSION, "accepted": {}, "refused": {}, "disputedAccepted": int(already)}
    bad = []
    for a_s, c in sorted(claims.items(), key=lambda kv: int(kv[0])):
        a = int(a_s)
        r = byayah.get(a)
        if r is None or r["status"] != "dev":
            bad.append(f"{s}:{a}: ادّعاءُ مرساةٍ مزاحةٍ على آيةٍ ليست منحرفة")
            continue
        wits = c.get("witnesses") if isinstance(c, dict) else None
        if not isinstance(wits, dict) or len(wits) < DISPUTED_MIN_WITNESSES:
            bad.append(f"{s}:{a}: يلزم {DISPUTED_MIN_WITNESSES} شاهدان من تشغيلتين")
            continue
        why, mdet = own_text_map_check(a, r, g_map, (cs_s.get(a) or (None, None))[1])
        det = {}
        if not why:
            for run, w in sorted(wits.items()):
                src = (sources or {}).get(str(run))
                if not isinstance(src, dict):
                    why = "لا مصدرَ محمَّلٌ له من تشغيلة whisper_witness — المكتوبُ في المرشّح لا يُصدَّق وحده"
                elif "error" in src:
                    why = f"تعذّر تحميلُه من مصدره: {src['error']}"
                elif _canon(disputed_src_rec(w)) != _canon(src):
                    why = "المكتوبُ في المرشّح يخالف مصدرَه (‏مخرَج تشغيلته) حرفاً"
                else:
                    why, d = own_text_head(src, s, a, r["startMs"], ref_words, g_map, want)
                if why:
                    why = f"الشاهد {run}: {why}"
                    break
                det[str(run)] = d
        if why:
            ev["refused"][str(a)] = why
            bad.append(f"{s}:{a}: {why}")
            continue
        r["status"] = "owntext"
        ev["accepted"][str(a)] = {"map": mdet, "witnesses": det}
    n = n_ayahs or PH.heard_gate_n_ayahs(int(s))
    ev["nAyahs"] = n
    total = int(already) + len(ev["accepted"])
    if total * 100 > DISPUTED_MAX_PCT * n:
        bad.append(f"المتنازَعُ عليه ({already}) والمرساةُ المزاحةُ داخل النصّ ({len(ev['accepted'])}) مجموعُهما {total} "
                   f"يتجاوز {DISPUTED_MAX_PCT}٪ من {n} آية — تُردّ السورةُ كلُّها")
    return (" · ".join(bad) if bad else None), ev


# ───────────── مسمّاةٌ غائبةٌ لكنّها مسموعةٌ في خريطة العامّة (‏ctc-absent-witnessed-1 · قرار القائد 2026-11-10) ─────────────
# ⭐ الحالةُ (‏الكردي 004.mp3 · س4 · 4:127): الخريطةُ تضع 4:127 مسموعةً عند [4133566، 4163246] بجودة 0.3، فيردّها
#    `heard_absent.agreed_anchors` («مسمّاةٌ غائبةٌ لكنّها مسموعةٌ في خريطة…»). وشاهدا Whisper float32 (‏medium · small) فرّغا
#    النافذةَ 4125–4170ث: 4:125 ثمّ 4:126 حتى ≈4162ث ثمّ 4:128 «وإن امرأة خافت» عند ≈4165ث — **ولا «ويستفتونك في النساء»**،
#    وأفضلُ مطابقةٍ لنصّها في الملفّ كلِّه 0.514 عند 5527ث (‏موضعُ 4:176 الشبيهة). فالمرساةُ الضعيفةُ تلقّطت صوتَ جارتيها.
#    فيُقبل التسميةُ **بشروطٍ مجتمعةٍ كلُّها تُعاد هنا من المصدر والخريطة لا من المكتوب**، وإلا بقي الردُّ القديمُ حرفاً:
#    ١) شاهدان float32 على الأقلّ من تشغيلتين متمايزتين، يُحمَّلان من مصدر التشغيلة (‏`pin_heard.load_witness`) ويطابقان
#       المكتوبَ حرفاً (‏كـ`disputed_src_rec`) — لا كلماتٌ مضمَّنةٌ يُوثق بها؛ وبصمةُ كلٍّ = بصمةُ الخريطة = بصمةُ الفهرس والملفُّ نفسُه
#       (‏`pin_heard.check_witness`)؛
#    ٢) كلٌّ منهما يفرّغ **النافذةَ التي ادّعتها الخريطةُ كاملةً** ويسمع فيها الجارتين بلفظهما: آخرَ W_K كلماتٍ من السابقة
#       وأوّلَ W_K من اللاحقة متّصلةً كلمةً بكلمة بثقة `pin_heard` ولا التصاقَ بطرف النافذة، والسابقةُ قبل اللاحقة؛
#    ٣) لا يسمع أيٌّ منهما **أوّلَ W_K كلماتٍ من الآية الغائبة** في تفريغه كلِّه (‏بأيّ ثقة)؛
#    ٤) جودةُ الخريطة هناك **دون 0.5** في كلّ مرشّحٍ (‏مِرساةٌ عامّةٌ أو أداءٌ منفرد؛ والأداءُ المنفردُ المقبولُ يبدأ من 0.5 فيردّ)؛
#    ٥) لا متّسعَ للآية: الفجوةُ بين نهاية السابقة المسموعة وبدء اللاحقة **عند كلٍّ من الشاهدين** أقلُّ من نصف المدّة المتوقَّعة
#       للغائبة (‏`witnessed_expected_ms`: وسيطُ مدّة الحرف عند أقرانها من آيات السورة نفسِها × حروفُها — يقابل
#       `pin_heard.expected_from_peers`) — فيثبت الغيابُ **بالزمن لا بالنصّ وحدَه**؛
#    ٦) القاعدةُ باسمٍ وإصدارٍ مستقلّين: `transform.witnessedAbsent` و`ctc-absent-witnessed-1` مع الدليل؛ لا الأولى ولا الأخيرة،
#       وضمن ربع آيات السورة؛ والإعلانُ يبقى SOURCE_TRUNCATED لكلّ آيةٍ (‏قاعدة 10-31 · `promote.declared_truncated_gaps`).
#    ⛔ لا عتبةَ تنخفض (‏0.5 · 5٪ · 300م.ث)، ولا يُرخى مسارٌ قائم: فحصُ «المطابقة القويّة ≥ 0.70» في الملفّ كلِّه يبقى كما هو،
#    والخريطةُ الجزئيّةُ تُردّ كما في #101. وسقفُ ربع السورة ولا-الأولى-ولا-الأخيرة في `heard_absent.check_named` قبل كلّ هذا.
WITNESSED_VERSION = "ctc-absent-witnessed-1"
WITNESSED_KEY = "witnessedAbsent"
WITNESSED_MIN_WITNESSES = 2
WITNESSED_Q_MAX = 0.5           # جودةُ الخريطة هناك دون هذا (‏الشرط ٤)
WITNESSED_SPACE_FRAC = 0.5      # الفجوةُ بين الجارتين أقلُّ من هذه النسبة من المتوقَّع (‏الشرط ٥)
WITNESSED_PREV_WINDOW = 6         # الجارةُ السابقة تُسمع بـW_K كلماتٍ متّصلةٍ من آخر هذا العدد من كلماتها
WITNESSED_MIN_PEERS = 3         # أقلُّ عددٍ من الأقران تُحسب منه المدّةُ المتوقَّعة


def _heard_absent():
    """بابُ `heard_absent` (‏alignment_v3 · stdlib وحده) — مصدرٌ واحدٌ لتعريف «المسموعة» في الخريطة (‏`candidates`)."""
    p = str(Path(__file__).resolve().parent.parent / "alignment_v3")
    if p not in sys.path:
        sys.path.insert(0, p)
    import heard_absent                                              # noqa: PLC0415
    return heard_absent


def witnessed_expected_ms(durs: dict, ayah: int, chars_of):
    """المدّةُ المتوقَّعةُ للآية الغائبة (‏م.ث) من أقرانها: وسيطُ (مدّةِ آيةٍ ÷ حروفِها) على `durs` {آية: (بدء، نهاية)} × حروفُ الغائبة.
    أو None إن قلّ الأقرانُ عن WITNESSED_MIN_PEERS. (‏البناءُ يمدّها بمدى المراسي والبوّابةُ بمداخل المرشّح؛ والصيغةُ واحدة.)"""
    rates = []
    for a, d in (durs or {}).items():
        try:
            dur, ch = int(d[1]) - int(d[0]), chars_of(a)
        except (TypeError, ValueError, IndexError):
            continue
        if a != ayah and dur > 0 and ch > 0:
            rates.append(dur / ch)
    if len(rates) < WITNESSED_MIN_PEERS:
        return None
    rates.sort()
    return rates[len(rates) // 2] * chars_of(ayah)


def _merged_windows(wit) -> list:
    iv = []
    for rec in ((wit or {}).get("ayahs") or {}).values():
        w = rec.get("windowMs") if isinstance(rec, dict) else None
        try:
            a, b = int(w[0]), int(w[1])
        except (TypeError, ValueError, IndexError):
            continue
        if b > a:
            iv.append((a, b))
    out: list = []
    for a, b in sorted(iv):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def witness_covers(wit, lo: int, hi: int) -> bool:
    """هل يفرّغ الشاهدُ [lo، hi] كاملاً بنوافذَ متّصلة؟"""
    return any(a <= int(lo) and b >= int(hi) for a, b in _merged_windows(wit))


def _word_hits(wit, target) -> list:
    """[(مقطع، نافذة)] كلُّ موضعٍ تتطابق فيه كلماتُ `target` متّصلةً كلمةً بكلمة (‏تطبيعُ هذا الباب) في تفريغ الشاهد."""
    k, out = len(target), []
    for rec in ((wit or {}).get("ayahs") or {}).values():
        win = rec.get("windowMs") or [None, None]
        tk = _wtoks(rec)
        for i in range(len(tk) - k + 1):
            span = tk[i:i + k]
            if [x[0] for x in span] == list(target):
                out.append((span, win))
    return out


def witnessed_witness_check(wit, surah, ayah, claim, own, prev, nxt, meta, want_sha, expected_ms, bounds=None):
    """(None، تفصيل) إن أثبت الشاهدُ الواحدُ الشروطَ ١(‏النموذج float32 والبصمة) و٢ و٣ و٥ للآية، وإلا (السببُ، None)."""
    import pin_heard as PH                                           # noqa: PLC0415
    try:
        PH.check_witness(wit, surah, meta, want_sha)
    except SystemExit as e:
        return str(e), None
    k = PH.W_K
    if claim and not witness_covers(wit, claim[0], claim[1]):
        return (f"لا يفرّغ النافذةَ التي ادّعتها الخريطةُ [{claim[0]}، {claim[1]}] كاملةً "
                f"(‏نوافذُه {_merged_windows(wit)})"), None
    if _word_hits(wit, own[:k]):
        return f"يسمع في تفريغه أوّلَ {k} كلماتٍ من الآية الغائبة «{' '.join(own[:k])}» — مسموعةٌ لا غائبة", None
    # ⭐ (‏kurdi 4:127 · أوّل تشغيلٍ حقيقيّ · أمر القائد) Whisper كتب «من كل شيء محيطا» لا «بكل شيء محيطا» في الشهود الأربعة، فلم تُسمع
    #    آخرُ W_K كلماتٍ من السابقة. فيُقبل **أيُّ W_K كلماتٍ متّصلةٍ داخل آخر WITNESSED_PREV_WINDOW كلماتٍ** منها (‏مثل «الأرض وكان الله»)
    #    مطابقةً حرفيّةً بالثقة نفسِها؛ ولا يتغيّر W_K. والفجوةُ تُحسب من **نهاية المقطع المطابَق نفسِه** لا من نهاية الآية (‏فتكبر الفجوةُ
    #    ويصعب الشرط). ⛔ لا إرخاءَ لثقةٍ ولا لمطلع الغائبة ولا للملتقى ولا للجودة.
    prevs = []                                                       # [(مقطع، نافذة، عددُ الكلمات بعد المقطع من السابقة)]
    for i in range(max(0, len(prev) - WITNESSED_PREV_WINDOW), len(prev) - k + 1):
        for h in _word_hits(wit, prev[i:i + k]):
            if _span_ok(h[0], h[1]) is None:
                prevs.append((h[0], h[1], prev[i + k:]))
    nexts = [h for h in _word_hits(wit, nxt[:k]) if _span_ok(h[0], h[1]) is None]
    if not prevs:
        return (f"لا يسمع الجارةَ السابقةَ بلفظها ({k} كلماتٍ متّصلةً من آخر {WITNESSED_PREV_WINDOW} كلماتٍ منها "
                f"«{' '.join(prev[-WITNESSED_PREV_WINDOW:])}» بثقةٍ كافية)"), None
    if not nexts:
        return f"لا يسمع الجارةَ اللاحقةَ بلفظها (‏أوّلَ {k} كلماتٍ «{' '.join(nxt[:k])}» بثقةٍ كافية)", None
    if not claim and not bounds:
        return "لا موضعَ يقيّد ملتقى الجارتين (‏لا نافذةَ مدّعاةً ولا مداخلَ جارتين) — لا يُقبل ادّعاءٌ بلا قيدٍ مكانيّ", None
    pairs = [(p, n) for p in prevs for n in nexts if n[0][0][1] >= p[0][0][1]]
    if not pairs:
        return "اللاحقةُ لا تأتي بعد السابقة في تفريغه", None
    # ⛔ (‏مراجعةُ القائد #108) الملتقى يجب أن يقع **في الموضع المدّعى** لا في أيّ موضعٍ يكرّر فيه القارئُ اللفظَ أو يتشابه:
    #    (أ) مع claim: الفترةُ [نهايةُ السابقة، بدءُ اللاحقة] تتقاطع مع نافذة الخريطة المدّعاة؛
    #    (ب) مع bounds (‏البوّابة: نهايةُ مدخل a−1 وبدءُ مدخل a+1 في المرشّح نفسِه): طرفا الملتقى كلٌّ ضمن TOL_MS من طرفه.
    def located(p_end_, n_start_, tail_):
        if claim and not (p_end_ <= claim[1] and n_start_ >= claim[0]):
            return False
        if bounds:
            # بدءُ اللاحقة ضمن TOL_MS من بدء مدخل a+1 كما كان.
            if abs(n_start_ - bounds[1]) > TOL_MS:
                return False
            if not tail_:
                # المقطعُ هو آخرُ W_K كلماتٍ بلا شيءٍ بعده ⇒ القيدُ القديمُ حرفاً (‏نهايته ضمن TOL_MS من نهاية مدخل a−1).
                if abs(p_end_ - bounds[0]) > TOL_MS:
                    return False
            else:
                # بقيت بعده كلماتٌ ⇒ نهايتُه المقيسةُ داخل مدخل a−1 نفسِه: بين بدئه ونهايته + TOL_MS (‏بلا تقديرٍ بوتيرة الأقران).
                p_start_ = bounds[2] if len(bounds) > 2 else None
                if p_start_ is None or not (p_start_ <= p_end_ <= bounds[0] + TOL_MS):
                    return False
        return True
    # الفجوةُ من نهاية **المقطع المطابَق** (‏p[0][-1][2]) لا من نهاية الآية.
    cand = [(int(p[0][-1][2]), int(n[0][0][1]), bool(p[2])) for p, n in pairs]
    cand = [c for c in cand if located(*c)]
    if not cand:
        where = (f"نافذة الخريطة [{claim[0]}، {claim[1]}]" if claim else "") + (" و" if claim and bounds else "") + \
                (f"ما بين نهاية مدخل الجارة السابقة {bounds[0]} وبدء اللاحقة {bounds[1]} (±{TOL_MS})" if bounds else "")
        return f"ملتقى الجارتين في تفريغه لا يقع في الموضع المدّعى — {where}", None
    p_end, n_start, _tail = min(cand, key=lambda c: max(0, c[1] - c[0]))
    gap = max(0, n_start - p_end)
    if not expected_ms or expected_ms <= 0:
        return "لا مدّةَ متوقَّعةً للآية من أقرانها — لا يثبت الغيابُ بالزمن", None
    if gap >= WITNESSED_SPACE_FRAC * expected_ms:
        return (f"الفجوةُ بين السابقة ({p_end}) واللاحقة ({n_start}) {gap}م.ث ≥ نصف المتوقَّع "
                f"{WITNESSED_SPACE_FRAC * expected_ms:.0f}م.ث (‏{expected_ms:.0f}) — فيها متّسعٌ للآية"), None
    return None, {"model": wit.get("model"), "computeType": wit.get("computeType"), "prevEndMs": p_end,
                  "nextStartMs": n_start, "gapMs": gap, "windowsMs": _merged_windows(wit)}


def witnessed_absent_one(surah, ayah, n_ayahs, g_rec, r_rec, wits, sources, ref_words, meta, want_sha, expected_ms, bounds=None):
    """(None، دليل) إن ثبت غيابُ الآية المسمّاة بالشروط ١–٥ كلِّها، وإلا (سببُ الردّ، None).
    `g_rec`/`r_rec`: سجلُّ الآية في خريطة العامّة وخريطة نموذج التلاوة (‏`heardMap[آية]`: anchorMs · anchorQuality · heardMs · score)
    — `r_rec` اختياريّ (‏البوّابةُ لا تملك إلا العامّة). `wits`: {تشغيلة: سجلُّ الشاهد المكتوب}، و`sources`: المحمَّلُ من المصدر."""
    import pin_heard as PH                                           # noqa: PLC0415
    HA = _heard_absent()
    if not 2 <= int(ayah) <= int(n_ayahs) - 1:
        return f"لا تسري القاعدةُ على الآية الأولى ولا الأخيرة (‏2..{int(n_ayahs) - 1})", None
    cands = HA.candidates(g_rec) + HA.candidates(r_rec)
    hi_q = [c for c in cands if c[3] >= WITNESSED_Q_MAX]
    if hi_q:
        return (f"جودةُ الخريطة هناك {hi_q[0][3]} ({hi_q[0][0]} {hi_q[0][1]}–{hi_q[0][2]}) ≥ {WITNESSED_Q_MAX} — "
                "الردُّ القديمُ باقٍ"), None
    claim = [min(c[1] for c in cands), max(c[2] for c in cands)] if cands else None
    if not isinstance(wits, dict) or len(wits) < WITNESSED_MIN_WITNESSES:
        return f"يلزم {WITNESSED_MIN_WITNESSES} شاهدان float32 من تشغيلتين متمايزتين", None
    own, prev, nxt = ref_words(surah, ayah), ref_words(surah, ayah - 1), ref_words(surah, ayah + 1)
    if min(len(own), len(prev), len(nxt)) < PH.W_K:
        return "نصُّ الآية أو إحدى جارتيها أقصرُ من W_K", None
    det = {}
    for run, w in sorted(wits.items()):
        src = (sources or {}).get(str(run))
        if not isinstance(src, dict):
            why = "لا مصدرَ محمَّلٌ له من تشغيلة whisper_witness — المكتوبُ في المرشّح لا يُصدَّق وحده"
        elif "error" in src:
            why = f"تعذّر تحميلُه من مصدره: {src['error']}"
        elif _canon(disputed_src_rec(w)) != _canon(src):
            why = "المكتوبُ في المرشّح يخالف مصدرَه (‏مخرَج تشغيلته) حرفاً"
        else:
            why, d = witnessed_witness_check(src, surah, ayah, claim, own, prev, nxt, meta, want_sha, expected_ms, bounds)
        if why:
            return f"الشاهد {run}: {why}", None
        det[str(run)] = d
    return None, {"claimMs": claim, "mapQuality": max((c[3] for c in cands), default=None),
                  "expectedMs": round(expected_ms), "witnesses": det}


def witnessed_absent_verdict(s, g_map, want, cand_idx, ref_words=None, n_ayahs=None, sources=None):
    """يُعيد حسابَ كلّ ادّعاءٍ في `transform.witnessedAbsent[س]` من المصدر والخريطة والمرشّح. يُرجع (سببُ ردّ السورة أو None، الدليل).
    بلا ادّعاءٍ للسورة لا يتغيّر شيءٌ حرفاً. البوّابةُ تملك خريطةَ العامّة وحدَها، فشرطُ الجودة (‏٤) عليها وحدَها هنا
    (‏والبناءُ يحكم بالخريطتين)، والمدّةُ المتوقَّعةُ من مداخل المرشّح نفسِه."""
    tr = cand_idx.get("transform") if isinstance(cand_idx.get("transform"), dict) else {}
    allc = tr.get(WITNESSED_KEY)
    claims = allc.get(str(s)) if isinstance(allc, dict) else None
    if not claims or not isinstance(claims, dict):
        return None, None
    import pin_heard as PH                                           # noqa: PLC0415
    ref_words = ref_words or (lambda ss, a: disputed_ref_words(cand_idx.get("riwaya") or "hafs", ss, a))
    n = n_ayahs or PH.heard_gate_n_ayahs(int(s))
    gap_rec = (tr.get("truncatedGaps") or {}).get(str(s)) if isinstance(tr.get("truncatedGaps"), dict) else None
    declared = {a for a in ((gap_rec or {}).get("absent") or []) if type(a) is int}
    present = by_surah(cand_idx.get("entries") or []).get(int(s)) or {}
    chars_of = lambda a: sum(len(w) for w in ref_words(int(s), a))   # noqa: E731
    durs = {a: (v[0], v[1]) for a, v in present.items() if v[1] is not None}
    ev = {"version": WITNESSED_VERSION, "accepted": {}, "refused": {}, "nAyahs": n}
    bad = []
    anc = (g_map or {}).get("anchors") or {}
    for a_s, c in sorted(claims.items(), key=lambda kv: int(kv[0])):
        a = int(a_s)
        if a not in declared:
            bad.append(f"{s}:{a}: ادّعاءُ غيابٍ مشهودٍ لآيةٍ لم يُعلَن حجبُها في truncatedGaps")
            continue
        if a in present:
            bad.append(f"{s}:{a}: ادّعاءُ غيابٍ مشهودٍ لآيةٍ لها مدخلٌ في المرشّح")
            continue
        rec = anc.get(str(a))
        g_rec = {"anchorMs": rec[0] if isinstance(rec, list) and rec else None,
                 "anchorQuality": rec[1] if isinstance(rec, list) and len(rec) > 1 else None}
        pe, ns = present.get(a - 1), present.get(a + 1)
        if not pe or not ns or pe[1] is None:
            bad.append(f"{s}:{a}: لا مدخلَ للجارة السابقة أو اللاحقة في المرشّح — لا قيدَ مكانيّ لملتقاهما")
            continue
        # ⛔ الملتقى بين نهاية مدخل a−1 وبدء مدخل a+1 في المرشّح نفسِه ضمن TOL_MS (‏مراجعةُ القائد #108)
        why, det = witnessed_absent_one(int(s), a, n, g_rec, None, (c or {}).get("witnesses"), sources, ref_words,
                                        g_map, want, witnessed_expected_ms(durs, a, chars_of),
                                        bounds=(int(pe[1]), int(ns[0]), int(pe[0])))
        if why:
            ev["refused"][str(a)] = why
            bad.append(f"{s}:{a}: {why}")
            continue
        ev["accepted"][str(a)] = det
    if len(claims) * 4 > n:
        bad.append(f"المسمّاةُ المشهودةُ {len(claims)} تتجاوز ربع آيات السورة ({n}) — الإسقاطُ الكامل")
    return (" · ".join(bad) if bad else None), ev


def judge(cand_idx: dict, pub_idx: dict | None, cand_sha: str, maps: dict,
          maps_r: dict | None = None, witness: dict | None = None,
          dual: dict | None = None, ref_words=None, disputed_src: dict | None = None) -> dict:
    """حكمُ البوّابة كاملاً من المرشّح والمنشور والخرائط ({سورة: compact_map}).
    يُرجع {"ok": bool, "reason": str|None, "required": [...], "modified": [...], "sample": [...],
            "surahs": {س: {"reason":..., "rows":[...]}}, "dual": {س: دليل}}.
    الباب الثاني (‏`maps_r` خرائطُ نموذج التلاوة · `witness` {سورة: مخرَجُ whisper_witness} · `dual` قائمةٌ تُعطى بدل الملفّ):
    لا يمسّ إلا سورةً **معدّلةً** لقارئٍ مسمّىً في `heard_dual.txt`؛ وما سواها بالشيفرة القديمة حرفاً."""
    ents = cand_idx.get("entries") or []
    cs = by_surah(ents)
    modified = modified_surahs(ents, (pub_idx or {}).get("entries") or []) if pub_idx else sorted(cs)
    sample = sample_surahs(cand_sha, [s for s in cs if s not in modified])
    required = sorted(set(modified) | set(sample))
    present = sorted(cs)
    shas = cand_idx.get("audioSha256")
    audio_by_surah = {}
    if isinstance(shas, list):
        # القائمة الثابتة تبقي موضع السورة المحذوفة؛ المضغوطة تتبع السور الحاضرة مرتبةً.
        if len(shas) == 114:
            audio_by_surah = {s: shas[s - 1] for s in present if 1 <= s <= 114}
        elif len(shas) == len(present):
            audio_by_surah = dict(zip(present, shas))
    out = {"ok": False, "reason": None, "required": required, "modified": modified,
           "sample": sample, "surahs": {}, "sampleFindings": [], "version": VERSION, "dual": {}}
    dual_set = dual_surahs(cand_idx, dual)
    ps = by_surah((pub_idx or {}).get("entries") or []) if pub_idx else {}
    out["weak"] = {}
    bad = []
    for s in required:
        # ⚖️ العيّنةُ (غيرُ المعدّلة) للتقرير وحده: ما يُوجد فيها يُسجَّل ولا يردّ.
        sink = bad if s in modified else out["sampleFindings"]
        m = maps.get(s) or maps.get(str(s))
        if not m:
            sink.append(f"س{s}: لا خريطةَ سماع")
            continue
        want = audio_by_surah.get(s)
        if not isinstance(want, str) or not want.strip():
            sink.append(f"س{s}: لا بصمةَ صوتٍ صالحة في audioSha256 للمرشّح")
            continue
        if m.get("sha256") != want:
            sink.append(f"س{s}: الصوتُ المسموع ({str(m.get('sha256'))[:8]}) غيرُ صوت المرشّح ({str(want)[:8]})")
            continue
        refs = {v[2] for v in cs[s].values()}
        if m.get("fileRef") and refs and m["fileRef"] not in refs:
            sink.append(f"س{s}: سُمع {m['fileRef']} والمرشّحُ يشير إلى {sorted(refs)[0]}")
            continue
        if s in modified and s in dual_set:
            mr = (maps_r or {}).get(s) or (maps_r or {}).get(str(s))
            wt = (witness or {}).get(s) or (witness or {}).get(str(s))
            why, dv = dual_surah(s, cs[s], m, mr, wt, want, cand_sha, cand_idx.get("riwaya"), ref_words)
            # ⛔ قاعدةُ المِرساة الضعيفة في الباب المزدوج: آيةٌ ممسوسةٌ لم تقسها **أيُّ** خريطةٍ (‏G ولا R) ولم يحسمها شاهد
            #    تردّ السورة — ولا تُعفى بنسبة التغطية 90٪ (‏تشديد 2026-11-10). والمقيسةُ بـR وحدها تبقى لعيّنة الاستقلال كما هي.
            pend = [r for r in dv["rows"] if r["status"] == "unmeasured"]
            weak_d = weak_touched(cs[s], ps.get(s), pend)
            ev_w = {"version": WEAK_VERSION, "weak": weak_d, "witnessed": [], "missing": weak_d, "dualPath": True}
            out["weak"][str(s)] = ev_w
            why_w = (f"{len(weak_d)} آيةً مسّها التحويل ولم تقسها خريطةٌ بجودة {MIN_Q} ولا شهد لها شاهد Whisper في موضعها "
                     f"(الآيات {','.join(str(a) for a in weak_d[:30])})") if weak_d else None
            why = " · ".join(x for x in (why, why_w) if x) or None
            out["surahs"][str(s)] = {"reason": why, "rows": dv["rows"]}
            out["dual"][str(s)] = dv["evidence"]
            if why:
                sink.append(f"س{s}: {why}")
            continue
        rows = surah_rows({a: v[0] for a, v in cs[s].items()}, m)
        why_d, ev_d = disputed_verdict(s, rows, m, want, cand_idx, ref_words,
                                       sources=(disputed_src or {}).get(str(s)))
        if ev_d:
            out.setdefault("disputed", {})[str(s)] = ev_d
        # ⭐ (‏#107) المرساةُ المزاحةُ داخل نصّ الآية نفسِها — بعد #101 (‏فلا تُعدّ آيةٌ بالقاعدتين) والسقفُ مشتركٌ بينهما
        why_o, ev_o = own_text_verdict(s, rows, m, want, cand_idx, ref_words, sources=(disputed_src or {}).get(str(s)),
                                       already=len((ev_d or {}).get("accepted") or {}))
        if ev_o:
            out.setdefault("ownText", {})[str(s)] = ev_o
        # ⭐ (‏ctc-absent-witnessed-1) مسمّاةٌ غائبةٌ مسموعةٌ في الخريطة — يُعاد حكمُها من المصدر هنا لا من المكتوب
        why_a, ev_a = witnessed_absent_verdict(s, m, want, cand_idx, ref_words, sources=(disputed_src or {}).get(str(s)))
        if ev_a:
            out.setdefault("witnessedAbsent", {})[str(s)] = ev_a
        why = " · ".join(x for x in (surah_verdict(rows), why_d, why_o, why_a) if x) or None
        if s in modified:
            wt = (witness or {}).get(s) or (witness or {}).get(str(s))
            why_w, ev_w = weak_verdict(s, cs[s], ps.get(s), rows, m, wt, want, cand_idx.get("riwaya"), ref_words,
                                       cand_idx=cand_idx, sources=(disputed_src or {}).get(str(s)))
            out["weak"][str(s)] = ev_w
            why = " · ".join(x for x in (why, why_w) if x) or None
        out["surahs"][str(s)] = {"reason": why, "rows": rows}
        if why:
            sink.append(f"س{s}{'' if s in modified else ' (عيّنة)'}: {why}")
    out["ok"] = not bad
    out["reason"] = " · ".join(bad)[:2000] if bad else None
    return out


def gate_error(cand_idx: dict, pub_idx: dict | None, cand_sha: str, rep: dict | None) -> str | None:
    """ما تستدعيه الترقية: سببُ الردّ أو None. **يعيد الحساب ولا يقرأ حكماً مكتوباً.**"""
    if not isinstance(rep, dict):
        return "لا حكمَ سماعٍ (state-heard) — أطلق heard_gate.yml على هذا المرشّح"
    if rep.get("sha256") != cand_sha:
        return "حكمُ السماع على بصمةٍ أخرى — يُعاد على هذه"
    maps = {int(k): v for k, v in (rep.get("maps") or {}).items()}
    maps_r = {int(k): v for k, v in (rep.get("mapsR") or {}).items()}
    wit = {int(k): v for k, v in (rep.get("witness") or {}).items()}
    dsrc = rep.get("disputedSource") if isinstance(rep.get("disputedSource"), dict) else {}
    try:
        j = judge(cand_idx, pub_idx, cand_sha, maps, maps_r, wit, disputed_src=dsrc)
    except ValueError as e:                      # heard_dual.txt معطوبٌ ⇒ يُغلق الحكم ولا يُفتح
        return f"بوّابةُ السماع: قائمةُ heard_dual.txt معطوبة — {e}"
    if not j["required"]:
        return None
    return None if j["ok"] else "بوّابةُ السماع: " + j["reason"]


# ───────────── قراءةُ تقرير السبر النصّيّ (‏للمعايرة على سبور التدقيق) ─────────────
def map_from_report(text: str) -> dict:
    """تقريرُ `ctc_heard_map --report` ⇒ compact_map (‏الأزمنةُ فيه بعُشر الثانية)."""
    anc = {}
    surah = None
    for ln in text.splitlines():
        p = ln.split("\t")
        if not re.fullmatch(r"\d+:\d+", p[0]) or len(p) < 7:
            continue
        s, a = (int(x) for x in p[0].split(":"))
        surah = s
        try:
            am, q = [int(float(p[1]) * 1000), int(float(p[2]) * 1000)], float(p[3])
        except ValueError:
            am, q = None, None
        occ = []
        try:
            if p[4] != "—":
                occ.append([int(float(p[4]) * 1000), int(float(p[5]) * 1000), float(p[6])])
        except ValueError:
            pass
        if len(p) > 7:
            for mm in re.finditer(r"(\d+)–(\d+)s\(([0-9.]+)\)", p[7]):
                occ.append([int(mm.group(1)) * 1000, int(mm.group(2)) * 1000, float(mm.group(3))])
        anc[str(a)] = [am, q, occ]
    return {"surah": surah, "anchors": anc}


def main() -> int:
    """قراءةٌ محضة: `heard_gate.py <مرشّح> [...]` يطبع حكمَ البوّابة من الدلو كما تحكم الترقية."""
    import gzip
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import promote as P  # noqa: PLC0415
    cl, bucket = P.s3()
    for src in sys.argv[1:]:
        body = cl.get_object(Bucket=bucket, Key=src)["Body"].read()
        sha = hashlib.sha256(body).hexdigest()
        idx = json.loads(gzip.decompress(body))
        riw, fn = src.split("/")[1], src.split("/")[2]
        pub = json.loads(gzip.decompress(cl.get_object(
            Bucket=bucket, Key=f"timings/{riw}/{fn.split('.')[0]}.jz")["Body"].read()))
        try:
            rep = json.loads(cl.get_object(Bucket=bucket, Key=state_key(src))["Body"].read())
        except Exception:                                   # noqa: BLE001
            rep = None
        why = gate_error(idx, pub, sha, rep)
        print(f"■ {src} ({sha[:8]}) ⇒ {'✅ يمرّ' if why is None else '⛔ ' + why}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
