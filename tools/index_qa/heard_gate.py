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
# ⭐ النافذةُ **تبدأ من البدء المنشور** وقبلها حشوٌ لا يتجاوز 300م.ث (‏قرار القائد 20:30Z · كان 3000 فحمل ذيلَ الآية السابقة
#    فسُمع «عن الهواء وإلا وحي» مكان «إن هو إلا وحي» في 53:4). ⛔ لا يُعالَج ذلك بقبول ذيل السابقة ولا بفزرة (fuzzy)
#    ولا بتخفيف شرطٍ في `pin_heard._whisper_check` (‏الكلماتُ الأولى بلا fuzzy · الثقة · الاتّفاقُ ≤300م.ث مع البدء المنشور كما هي حرفاً).
WIT_PAD_MS = 300             # حشوُ ما قبل البدء المنشور في نافذة الشاهد (‏نافذةٌ لا عتبة؛ والحكمُ لا يقرأها)
WIT_TAIL_PAD_MS = 3000       # حشوُ ما بعد نهاية المنشور (‏لم يتغيّر: الآخرُ يُطابَق بالنهاية لا بالبدء)
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
    nd = dual_needs(dual_classify(starts, g_map, r_map), cand_sha, surah)
    return sorted(set(nd["contested"]) | set(nd["cover"]) | set(nd["sample"]))


