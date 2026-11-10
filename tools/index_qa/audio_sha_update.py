# -*- coding: utf-8 -*-
"""تحديثُ بصمة الصوت (`audioSha256`) لسورةٍ أُعيدت محاذاتُها كلُّها على الملفّ الحاليّ.

تُستعمل من خطوة الدمج في `ctc_splice.yml`. القاعدة:
- سورةٌ أُعيدت **كلُّها** (‏لا `rewindow` لها، أو مداه يغطّي 1..N) تُكتب بصمةُ الملفّ المقيسةُ في تشغيلتها
  بعد التحقّق من تطابق `fileRef` المدموج بالمحاذى.
- سورةٌ أُعيدت **جزئياً** (‏`rewindow` لا يغطّي 1..N) **لا تتحدّث** بصمتُها: ما خارج المدى ما زال على
  الصوت القديم، وتحديثُ البصمة يخفي انحرافَه عن بوّابة السماع.
- قائمةُ البصمات بتخطيطَين: 114 موضعاً ثابتاً (‏السورة s في الموضع s-1) أو مضغوطةٌ على السور الحاضرة؛
  وما سواهما يُترك كما هو. لا يُمسّ حارسٌ ولا تُخفَّف عتبة؛ وبوّابةُ السماع تبقى تقارن البصمة بالمسموع.
"""
from __future__ import annotations

import re

_RANGE = re.compile(r"(\d+):(\d+)-(\d+)")


def rewindow_ranges(text):
    """«55:1-78,38:44-51/nb» ⇒ {55: {(1, 78)}, 38: {(44, 51)}} — اللاحقةُ /nb لا تغيّر المدى."""
    out = {}
    for m in _RANGE.finditer(text or ""):
        s, a, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        out.setdefault(s, set()).add((a, b))
    return out


def covers_whole(ranges, count):
    """هل تغطّي الأمداءُ 1..count متّصلةً؟"""
    need = 1
    for a, b in sorted(ranges):
        if a > need:
            return False
        need = max(need, b + 1)
    return need > count


def full_surahs(taken, rewindow, counts):
    """السورُ المأخوذةُ التي أُعيدت كلُّها: بلا rewindow لها، أو مداها يغطّي 1..N."""
    rw = rewindow_ranges(rewindow)
    return [s for s in taken if s not in rw or covers_whole(rw[s], counts[s - 1])]


def update(idx, recs, full, log=print):
    """يكتب بصمةَ `recs[s]['sha256']` للسور في `full` ويردّ السورَ المحدَّثة.

    `recs`: {سورة: سجلُّ المحاذاة (فيه fileRef وsha256)}. يرفع SystemExit إن خالف fileRef المدموجُ المحاذى."""
    sha = idx.get("audioSha256")
    present = sorted({int(e["ayahId"].split(":")[0]) for e in idx["entries"]})
    if not isinstance(sha, list):
        log("⚠️ لا قائمةَ بصمات — تُترك كما هي")
        return []
    if len(sha) == 114:
        pos = {s: s - 1 for s in range(1, 115)}
    elif len(sha) == len(present):
        pos = {s: i for i, s in enumerate(present)}
    else:
        log(f"⚠️ قائمةُ البصمات {len(sha)} والسورُ {len(present)} — تُترك كما هي")
        return []
    done = []
    for s in full:
        rec = recs[s]
        for e in idx["entries"]:
            if int(e["ayahId"].split(":")[0]) == s and e["fileRef"] != rec["fileRef"]:
                raise SystemExit(f"⛔ س{s}: fileRef المدموج {e['fileRef']} ≠ المحاذى {rec['fileRef']}")
        new = rec.get("sha256")
        if not new:
            continue
        if sha[pos[s]] and sha[pos[s]] != new:
            log(f"🔄 س{s}: بصمةُ الصوت تبدّلت عند المصدر — تُكتب المقيسة")
        sha[pos[s]] = new
        done.append(s)
    idx["audioSha256"] = sha
    return done
