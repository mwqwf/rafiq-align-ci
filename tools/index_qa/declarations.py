#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""إعلاناتُ الغياب في ترويسة الفهرس — **وحدةٌ مشتركةٌ واحدة** لكلّ أداةٍ تكتب ترويسةً فوق أصلٍ يحمل إعلاناً.

أمرُ القائد (‏2026-11-10 · طلب توريث `drop_ayahs`): «يكون التوريثُ بالدالّة المشتركة نفسها التي في #102 وpin_heard،
لا بنسخةٍ ثالثة». فنُقلت هنا الدوالُّ كما هي حرفاً من موضعيها، ويستوردها الثلاثة:
  ‏`drop_surah`  ← `prior_declarations` و`merged_op` (‏#102: سجلٌّ لكلّ سورةٍ في `transform.declarations`)
  ‏`pin_heard`   ← `declared_absent` و`inherit_declaration` (‏#97: `dropSurah` ورمزُه ونصُّه ومنشؤه حرفاً)
  ‏`drop_ayahs`  ← الأربعُ كلُّها (‏يرث إعلانَ الأصل ويُضيف سجلَّ سورته في `declarations`)

ولا يُرخى بها حارس: ما كان يُردّ في موضعه يُردّ هنا بالنصّ نفسه.
"""
from __future__ import annotations

import re

DECL_FIELDS = ("reasonCode", "reasonUser", "reason")


def _surah_of(aid):
    return int(str(aid).split(":")[0])


def op_surahs(op, name):
    """سورُ مقطعٍ واحدٍ من `op` (‏`drop_surah:` أو `declare_gap:`) — المقاطعُ تفصلها `|`."""
    out = set()
    for seg in str(op or "").split("|"):
        seg = seg.strip()
        if seg.startswith(name + ":"):
            out |= {int(x) for x in re.findall(r"\d+", seg[len(name) + 1:])}
    return out


def prior_declarations(idx):
    """كلُّ إعلانٍ في ترويسة الأصل، سورةً سورة: {"س": {"op", "reasonCode", "reasonUser", "reason"}}.

    ⛔ العطبُ المقيس (‏akri_qalun.b99e3573 · 2026-11-10): الأصلُ `drop_surah:4|declare_gap:24`، وإسقاطُ
    س10 وس37 برمزٍ غير SOURCE_TRUNCATED كان يكتب ترويسةً جديدة بحقلٍ واحدٍ للرمز ⇒ إمّا أن يُمحى
    إعلانُ ذيل س24 وإسقاطُ س4، وإمّا أن يُكتب للسور كلِّها رمزٌ واحدٌ لا يصف إلا بعضَها.
    ⇒ الإعلانُ سجلٌّ لكلّ سورةٍ في `transform.declarations`: ما حمله الأصلُ في هذا الحقل يُنقل **حرفاً**،
    وما لم يحمله يُشتقّ من حقول الأصل العليا التي كانت وحدَها تصفه يومَ كُتب (‏`op` و`dropSurah`)."""
    tr = idx.get("transform") if isinstance(idx.get("transform"), dict) else {}
    if not tr:
        return {}
    have = tr.get("declarations")
    if have is not None and not isinstance(have, dict):
        raise SystemExit("⛔ transform.declarations في الأصل ليس قاموساً — لا يُورَّث ما لا يُقرأ")
    out = {str(k): dict(v) for k, v in (have or {}).items()}
    top = {f: tr[f] for f in DECL_FIELDS if tr.get(f)}
    kinds = [("drop_surah", op_surahs(tr.get("op"), "drop_surah")),
             ("declare_gap", op_surahs(tr.get("op"), "declare_gap")),
             ("drop_surah", {int(x) for x in (tr.get("dropSurah") or [])})]
    for kind, ss in kinds:
        for s in sorted(ss):
            if str(s) not in out:
                out[str(s)] = {"op": kind, **top}
    return out


def merged_op(decls):
    """`op` يضمّ كلَّ إعلانٍ قديمٍ وجديد: `drop_surah:4,10,37|declare_gap:24`."""
    parts = []
    for kind in ("drop_surah", "declare_gap"):
        ss = sorted(int(s) for s, d in decls.items() if d.get("op") == kind)
        if ss:
            parts.append(kind + ":" + ",".join(str(n) for n in ss))
    return "|".join(parts)


def declared_absent(idx, surah=None):
    """السورُ المعلَنةُ الغيابِ في ترويسة الأصل: `transform.dropSurah` ∪ مجموعاتُ `drop_surah:` في `op`.

    ⛔ يُردّ: تثبيتُ سورةٍ معلَنةِ الغياب · إعلانٌ لسورةٍ لها مداخلُ في الأصل · إعلانٌ بلا `reasonCode` و`reasonUser`
    (‏فلا يُورَّث إعلانٌ لا يُعرض سببُه على المستخدم)."""
    tr = idx.get("transform") if isinstance(idx.get("transform"), dict) else {}
    declared = {int(s) for s in (tr.get("dropSurah") or [])}
    for group in re.findall(r"drop_surah:([\d,\s]+)", str(tr.get("op") or "")):
        declared.update(int(s) for s in re.findall(r"\d+", group))
    if not declared:
        return []
    if surah is not None and surah in declared:
        raise SystemExit(f"⛔ س{surah} معلَنةُ الغياب في الأصل — لا يُثبَّت ما لا مدخلَ له")
    present = {_surah_of(e["ayahId"]) for e in idx.get("entries") or []}
    if declared & present:
        raise SystemExit(f"⛔ إعلانُ الغياب يسمّي سوراً لها مداخل في الأصل: {sorted(declared & present)}")
    if not tr.get("reasonCode") or not tr.get("reasonUser"):
        raise SystemExit("⛔ إعلانُ الغياب في الأصل بلا reasonCode وreasonUser — لا يُورَّث إعلانٌ بلا سببٍ ظاهر")
    return sorted(declared)


def inherit_declaration(idx, key, live_sha):
    """حقولُ التحويل الجديد التي تحمل إعلانَ الغياب الموروث كما يحمله `splice_surah`:
    `dropSurah` (‏السورُ المعلَنة وحدَها، لا يُضاف إليها شيء) و`reasonCode`/`reasonUser` بنصّهما حرفاً،
    والمنشأ: `fromKey`/`fromSha256` هو الأصلُ المنشور الذي صدر عنه الإعلان (‏شرطُ `promote.inherited_drops`
    الذي لا يُمسّ)، والأصلُ المرحليُّ المباشر يُسجَّل في `stagedFromKey`/`stagedFromSha256`.
    بلا إعلانٍ في الأصل ⇒ `fromKey` = المفتاحُ نفسُه كما كان حرفاً."""
    tr = idx.get("transform") if isinstance(idx.get("transform"), dict) else {}
    out = {"fromSha256": live_sha, "fromKey": key}
    for k in ("reasonCode", "reasonUser"):
        if tr.get(k):
            out[k] = tr[k]
    drops = declared_absent(idx)
    if not drops:
        return out
    out["dropSurah"] = drops
    if key.startswith("timings-staging/"):
        origin, origin_sha = str(tr.get("fromKey") or ""), str(tr.get("fromSha256") or "")
        want = f"timings/{idx.get('riwaya')}/{idx.get('reciterId')}.jz"
        if origin != want or not re.fullmatch(r"[0-9a-f]{64}", origin_sha):
            raise SystemExit(f"⛔ الأصلُ المرحليّ يحمل إعلانَ غيابٍ ومنشؤه ليس المنشورَ {want} ببصمةٍ كاملة ({origin!r}) "
                             "— لا يُورَّث إعلانٌ مجهولُ المنشأ")
        out.update(fromKey=origin, fromSha256=origin_sha, stagedFromKey=key, stagedFromSha256=live_sha)
    return out