def witness_windows(ends: dict, ayahs) -> str:
    """نوافذُ `whisper_witness --ayahs` (‏آية:بدء-نهاية): من البدء المنشور − WIT_PAD_MS إلى النهاية المنشورة + WIT_TAIL_PAD_MS، بسقف 120ث."""
    parts = []
    for a in sorted(ayahs):
        st, en = ends[a]
        lo = max(0, int(st) - WIT_PAD_MS)
        hi = int(en if en is not None else st + 20000) + WIT_TAIL_PAD_MS
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
    asked = sorted(set(nd["contested"]) | set(nd["cover"]) | set(nd["sample"]))
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
        elif r["status"] == "unmeasured" and a in nd["cover"] and a in ok_wit:
            r["status"], r["witness"] = "witness", res[a][1]
    covered = sum(1 for r in rows if r["status"] != "unmeasured")
    ev.update({"n": n, "gMeasured": g_meas, "rMeasured": r_meas, "covered": covered,
               "contested": nd["contested"], "contestedResolved": resolved,
               "coverWitnessed": [r["ayah"] for r in rows if r["status"] == "witness"],
               "sample": nd["sample"], "sampleOk": [a for a in nd["sample"] if a in ok_wit],
               "witness": {str(a): res[a][1][:200] for a in sorted(res) if a in set(resolved) | set(nd["sample"]) | set(nd["cover"])},
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


# ───────────── الباب الثالث: آيةٌ مكرّرةٌ مشهودة (‏إذنُ المالك 2026-11-07 20:40Z) ─────────────
# ⭐ **إضافيٌّ لا بديل ويُغلق عند الشكّ.** آيةٌ **منحرفةٌ عن المِرساة العامّة** (‏status=dev بقاعدة 1500م.ث نفسِها) تمرّ إن اجتمعت فيها
#    **ثلاثةُ شروطٍ لا يكفي منها اثنان**، وكلُّها يُعاد حسابُها من البيانات المحفوظة (‏لا حكمٌ مكتوب):
#    ١. **شاهدُ Whisper حاسم** بشروط `pin_heard._whisper_check` نفسِها بلا fuzzy (‏تطابقُ الطرفين · الثقة · اتّفاقٌ ≤300م.ث مع **البدء
#       المنشور**)، ونافذتُه المصلحةُ التي تبدأ من البدء المنشور بحشوٍ ≤ WIT_PAD_MS (‏يُتحقَّق منها في الشاهد المحفوظ نفسِه).
#    ٢. **مدخلُها يمرّ إحصاءَ النوافذ** (‏`entry_window_census.judge_entry` بقاعدة الأقرب) على نافذة مدخلها المنشور بعينه (‏بدءاً ونهاية).
#    ٣. **تكرارُها مقيسٌ في خريطة السماع**: أداءٌ آخرُ للآية نفسِها، قبل المِرساة أو بعدها (‏منفصلٌ عنها)، بجودةٍ ≥ REPEAT_OCC_Q،
#       ولا يقع على مِرساة آيةٍ أخرى (‏فذاك المتشابهات لا التكرار).
#    ⛔ لا يمسّ TOL_MS ولا MIN_Q ولا عتبة 5٪ ولا `--allow`؛ والثوابتُ في الشيفرة لا في البيئة. ومقصورٌ على الآيات المنحرفة عن العامّة:
#       ما لم تنحرف لا يدخله، وما بقي منحرفاً بعد الباب يردّ السورةَ كما كان.
REPEAT_VERSION = "heard-repeat-1"
REPEAT_OCC_Q = 0.5           # أدنى جودةٍ لأداءٍ آخرَ للآية يُعدّ به التكرارُ مقيساً
REPEAT_OTHER_OVERLAP = 0.5   # تقاطعُ الأداء مع مِرساة آيةٍ أخرى بهذه النسبة من الأقصر ⇒ تشابهٌ لا تكرار
REPEAT_STATUS = "witnessed_repeat"
# ⭐ الشاهدُ الملتصق بنافذته ليس شاهداً (‏تنبيهُ ظلّ #85 · التشغيلة 42411226107): في كلّ نوافذ Whisper المفرَّغة كان بدءُ الكلمة الأولى = بدءَ النافذة
#    تماماً (‏المنشور − 300) فيمرّ شرطُ ≤300م.ث دائماً عند حدّه. فإن قلّ |بدءُ أوّل كلمةٍ مطابقة − بدءِ النافذة| عن هذا فالشاهدُ غيرُ حاسم.
#    تشديدٌ في هذا الباب وحدَه (‏لا في `_whisper_check`).
WIT_MIN_FROM_WINDOW_MS = 50


def _span_overlap(x, y) -> float:
    lo, hi = max(x[0], y[0]), min(x[1], y[1])
    short = min(x[1] - x[0], y[1] - y[0])
    return max(0, hi - lo) / short if short > 0 else 0.0


def other_performance(ayah: int, am, occ, anchors: dict):
    """الأداءُ الآخرُ المقيس للآية (‏الشرط ٣) أو None. `am=[بدء،نهاية]` مِرساةُ الآية، `occ` أداءاتُها [[بدء،نهاية،جودة]…]،
    و`anchors` كلُّ مراسي السورة {آية: [مِرساة، جودة، أداءات]} لاستبعاد ما تفسّره آيةٌ أخرى."""
    try:
        a0, a1 = int(am[0]), int(am[1])
    except (TypeError, ValueError, IndexError):
        return None
    if a1 <= a0:
        return None
    others = []
    for b, rec in (anchors or {}).items():
        if str(b) == str(ayah) or not isinstance(rec, list) or len(rec) < 2 or not rec[0] or rec[1] is None:
            continue
        try:
            if float(rec[1]) >= MIN_Q and int(rec[0][1]) > int(rec[0][0]):
                others.append((int(rec[0][0]), int(rec[0][1])))
        except (TypeError, ValueError, IndexError):
            continue
    for o in occ or []:
        try:
            o0, o1, q = int(o[0]), int(o[1]), float(o[2])
        except (TypeError, ValueError, IndexError):
            continue
        if q < REPEAT_OCC_Q or o1 <= o0:
            continue
        before, after = o0 < a0 - TOL_MS, (o0 >= a1 - TOL_MS and o0 > a0 + TOL_MS)   # منفصلٌ عن المِرساة (‏المِرساةُ نفسُها ليست أداءً آخر)
        if not (before or after):
            continue
        if any(_span_overlap((o0, o1), x) > REPEAT_OTHER_OVERLAP for x in others):
            continue
        return {"startMs": o0, "endMs": o1, "q": q, "where": "before" if before else "after"}
    return None


def repeat_candidates(rows: list[dict], cmap: dict) -> dict:
    """{آية: الأداءُ الآخر} للآيات المنحرفة عن المِرساة العامّة ولها تكرارٌ مقيس (‏الشرط ٣) — وحدَها تُسأل عن الشاهد والإحصاء."""
    anc = (cmap or {}).get("anchors") or {}
    out = {}
    for r in rows:
        if r["status"] != "dev":
            continue
        rec = anc.get(str(r["ayah"]))
        if not isinstance(rec, list) or len(rec) < 3:
            continue
        o = other_performance(r["ayah"], rec[0], rec[2], anc)
        if o:
            out[r["ayah"]] = o
    return out


def repeat_plan(starts: dict, g_map: dict) -> list[int]:
    """آياتُ السورة التي يُشغَّل لها الشاهدُ والإحصاء (‏من خريطة العامّة بعد قياسها — يستعملها سيرُ العمل)."""
    return sorted(repeat_candidates(surah_rows(starts, g_map), g_map))


def _window_ok(wit, a: int, start: int) -> bool:
    """نافذةُ الشاهد المحفوظة تبدأ من البدء المنشور بحشوٍ ≤ WIT_PAD_MS (‏لا نافذةً أبكرَ تحمل ذيلَ السابقة)."""
    try:
        lo = int((((wit or {}).get("ayahs") or {}).get(str(a)) or {}).get("windowMs")[0])
    except (TypeError, ValueError, IndexError):
        return False
    return start - WIT_PAD_MS <= lo <= start


def _census_eval(cen, surah, want, cs_s, ayahs, texts):
    """{آية: (يمرّ؟, تفصيل)} من إحصاء النوافذ المحفوظ: تُعاد قاعدةُ الأقرب من كلمات النافذة، ويُشترط أن تكون النافذةُ
    نافذةَ مدخل المرشّح (‏بدءاً ونهاية) وأن يكون الصوتُ صوتَه. إحصاءٌ غيرُ صالح ⇒ لا شيء."""
    import entry_window_census as EW  # noqa: PLC0415  (‏استيرادٌ كسول: يستورد هذا الملفَّ)
    import pin_heard as PH  # noqa: PLC0415
    if not isinstance(cen, dict) or int(cen.get("surah") or 0) != surah:
        return {}, "لا إحصاءَ لهذه السورة"
    if cen.get("sha256") != want:
        return {}, f"إحصاءٌ على صوتٍ آخر ({str(cen.get('sha256'))[:8]}) لا صوتِ المرشّح ({str(want)[:8]})"
    if cen.get("model") not in PH.W_MODELS or cen.get("computeType") != "float32":
        return {}, f"الإحصاءُ يلزمه {PH.W_MODELS} بـfloat32 (‏وجد {cen.get('model')}/{cen.get('computeType')})"
    res, ents = {}, cen.get("entries") or {}
    for a in ayahs:
        rec = ents.get(str(a))
        if not isinstance(rec, dict):
            res[a] = (False, {"reason": "لا إحصاءَ لمدخل هذه الآية"})
            continue
        if rec.get("startMs") != cs_s[a][0] or rec.get("endMs") != cs_s[a][1]:
            res[a] = (False, {"reason": f"نافذةُ الإحصاء [{rec.get('startMs')},{rec.get('endMs')}] ليست مدخلَ المرشّح "
                                        f"[{cs_s[a][0]},{cs_s[a][1]}]"})
            continue
        try:
            r = EW.judge_entry(a, PH._norm_words(rec.get("words")), texts)
        except (KeyError, ValueError) as e:                    # نصٌّ مرجعيٌّ ناقص ⇒ لا حكم
            res[a] = (False, {"reason": f"تعذّر حكمُ المدخل: {e}"})
            continue
        res[a] = (r["verdict"] == "pass", {k: r.get(k) for k in ("verdict", "reason", "simSelf", "simNearestOther", "nearestOther",
                                                                   "gap", "words", "heard", "detail")})
    return res, None


def repeat_rescue(s: int, rows: list[dict], g_map: dict, cs_s: dict, want, riwaya, wit, cen, ref_words=None, texts=None) -> dict:
    """يرفع آياتِ `rows` المنحرفةَ المكرَّرةَ المشهودةَ إلى status=witnessed_repeat (‏في مكانها) ويُرجع دليلَ كلّ مرشَّحةٍ {آية: دليل}.
    الدليلُ: التفريغُ والثقةُ والفرقُ (‏Whisper − البدء المنشور) ونتيجةُ الإحصاء والأداءُ الآخرُ المقيس. بلا مرشَّحةٍ ⇒ {}."""
    cands = repeat_candidates(rows, g_map)
    if not cands:
        return {}
    starts = {a: v[0] for a, v in cs_s.items()}
    ayahs = sorted(cands)
    wres, bad_w = ({}, "لا شاهدَ Whisper")
    if wit:
        wres, bad_w = _witness_eval(wit, s, g_map, want, riwaya, starts, ayahs, ref_words)
    cres, bad_c = ({}, "لا إحصاءَ للنوافذ")
    if cen:
        try:
            if texts is None:
                import entry_window_census as EW  # noqa: PLC0415
                texts = EW.surah_texts(riwaya, s)
            cres, bad_c = _census_eval(cen, s, want, cs_s, ayahs, texts)
        except (SystemExit, Exception) as e:                   # noqa: BLE001  نصُّ السورة المرجعيّ غيرُ متاح ⇒ يُغلق (لا إحصاءَ)
            cres, bad_c = {}, f"تعذّر تحميلُ نصّ السورة المرجعيّ: {e}"

    by_ayah = {r["ayah"]: r for r in rows}
    ev = {}
    for a in ayahs:
        winfo = str(wres.get(a, (False, bad_w))[1])
        m = re.search(r"[Ww]hisper (\d+) (?:· CTC|وأقربُ)", winfo)
        try:
            lo_w = int((((wit or {}).get("ayahs") or {}).get(str(a)) or {}).get("windowMs")[0])
        except (TypeError, ValueError, IndexError):
            lo_w = None
        from_window = (int(m.group(1)) - lo_w) if (m and lo_w is not None) else None
        stuck = from_window is None or abs(from_window) < WIT_MIN_FROM_WINDOW_MS
        w_ok = bool(wres.get(a, (False,))[0]) and _window_ok(wit, a, starts[a]) and not stuck
        c_ok = bool(cres.get(a, (False,))[0])
        cinfo = cres.get(a, (False, {"reason": bad_c}))[1]
        words = (((wit or {}).get("ayahs") or {}).get(str(a)) or {}).get("words") or []
        ok = w_ok and c_ok
        ev[a] = {"passed": ok, "witnessOk": w_ok, "censusOk": c_ok, "startMs": starts[a], "anchorMs": by_ayah[a]["anchorMs"],
                 "devMs": by_ayah[a]["devMs"], "otherPerformance": cands[a],
                 "witness": {"detail": winfo[:300], "whisperMs": int(m.group(1)) if m else None,
                             "diffMs": (int(m.group(1)) - starts[a]) if m else None,
                             "windowMs": ((((wit or {}).get("ayahs") or {}).get(str(a)) or {}).get("windowMs")),
                             "windowOk": _window_ok(wit, a, starts[a]),
                             "wordMinusWindowMs": from_window, "stuckToWindow": stuck,
                             "heard": " ".join(str(x.get("w", "")) for x in words)[:400]},
                 "census": cinfo}
        if ok:
            by_ayah[a]["status"] = REPEAT_STATUS
            by_ayah[a]["repeat"] = {"otherPerformance": cands[a], "witness": winfo[:200]}
    return ev


def judge(cand_idx: dict, pub_idx: dict | None, cand_sha: str, maps: dict,
          maps_r: dict | None = None, witness: dict | None = None,
          dual: dict | None = None, ref_words=None,
          rwit: dict | None = None, rcensus: dict | None = None, texts=None) -> dict:
    """حكمُ البوّابة كاملاً من المرشّح والمنشور والخرائط ({سورة: compact_map}).
    يُرجع {"ok": bool, "reason": str|None, "required": [...], "modified": [...], "sample": [...],
            "surahs": {س: {"reason":..., "rows":[...]}}, "dual": {س: دليل}}.
    الباب الثاني (‏`maps_r` خرائطُ نموذج التلاوة · `witness` {سورة: مخرَجُ whisper_witness} · `dual` قائمةٌ تُعطى بدل الملفّ):
    لا يمسّ إلا سورةً **معدّلةً** لقارئٍ مسمّىً في `heard_dual.txt`؛ وما سواها بالشيفرة القديمة حرفاً.
    الباب الثالث (‏`rwit` {سورة: شاهدُ Whisper} · `rcensus` {سورة: إحصاءُ النوافذ} · `texts` نصوصُ السورة المرجعيّة تُعطى بدل المستودع):
    لا يمسّ إلا **الآيةَ المنحرفةَ** عن المِرساة العامّة في المسار القديم ولها تكرارٌ مقيس؛ ودليلُه في `out["repeat"]`."""
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
           "sample": sample, "surahs": {}, "sampleFindings": [], "version": VERSION, "dual": {}, "repeat": {}}
    dual_set = dual_surahs(cand_idx, dual)
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
            out["surahs"][str(s)] = {"reason": why, "rows": dv["rows"]}
            out["dual"][str(s)] = dv["evidence"]
            if why:
                sink.append(f"س{s}: {why}")
            continue
        rows = surah_rows({a: v[0] for a, v in cs[s].items()}, m)
        if any(r["status"] == "dev" for r in rows):          # ⭐ الباب الثالث: آياتٌ منحرفةٌ مكرّرةٌ مشهودة (‏تُرفع في مكانها)
            ev = repeat_rescue(s, rows, m, cs[s], want, cand_idx.get("riwaya"), (rwit or {}).get(s) or (rwit or {}).get(str(s)),
                               (rcensus or {}).get(s) or (rcensus or {}).get(str(s)), ref_words, texts)
            if ev:
                out["repeat"][str(s)] = {str(a): v for a, v in ev.items()}
        why = surah_verdict(rows)
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
    rwit = {int(k): v for k, v in (rep.get("repeatWitness") or {}).items()}
    rcen = {int(k): v for k, v in (rep.get("repeatCensus") or {}).items()}
    try:
        j = judge(cand_idx, pub_idx, cand_sha, maps, maps_r, wit, rwit=rwit, rcensus=rcen)
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
