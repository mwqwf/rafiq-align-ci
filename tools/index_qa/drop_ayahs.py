#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يحجب **آياتٍ غائبةً في وسط سورةٍ حاضرة** من فهرسٍ منشورٍ ويعلنها بسببها — بدل إسقاط السورة كلّها.

    python tools/index_qa/drop_ayahs.py --key timings/hafs/x.jz --sha 82151d14 \\
        --ayahs "79:15,79:17,79:18" --evidence ev.json --reason "…قياس…" \\
        --reason-user "تسجيلُ هذه السورة ينقصه بعضُ آياتها." --reason-code SOURCE_TRUNCATED --yes

⭐ **سببُه (أمرُ المالك 2026-10-31 · cmsg_01SnWBBbg8UvScqE3YMKdPHaAmmNARSqWMUt85wRaf6dSw):**
«إن كنتم ترون طريقة أفضل من الإسقاط فطبّقوه وصحّحوا القاعدة». كانت قاعدةُ 2026-10-02: البترُ في
أوّل السورة أو آخرها يُعلَن، وفي الوسط تُلغى السورةُ بأكملها. والجديد: تُحذف مداخلُ الآيات
الغائبة **وحدَها** (‏النصُّ الصوتيُّ لا يُحرَّف: آيةٌ بلا صوتٍ لها لا مدخلَ لها) وتُعلن بسببها.

**ما يفعله بالضبط** (‏ولا شيءَ غيره):
1. يتحقّق من بصمة المنشور، ويشترط أن تكون السورةُ في الأصل **تامّةَ المداخل**.
2. يحذف مداخلَ الآيات المسمّاة وحدَها. ⛔ **`startMs`/`endMs` لكلّ مدخلٍ باقٍ لا يُمسّ** (‏لا تُمَدّ الجارة)
   — إلا بـ`--aligned a<سورة>.json` من `ctc_gapsplit --absent-ayahs`: حدودُ الجارات مقيسةٌ بنافذة CTC
   بنصوص الحاضرات وحدها (‏المحاذي القديمُ عصرها بين الغائبات)، فتُطبَّق بحرّاسها وتُعلَن السورةُ بـ`ctc-gapsplit-1`.
3. يضيف المعرّفات إلى `missing.ids` معدودةً تحت `source_truncated`.
4. يكتب `transform.truncatedGaps[س] = {absent, reason, evidence}` و`op` يحمل `declare_gap:س` مع
   `reasonCode = SOURCE_TRUNCATED` و`reasonUser`، ويحمل إعلاناتِ الذيل الموروثة (‏`carried_declared_tails`).
5. يرفع إلى `timings-staging/{riwaya}/{id}.{sha8}.jz` — **ولا يمسّ المنشور**.

⛔ **حُرّاسُه** (‏وما لم يجتزها لا يُرفع شيء):
- لا أولى السورة ولا آخرتها (‏تلك بابُ الصدر/الذيل: `truncate_tail.py`).
- لا يُحجب أكثر من **ربع** آيات السورة، وإلا فالإسقاطُ الكامل (‏`drop_surah.py`).
- لكلّ آيةٍ دليلٌ في ملفّ `--evidence`: `{"79:15": {"method": "ctc_window|whisper", "detail": "نصّ قياس"}}`.
- `--reason-code` لا يقبل إلا `SOURCE_TRUNCATED` أو `TIMING_UNDER_REPAIR` (‏قائمةٌ مغلقةٌ على رمزين) و`--reason-user` إلزاميٌّ بلا كلماتٍ إداريّة.
- ⭐ `TIMING_UNDER_REPAIR` (‏آياتٌ منشورةٌ يُسمع في مدخلها صوتُ آيةٍ أخرى فتُحجب مؤقّتاً إلى أن يُصلح توقيتُها — ليس بتراً في المصدر):
  يشترط لكلّ آيةٍ في ملفّ الدليل، فوق method وdetail، `"heard": {"witness": "…", "runId": 12345, "text": "نصّ ما سُمع"}`؛
  ويُسجَّل الغيابُ تحت `byReason.timing_under_repair` لا `source_truncated` (‏فلا يُعفى من عتبة الغياب غيرِ المعلَّل). ولا يُخلط الرمزان في ترويسةٍ واحدة.
