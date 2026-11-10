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


def compact_map(heard: dict) -> dict:
    """ما يلزم الحكمَ من مخرَج `ctc_heard_map` (‏يُحفظ في state ويُعاد منه الحساب)."""
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
                 ref_words=None):
    """(سببُ الردّ أو None، دليل) لقاعدة المِرساة الضعيفة في سورةٍ معدّلة. الشاهدُ يُعاد حكمُه هنا ولا يُقرأ حكمٌ مكتوب."""
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
    if not miss:
        return None, ev
    return (f"{len(miss)} آيةً مسّها التحويل ومرساتُها دون {MIN_Q} بلا شاهد Whisper يشهد لنصّها في موضعها "
            f"(الآيات {','.join(str(a) for a in miss[:30])})" + (f" — {bad}" if bad and not res else "")), ev


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


def _witness_eval(wit, surah, g_map, want_sha, riwaya, starts, ayahs, ref_words=None):
    """{آية: (حاسمٌ؟, تفصيل)} بشروط `pin_heard._whisper_check` نفسِها، والبدءُ المقابَل هو **البدءُ المنشور**. الشاهدُ غيرُ الصالح ⇒ لا شيء."""
    import pin_heard as PH  # noqa: PLC0415  (‏استيرادٌ كسول: pin_heard نفسُه يستورد هذا الملفّ)
    try:
        PH.check_witness(wit, surah, g_map, want_sha)
    except SystemExit as e:
        return {}, str(e)
    ref_words = ref_words or PH.ref_words_for
    res = {}
    for a in ayahs:
        if str(a) not in ((wit or {}).get("ayahs") or {}):
            res[a] = (False, "لا تفريغَ لهذه الآية في الشاهد")
            continue
        try:
            ref = ref_words(riwaya, surah, a)
        except (SystemExit, Exception):                    # noqa: BLE001
            ref = None
        hm = {"heardMap": {str(a): {"anchorMs": [int(starts[a]), int(starts[a]) + 1]}}}
        c, info = PH._whisper_check(wit, hm, surah, a, ref, fuzzy=False)
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
DISPUTED_VERSION = "heard-disputed-1"
DISPUTED_MAX_PCT = 10
DISPUTED_MIN_WITNESSES = 2
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
    da = tr.get("disputedAnchors")
    if not isinstance(da, dict):
        return {}
    if loader is None:
        import pin_heard as PH  # noqa: PLC0415
        loader = PH.load_witness
    out = {}
    for s, claims in sorted(da.items(), key=lambda kv: str(kv[0])):
        runs = set()
        for c in (claims.values() if isinstance(claims, dict) else []):
            if isinstance(c, dict) and isinstance(c.get("witnesses"), dict):
                runs |= {str(r) for r in c["witnesses"]}
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


def disputed_one(wit, surah, ayah, start, anchor, other, ref_words, g_map, want_sha):
    """(None، تفصيل) إن أثبت الشاهدُ الواحد الشرطين ٢ و٣ للآية، وإلا (سببُ الردّ، None)."""
    import pin_heard as PH  # noqa: PLC0415
    try:
        PH.check_witness(wit, surah, g_map, want_sha)
    except SystemExit as e:
        return str(e), None
    own, oth = ref_words(surah, ayah), ref_words(surah, other)
    k = PH.W_K
    if len(own) < k or len(oth) < k:
        return "نصُّ الآية أو الآية الأخرى أقصرُ من W_K", None
    own_grams = {tuple(own[i:i + k]) for i in range(len(own) - k + 1)}
    head = why2 = why3 = None
    hit3 = None
    for rec in (wit.get("ayahs") or {}).values():
        win = rec.get("windowMs") or [None, None]
        tk = _wtoks(rec)
        for i in range(len(tk) - k + 1):
            span = tk[i:i + k]
            words = [x[0] for x in span]
            if head is None and words == own[:k]:
                if abs(span[0][1] - int(start)) > PH.W_AGREE_MS:
                    why2 = f"مطلعُ الآية عند {span[0][1]} بعيدٌ عن المنشور {start} (>{PH.W_AGREE_MS}م.ث)"
                else:
                    bad = _span_ok(span, win)
                    if bad:
                        why2 = f"مطلعُ الآية: {bad}"
                    else:
                        head = span[0][1]
            if hit3 is None and span[0][1] <= int(anchor) < span[-1][2]:
                if tuple(words) in own_grams:
                    why3 = "ما سُمع عند المرساة من نصّ الآية نفسِها (‏تكرارٌ لا تنازع)"
                elif not any(words == oth[j:j + k] for j in range(len(oth) - k + 1)):
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


def disputed_verdict(s, rows, g_map, want, cand_idx, ref_words=None, n_ayahs=None, sources=None):
    """يُحوّل كلَّ صفٍّ «dev» مدّعىً في `transform.disputedAnchors[س]` ومُثبَتٍ بالشروط إلى «disputed».
    يُرجع (سببُ ردّ السورة أو None، الدليل). بلا ادّعاءٍ للسورة لا يتغيّر شيءٌ حرفاً."""
    tr = cand_idx.get("transform") if isinstance(cand_idx.get("transform"), dict) else {}
    claims = ((tr.get("disputedAnchors") or {}).get(str(s))) if isinstance(tr.get("disputedAnchors"), dict) else None
    if not claims:
        return None, None
    import pin_heard as PH  # noqa: PLC0415
    ref_words = ref_words or (lambda ss, a: disputed_ref_words(cand_idx.get("riwaya") or "hafs", ss, a))
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
                why, d = disputed_one(src, s, a, r["startMs"], r["anchorMs"], other, ref_words, g_map, want)
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
        why = " · ".join(x for x in (surah_verdict(rows), why_d) if x) or None
        if s in modified:
            wt = (witness or {}).get(s) or (witness or {}).get(str(s))
            why_w, ev_w = weak_verdict(s, cs[s], ps.get(s), rows, m, wt, want, cand_idx.get("riwaya"), ref_words)
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
