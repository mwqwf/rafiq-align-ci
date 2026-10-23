# -*- coding: utf-8 -*-
"""إبقاء خرائط السماع الصالحة عند تبدّل بصمة الفهرس الحيّ (e6 · 2026-10-18).

خريطة السماع دالّةٌ في صوت السورة ونصّها لا في توقيتات الفهرس. فإذا رُقّي الفهرس تغيّرت بصمته وصار
تقرير state-heard «متقادماً» وإن كانت خرائطه صحيحة لكلّ سورةٍ لم يتغيّر صوتها. هذا يعيد ربط تلك الخرائط
بالحيّ الجديد بلا CTC، بالشرط نفسه الذي يحسب السورةَ «مغطّاة» في heard_pub.yml، ولا يُربط غيرُه.
⛔ لا يُربط شيءٌ عند اختلاف: بصمة الصوت المقيسة عن المعلَنة في الفهرس · رابط الملفّ · وجود المراسي ·
نسخة الصيغة · نوع التقرير. وبلا rekey صراحةً يبقى السلوك القديم حرفاً.
"""
from __future__ import annotations
import heard_gate as H


def valid_old_maps(old: dict, live_sha: str, cs: dict, want: dict, rekey: bool) -> dict:
    maps = {int(k): v for k, v in (old.get("maps") or {}).items()}
    if old.get("sha256") == live_sha:
        return maps
    if not rekey:
        return {}
    if old.get("version") != H.VERSION or old.get("kind") != "heard":
        return {}
    keep = {}
    for s, m in maps.items():
        refs = {v[2] for v in cs.get(s, {}).values()}
        if (want.get(s) and m.get("sha256") == want[s] and m.get("anchors")
                and m.get("fileRef") in refs and len(refs) == 1):
            keep[s] = m
    return keep