- ⭐ دليلُ «نهاية المدخل» (‏`"kind": "end"` · موافقةُ القائد 2026-11-10): لآيةٍ بدؤها سليمٌ ونهايةُ مدخلها في صوت آيةٍ أخرى.
  مع TIMING_UNDER_REPAIR وحدَه، ويلزمه فوق ما سبق `method=whisper` و`probe = {ayah, heardAyah, endMs}` و`witnesses` =
  {تشغيلة: سجلُّ الشاهد}: شاهدان متمايزان يُحمَّلان من مصدرهما ويطابقان المكتوبَ حرفاً، وبصمتُهما audioSha256 للسورة، و`endMs`
  نهايةُ المدخل المنشور، ويسمع كلٌّ منهما عند آخر لحظةٍ منه نصَّ heardAyah لا نصَّ الآية (‏`timing_repair.end_evidence_error`).
  وكلُّ قيود هذا الباب باقيةٌ عليه كما هي (‏الربع · لا الأولى ولا الأخيرة · reasonUser · دليلٌ لكلّ آية).
- الناتجُ يجتاز `promote.declared_truncated_gaps` قبل الرفع.
⚖️ **ولا يُعفي من شيء**: المرشّحُ يمرّ بعده ببوّابات الترقية كلّها.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                 # noqa: BLE001
        pass

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

_BANNED = ("إذن المالك", "أمر المالك", "بإذنٍ نصّيّ", "بإذن نصي", "المشرف", "المالك", "github-")
METHODS = ("ctc_window", "whisper")


def _key(aid: str):
    s, a = str(aid).split(":")
    return int(s), int(a)


def parse_ayahs(spec: str):
    """«79:15,79:17» ⇒ {79: [15, 17]} — ويُردّ المكرّر وما خرج عن المصحف."""
    import drop_surah
    counts = drop_surah.SURAH_AYAHS
    out: dict[int, list[int]] = {}
    seen = set()
    for item in [x for x in str(spec or "").replace("،", ",").replace(" ", ",").split(",") if x]:
        try:
            s, a = _key(item)
        except ValueError:
            raise SystemExit(f"⛔ --ayahs بصيغة سورة:آية مثل 79:15 لا {item!r}")
        if not 1 <= s <= len(counts) or not 1 <= a <= counts[s - 1]:
            raise SystemExit(f"⛔ آيةٌ خارج المصحف: {item}")
        if (s, a) in seen:
            raise SystemExit(f"⛔ آيةٌ مكرّرة: {item}")
        seen.add((s, a))
        out.setdefault(s, []).append(a)
    if not out:
        raise SystemExit("⛔ --ayahs فارغ")
    return {s: sorted(v) for s, v in out.items()}


RETIME_KEYS = {"startMs", "endMs", "conf", "confBand", "startApprox"}
RETIME_ENGINE = "ctc-gapsplit-1"


def _band(conf: float) -> str:
    return "HIGH" if conf >= 0.8 else ("MED" if conf >= 0.5 else "LOW")


def apply_retimed(ents: list, s: int, absent: list, retimed: dict) -> list:
    """يطبّق حدودَ الجارات المقيسة بنافذة CTC على مداخل السورة `s` (‏`retimed`: «س:آ» ⇒ {startMs,endMs,conf,snapped}).

    ⛔ حرّاسُه: الجارةُ حاضرةٌ غيرُ محجوبة وداخلَ [أدنى المحجوب-1 ، أعلى المحجوب+1] وحدَها · حدّا النافذة
    (بدءُ أوّل جارةٍ ونهايةُ آخرها) لا يتحرّكان · الحدودُ صاعدةٌ لا تتداخل في السورة كلّها بعد التطبيق.
    ولا يُغيَّر في المدخل إلا `RETIME_KEYS`."""
    lo, hi = min(absent) - 1, max(absent) + 1
    mine = {k: v for k, v in (retimed or {}).items() if _key(k)[0] == s}
    out, seen = [], set()
    for e in ents:
        ss, a = _key(e["ayahId"])
        r = mine.get(e["ayahId"]) if ss == s else None
        if r is None:
            out.append(e)
            continue
        if a in absent or not lo <= a <= hi:
            raise SystemExit(f"⛔ {e['ayahId']}: لا تُعاد محاذاةُ غير جارات النافذة [{s}:{lo}–{s}:{hi}] ولا المحجوبة")
        st, en = r.get("startMs"), r.get("endMs")
        if type(st) is not int or type(en) is not int or not 0 <= st < en:
            raise SystemExit(f"⛔ {e['ayahId']}: حدودٌ غيرُ سويّة {st}→{en}")
        if (a == lo and st != e["startMs"]) or (a == hi and en != e["endMs"]):
            raise SystemExit(f"⛔ {e['ayahId']}: حدُّ النافذة الخارجيُّ لا يتحرّك (‏من الأب نفسِه)")
        n = dict(e)
        n["startMs"], n["endMs"] = st, en
        if r.get("conf") is not None:
            n["conf"] = round(float(r["conf"]), 3)
            n["confBand"] = _band(float(r["conf"]))
        if r.get("snapped") is False:
            n["startApprox"] = True
        seen.add(e["ayahId"])
        out.append(n)
    miss = sorted(set(mine) - seen, key=_key)
    if miss:
        raise SystemExit(f"⛔ جاراتٌ مسمّاةٌ بلا مدخلٍ في الأصل: {miss}")
    prev = -1
    for e in out:
        if _key(e["ayahId"])[0] != s or _key(e["ayahId"])[1] in absent or not lo - 1 <= _key(e["ayahId"])[1] <= hi + 1:
            continue                  # المحجوبةُ تُحذف؛ ولا يُحاكَم إلا ما لامسته النافذةُ (‏ما خارجها لم يُمسّ)
        if e["startMs"] < prev:
            raise SystemExit(f"⛔ {e['ayahId']}: يبدأ {e['startMs']} قبل نهاية سابقتِه {prev} بعد إعادة المحاذاة")
        prev = e["endMs"]
    return out


def drop_ayahs(idx: dict, ayahs: dict, evidence: dict, *, reason: str, reason_user: str,
               reason_code: str, from_sha: str, from_key: str, retimed: dict | None = None,
               already_absent: bool = False, witnessed: dict | None = None,
               end_loader=None, end_ref_words=None) -> dict:
    """يُعيد فهرساً جديداً حُجبت منه الآياتُ المسمّاة ومعلَنةً، أو يرفع SystemExit بالسبب.

    ‏`retimed` (اختياري · أمر 2026-10-31): حدودُ الجارات المقيسةُ بـCTC على نافذةٍ بنصوص الحاضرات وحدها
    (‏`ctc_gapsplit --absent-ayahs`) — فالمحاذي القديمُ «عصر» الغائباتِ بين جاراتها فكانت حدودُها خاطئة.
    ‏تُطبَّق قبل الحجب، وتُعلَن السورةُ بمحرّك `ctc-gapsplit-1` فيلزمها الإحصاءُ الشامل.

    ‏`already_absent` (أمر القائد 2026-11-07 · `ctc_splice mode=heard absent_ayahs`): الآياتُ المسمّاةُ **غائبةٌ أصلاً** من
    الفهرس المُدخَل (‏سورةٌ بُنيت من مراسٍ مسموعةٍ فقط من مصدرٍ ينقصه وسطُها، ولم يكن لها في الأب مدخلٌ أصلاً)،
    فلا مدخلَ يُحذف: يُعلَن الغيابُ بدليله وتُتحقَّق تسويتُه بالترويسة. وأيُّ حارسٍ مما فوق يبقى كما هو؛ ويُشدَّد
    بأن تكون مداخلُ السورة **كلَّ آياتها ناقص المسمّاة بالضبط**، وأن تكون المسمّاةُ مسجَّلةً في `missing.ids`
    و`byReason.source_truncated`. الافتراضُ False = السلوكُ الأصليّ حرفاً (‏سورةٌ تامّةٌ في الأصل تُحذف منها المسمّاة)."""
    import drop_surah
    import promote
    if reason_code not in promote.GAP_REASON_CODES:                    # ⛔ القائمةُ مغلقةٌ على رمزين لا ثالثَ لهما
        raise SystemExit("⛔ --reason-code لهذا الباب SOURCE_TRUNCATED أو TIMING_UNDER_REPAIR وحدَهما")
    reason_key = promote.GAP_REASON_CODES[reason_code]
    if witnessed and not already_absent:                               # ⛔ (ctc-absent-witnessed-1) لا يُكتب غيابٌ مشهودٌ إلا لسورةٍ بُنيت من المسموع
        raise SystemExit("⛔ witnessedAbsent لا يكون إلا مع --already-absent (‏سورةٌ بُنيت من المسموع)")
    if not (reason_user or "").strip():
        raise SystemExit("⛔ --reason-user إلزاميّ: التطبيقُ لا يعرض سببَ النقص بدونه")
    for w in _BANNED:
        if w in reason or w in reason_user:
            raise SystemExit(f"⛔ السببُ يحمل «{w}» — والحقلُ يُعرض للمستخدم")
    counts = drop_surah.SURAH_AYAHS_OF(idx)
    tr0 = idx.get("transform") if isinstance(idx.get("transform"), dict) else {}
    # ⛔ (‏2026-11-10 · 3siri bc63afc4 · #100) الترويسةُ الجديدة تُكتب من الصفر، فكان إعلانُ إسقاطِ سورةٍ كاملة في الأصل
    #    (‏`dropSurah` أو op=drop_surah:…) يُمحى بصمت ثمّ يردّه index_gate بـ«سورٌ غائبةٌ كلّياً».
    # ⭐ (‏أمر القائد 2026-11-10 · الكردي س4 فوق إعلان س55) يُورَّث الإعلانُ الآن **بالدوالّ المشتركة نفسها** التي
    #    في drop_surah (#102) وpin_heard (‏`declarations.py`)، بشروطٍ مجتمعة وإلا فالردُّ القديم:
    #    ① لا تُطلب آيةٌ من سورةٍ معلَنةٍ هي نفسُها (‏ولا من سورةٍ لها في الأصل سجلُّ إعلانٍ أيّاً كان) ⇒ الردُّ القديم حرفاً.
    #    ①ب سورةٌ محجوبةٌ كاملةً في الأصل لا يُحجب منها شيءٌ (‏تُردّ ①)؛ وسواها يورَّث إعلانُه سواءٌ أكانت المسمّاةُ غائبةً أصلاً أم محذوفةً الآن.
    #    ② منشأُ الإعلان المنشورُ ببصمته الكاملة (‏`inherit_declaration`: والأصلُ المرحليّ يسمّي منشأه وإلا رُدّ).
    #    ③ `dropSurah` و`reasonCode`/`reasonUser` العليا تُنقل حرفاً (‏شرطُ `promote.inherited_drops`)، و`declarations`
    #       يُنقل حرفاً (‏`prior_declarations`) ويُضاف إليه سجلُّ كلّ سورةٍ محجوبٍ منها برمزها هي (‏فلا يُخلط رمزان
    #       في حقلٍ واحد: `promote.surah_declaration` يقرأ رمزَ السورة من سجلّها وحدَه).
    #    و`op` يبقى `declare_gap:…` (‏لا `merged_op`): فـ`op` يبدأ بـdrop_surah يجعل index_gate يعدّه إسقاطاً جديداً
    #    فيتخطّى تحقّقَ `inherited_drops` من الأصل المنشور — والتوريثُ هنا يمرّ به كما يمرّ إعلانُ pin_heard.
    import declarations
    _op0 = idx.get("transform") if isinstance(idx.get("transform"), str) else str(tr0.get("op") or "")
    inherit = None
    if tr0.get("dropSurah") or _op0.startswith("drop_surah") or "drop_surah:" in _op0:
        _named = sorted(declarations.op_surahs(_op0, "drop_surah")
                        | {int(x) for x in (tr0.get("dropSurah") or []) if str(x).isdigit()})
        if not isinstance(idx.get("transform"), dict) or set(ayahs) & set(_named):
            raise SystemExit(f"⛔ الأصلُ يعلن إسقاطَ سورٍ كاملة {_named} (‏{_op0 or 'dropSurah'}) ولا تورّث هذه الأداةُ ذلك الإعلان — "
                             "الحجبُ عليه يمحوه بصمت. أصلِح الآياتِ بـpin_heard (‏يورّث الإعلانَ حرفاً) أو ابدأ من أصلٍ بلا إسقاط")
        # ⭐ (أمر القائد 2026-11-10 · benkirane_warsh 13:27–30 و3siri 36:46–52) الحجبُ بحذف مداخلَ حاضرةٍ في سورةٍ أخرى
        #    لم يعد مردوداً هنا: يُورَّث إعلانُ الإسقاط القائم حرفاً (‏الدوالّ المشتركة أدناه) بدل الرفض، وتقبل
        #    `promote.inherited_drops` الناتجَ لأنّ ما يفقده المنشورُ هو المحجوبُ المعلَنُ بدليله وحدَه (‏انظر استثناءها).
        #    ولا يُلتفّ بـ`--already-absent`: يبقى بابُه لما كان غائباً أصلاً فحسب.
        prior = declarations.prior_declarations(idx)
        clash = sorted(set(ayahs) & {int(k) for k in prior})
        if clash:
            raise SystemExit(f"⛔ س{clash}: لها في الأصل سجلُّ إعلانٍ ({[prior[str(k)] for k in clash]}) — "
                             "إعلانٌ جديدٌ عليها يمحو سجلَّها. ابدأ من فهرسها قبل الإعلان")
        inherit = {"fields": declarations.inherit_declaration(idx, from_key, from_sha), "prior": prior}
    ents = list(idx.get("entries") or [])
    recs, gone = {}, set()
    orig_all = {e["ayahId"]: e for e in ents}
    for s, absent in sorted(ayahs.items()):
        n = counts[s - 1]
        if min(absent) < 2 or max(absent) > n - 1:
            raise SystemExit(f"⛔ س{s}: لا يُحجب أولُ السورة ولا آخرُها (‏2..{n - 1}) — ذاك بابُ truncate_tail")
        if len(absent) * 4 > n:
            raise SystemExit(f"⛔ س{s}: المحجوب {len(absent)} يتجاوز ربع آيات السورة ({n}) — الإسقاطُ الكامل")
        mine = sorted(_key(e["ayahId"])[1] for e in ents if _key(e["ayahId"])[0] == s)
        if already_absent:
            want_mine = [a for a in range(1, n + 1) if a not in set(absent)]
            if mine != want_mine:
                raise SystemExit(f"⛔ س{s}: مداخلُها ({len(mine)}) ليست كلَّ آياتها ناقص المسمّاة ({len(want_mine)}) — "
                                 "لا يُعلَن غيابٌ لآيةٍ حاضرة ولا تبقى آيةٌ غائبةٌ بلا إعلان")
        elif mine != list(range(1, n + 1)):
            raise SystemExit(f"⛔ س{s} في الأصل ليست تامّة ({len(mine)}/{n}) — ليست حالةَ هذه الأداة")
        if (tr0.get("truncatedTail") or {}).get(str(s)) or (tr0.get("truncatedGaps") or {}).get(str(s)):
            raise SystemExit(f"⛔ س{s}: الأصلُ يعلن عليها ذيلاً أو حجباً — ابدأ من فهرسها قبل الإعلان")
        ev = {}
        for a in absent:
            rec = (evidence or {}).get(f"{s}:{a}")
            if (not isinstance(rec, dict) or rec.get("method") not in METHODS
                    or not str(rec.get("detail") or "").strip()):
                raise SystemExit(f"⛔ لا دليلَ قياسٍ للآية {s}:{a} (‏method من {METHODS} + detail)")
            ev[f"{s}:{a}"] = {"method": rec["method"], "detail": str(rec["detail"])}
            if "kind" in rec and reason_code != "TIMING_UNDER_REPAIR":
                raise SystemExit(f"⛔ {s}:{a}: دليلٌ بنوعٍ (kind) لا يكون إلا مع TIMING_UNDER_REPAIR")
            if reason_code == "TIMING_UNDER_REPAIR":
                if not promote.heard_evidence_ok(rec):
                    raise SystemExit(f"⛔ لا دليلَ سماعٍ للآية {s}:{a} — TIMING_UNDER_REPAIR يشترط "
                                     "heard = {witness, runId, text}: الشاهدُ ورقمُ تشغيلته ونصُّ ما سُمع")
                h = rec["heard"]
                ev[f"{s}:{a}"]["heard"] = {"witness": str(h["witness"]), "runId": h["runId"], "text": str(h["text"])}
                if "kind" in rec:
                    # ⭐ دليلُ نهاية المدخل: يُتحقَّق من مضمونه على الأصل المنشور ومن مصدر شاهدَيه (‏لا من حكمٍ مكتوب).
                    import timing_repair                              # noqa: PLC0415
                    if rec.get("kind") != timing_repair.END_KIND:
                        raise SystemExit(f"⛔ {s}:{a}: نوعُ الدليل {rec.get('kind')!r} غيرُ معروف (‏المقبول {timing_repair.END_KIND!r})")
                    if already_absent:
                        raise SystemExit(f"⛔ {s}:{a}: دليلُ نهاية المدخل لمدخلٍ منشورٍ فقط لا مع --already-absent")
                    why = timing_repair.end_evidence_error(idx, s, a, rec, end_loader, end_ref_words)
                    if why:
                        raise SystemExit(f"⛔ {s}:{a}: دليلُ نهاية المدخل مردود: {why}")
                    ev[f"{s}:{a}"].update({"kind": timing_repair.END_KIND, "probe": dict(rec["probe"]),
                                           "witnesses": {str(r): timing_repair._src_rec(w)
                                                         for r, w in sorted(rec["witnesses"].items())}})
        recs[str(s)] = {"absent": list(absent), "reason": reason_key, "evidence": ev}
        gone |= {f"{s}:{a}" for a in absent}
        if retimed:
            ents = apply_retimed(ents, s, list(absent), retimed)
    stray = sorted({_key(k)[0] for k in (retimed or {})} - set(ayahs))
    if stray:
        raise SystemExit(f"⛔ حدودٌ مُعاد قياسُها لسورٍ لا حجبَ فيها: {stray}")

    # ⭐ (ctc-absent-witnessed-1 · قرار القائد 2026-11-10) غيابٌ مشهودٌ لآياتٍ مسمّاةٍ غائبةٍ لكنّها مسموعةٌ في الخريطة: يُكتب في
    #    `transform.witnessedAbsent` باسمه وإصداره مع دليله (‏الشاهدان بتشغيلتيهما) ليعيد `heard_gate` حكمَه من المصدر.
    #    ⛔ لا يكون إلا مع `already_absent` (‏سورةٌ بُنيت من المسموع) وعلى آياتٍ مسمّاةٍ حجبُها فعلاً، بشاهدَين من تشغيلتين متمايزتين.
    wit_rec = {}
    if witnessed:
        if not already_absent:
            raise SystemExit("⛔ witnessedAbsent لا يكون إلا مع --already-absent (‏سورةٌ بُنيت من المسموع)")
        for s_k, claims in sorted(witnessed.items(), key=lambda kv: int(kv[0])):
            named = set(ayahs.get(int(s_k)) or [])
            if not isinstance(claims, dict) or not claims or not {int(a) for a in claims} <= named:
                raise SystemExit(f"⛔ س{s_k}: غيابٌ مشهودٌ لآياتٍ غيرِ محجوبةٍ بالاسم ({sorted(claims) if isinstance(claims, dict) else claims})")
            for a_k, c in claims.items():
                ws = c.get("witnesses") if isinstance(c, dict) else None
                if (not isinstance(ws, dict) or len(ws) < 2 or any(not isinstance(w, dict) for w in ws.values())):
                    raise SystemExit(f"⛔ {s_k}:{a_k}: الغيابُ المشهودُ يلزمه شاهدان من تشغيلتين متمايزتين")
            wit_rec[str(s_k)] = claims
    kept = [e for e in ents if e["ayahId"] not in gone]
    total = idx.get("ayahCount") or sum(counts)
    miss = dict(idx.get("missing") or {})
    ids = list(miss.get("ids") or [])
    if already_absent:
        # الغيابُ قائمٌ في الفهرس المُدخَل: يُتحقَّق من تسويته ولا يُزاد شيء (‏وإلا عُدّت الآيةُ مرّتين).
        if not gone <= set(ids):
            raise SystemExit(f"⛔ المسمّاةُ غيرُ مسجَّلةٍ في missing.ids: {sorted(gone - set(ids), key=_key)[:6]}")
        if int((miss.get("byReason") or {}).get("source_truncated", 0)) < len(gone):
            raise SystemExit("⛔ byReason.source_truncated لا يعدّ المسمّاةَ كلَّها — الأصلُ غيرُ متّسق")
        if len(ents) + int(miss.get("count") or 0) != total:
            raise SystemExit("⛔ الأصلُ نفسُه لا يحقّق العقد — لا يُبنى عليه")
    else:
        if set(ids) & gone:
            raise SystemExit("⛔ وسمُ الاكتمال يعدّ آياتٍ حاضرةً غائبة — الأصلُ غيرُ متّسق")
        if len(ents) + int(miss.get("count") or 0) != total:
            raise SystemExit("⛔ الأصلُ نفسُه لا يحقّق العقد — لا يُبنى عليه")
        reasons = dict(miss.get("byReason") or {})
        reasons[reason_key] = int(reasons.get(reason_key, 0)) + len(gone)
        miss.update({"count": int(miss.get("count") or 0) + len(gone), "byReason": reasons,
                     "ids": sorted(ids + sorted(gone), key=_key)})

    out = dict(idx)
    out["entries"] = kept
    out["missing"] = miss
    out["lowCount"] = sum(1 for e in kept if e.get("confBand") == "LOW")
    touched = sorted(ayahs)
    tails, keep_decl = drop_surah.carried_declared_tails(idx, kept, set(touched), reason_code, reason_user,
                                                          prior=(inherit or {}).get("prior"))
    # إعلاناتُ حجبٍ وسطيٍّ موروثةٌ لسورٍ أخرى: تُحمل كما هي بشرط أن تبقى مداخلُها مطابقة.
    old_gaps = {k: v for k, v in (tr0.get("truncatedGaps") or {}).items()
                if int(k) not in touched and isinstance(v, dict)}
    for k, v in old_gaps.items():
        have = sorted(_key(e["ayahId"])[1] for e in kept if _key(e["ayahId"])[0] == int(k))
        want = [a for a in range(1, counts[int(k) - 1] + 1) if a not in set(v.get("absent") or [])]
        if have != want:
            raise SystemExit(f"⛔ س{k}: إعلانُ الحجب الموروث لا يطابق مداخلَها — لا يُحمل كذب")
    for k, v in old_gaps.items():
        if v.get("reason") != reason_key:
            raise SystemExit(f"⛔ س{k}: الأصلُ يعلن حجباً بسبب {v.get('reason')} ولا يُخلط رمزان في ترويسةٍ واحدة "
                             f"(‏الجديد {reason_code}) — ابدأ كلَّ رمزٍ من مرشّحٍ منفصل")
    carried_gaps = sorted({int(k) for k in old_gaps})
    op = "declare_gap:" + ",".join(str(s) for s in touched)
    extra = sorted(set(keep_decl) | set(carried_gaps))
    if extra:
        op += "|declare_gap:" + ",".join(str(s) for s in extra)
    moved = sorted((k for k in (retimed or {})), key=_key)
    if moved:
        ebs = dict(out.get("engineBySurah") or {})
        for s in touched:
            ebs[str(s)] = RETIME_ENGINE        # ⇒ يلزمها الإحصاءُ الشامل (‏promote.census_surahs)
        out["engineBySurah"] = ebs
    out["transform"] = {
        **({"retimedNeighbours": moved} if moved else {}),
        **({"truncatedTail": tails} if tails else {}),
        "truncatedGaps": {**old_gaps, **recs},
        **({"witnessedAbsent": {**{k: v for k, v in ((tr0.get("witnessedAbsent") or {}) if isinstance(tr0.get("witnessedAbsent"), dict) else {}).items()
                                   if int(k) not in touched}, **wit_rec},
            "witnessedAbsentVersion": "ctc-absent-witnessed-1"} if (wit_rec or tr0.get("witnessedAbsent")) else {}),
        "op": op,
        "fromSha256": from_sha,
        "fromKey": from_key,
        "droppedEntries": 0 if already_absent else len(gone),
        "gapAyahs": len(gone),
        "reason": reason,
        "reasonUser": reason_user,
        "reasonCode": reason_code,
        "at": int(time.time() * 1000),
        "note": ("آياتٌ غائبةٌ في وسط السورة حُجبت وأُعلنت بدليلٍ لكلٍّ؛ "
                 + ("وحدودُ الجارات أُعيد قياسُها بنافذة CTC بنصوص الحاضرات وحدها." if moved
                    else "حدودُ كلّ مدخلٍ باقٍ لم تُمسّ.")),
    }
    if inherit:
        # الإعلانُ الموروث حرفاً (‏dropSurah · reasonCode/reasonUser العليا · المنشأ)، وسجلُّ كلّ سورةٍ في declarations:
        # القديمُ كما هو، والمحجوبُ منها الآن برمزها ونصّها هي.
        out["transform"].update(inherit["fields"])
        decls = {k: dict(v) for k, v in inherit["prior"].items()}
        for s in touched:
            decls[str(s)] = {"op": "declare_gap", "reasonCode": reason_code, "reasonUser": reason_user, "reason": reason}
        out["transform"]["declarations"] = decls
    if len(kept) + miss["count"] != total:
        raise SystemExit(f"⛔ اختلال العقد: {len(kept)} + {miss['count']} ≠ {total}")
    for e in kept:
        o = orig_all[e["ayahId"]]
        if e == o:
            continue
        if e["ayahId"] not in (retimed or {}) or any(e.get(k) != o.get(k) for k in (set(e) | set(o)) - RETIME_KEYS):
            raise SystemExit("⛔ تغيّر مدخلٌ باقٍ (startMs/endMs أو غيرهما) — لا يجوز")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--key", required=True)
    ap.add_argument("--sha", required=True, help="بادئةُ بصمة المنشور (تحقّق)")
    ap.add_argument("--ayahs", required=True, help="«79:15,79:17,79:18»")
    ap.add_argument("--evidence", default="", help="ملفّ JSON: دليلُ كلّ آية (‏أو من --aligned)")
    ap.add_argument("--aligned", nargs="*", default=[], help="a<سورة>.json من ctc_gapsplit --absent-ayahs: حدودُ الجارات + الدليل")
    ap.add_argument("--reason", required=True)
    ap.add_argument("--reason-user", required=True)
    ap.add_argument("--reason-code", required=True)
    ap.add_argument("--already-absent", action="store_true",
                    help="المسمّاةُ غائبةٌ أصلاً من الفهرس (‏مرشّحُ ctc_splice mode=heard الذي بُنيت سورتُه من المسموع وحده): "
                         "يُعلَن الغيابُ بدليله دون حذفِ مدخل — والمداخلُ يجب أن تساوي الآياتِ ناقص المسمّاة بالضبط")
    ap.add_argument("--yes", action="store_true", help="ارفع إلى الاختبار (الافتراض عرض)")
    a = ap.parse_args()
    ayahs = parse_ayahs(a.ayahs)
    evidence = json.loads(Path(a.evidence).read_text(encoding="utf-8")) if a.evidence else {}
    retimed, witnessed = {}, {}
    for fp in a.aligned:
        rec = json.loads(Path(fp).read_text(encoding="utf-8"))
        if sorted(rec.get("absent") or []) != sorted(ayahs.get(int(rec.get("surah", 0)), [])):
            raise SystemExit(f"⛔ {fp}: المحجوبةُ فيه تخالف --ayahs")
        retimed.update(rec.get("retimed") or {})
        evidence.update(rec.get("evidence") or {})
        if rec.get("witnessedAbsent"):
            witnessed[str(int(rec["surah"]))] = {k: {"witnesses": v.get("witnesses"), "detail": v.get("detail")}
                                                 for k, v in rec["witnessedAbsent"].items()}
    if not evidence:
        raise SystemExit("⛔ لا دليلَ: --evidence أو --aligned")
    import promote
    cl, bucket = promote.s3()
    body = cl.get_object(Bucket=bucket, Key=a.key)["Body"].read()
    live = hashlib.sha256(body).hexdigest()
    if not live.startswith(a.sha):
        raise SystemExit(f"⛔ البصمة لا تطابق: الحيّة {live[:16]} والمطلوبة {a.sha}")
    idx = json.loads(gzip.decompress(body).decode("utf-8"))
    out = drop_ayahs(idx, ayahs, evidence, reason=a.reason, reason_user=a.reason_user,
                     reason_code=a.reason_code, from_sha=live, from_key=a.key,
                     retimed=retimed or None, already_absent=a.already_absent, witnessed=witnessed or None)
    for s in ayahs:
        ok, why = promote.declared_truncated_gaps(out, s)
        if not ok:
            raise SystemExit(f"⛔ الناتجُ لا يجتاز declared_truncated_gaps (س{s}): {why}")
        print(f"declared_truncated_gaps س{s}: ✅ {why}")
    blob = gzip.compress(json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), 9)
    new_sha = hashlib.sha256(blob).hexdigest()
    target = f"timings-staging/{idx.get('riwaya')}/{idx.get('reciterId')}.{new_sha[:8]}.jz"
    print(f"من {a.key} ({live[:12]}) · " + (f"أُعلن غيابُ {out['transform']['gapAyahs']} آيةً غائبةً أصلاً" if a.already_absent
                                              else f"حُجبت {out['transform']['droppedEntries']} آيةً"))
    print(f"المداخل {len(idx['entries'])} ⇐ {len(out['entries'])} · الغياب ⇐ {out['missing']['count']}")
    print(f"إلى {target} ({len(blob)} بايت · بصمة {new_sha[:12]})")
    if not a.yes:
        print("(عرضٌ فقط — أضف --yes للرفع)")
        return
    cl.put_object(Bucket=bucket, Key=target, Body=blob, ContentType="application/gzip")
    got = cl.head_object(Bucket=bucket, Key=target)["ContentLength"]
    print(f"↑ رُفع · الدلو {got} · المحلّي {len(blob)} → {'✅' if got == len(blob) else '❌'}")


if __name__ == "__main__":
    main()
