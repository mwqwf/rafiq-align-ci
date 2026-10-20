# -*- coding: utf-8 -*-
"""حارسُ إطلاق بوّابة الجودة (openers + ملوح audio_qa) لمرشّح مسرح — تشديدٌ لا تليين.

أُنشئ بعد هدرٍ مقيس (2026-10-20 15:46Z): ملوحٌ أُطلقت لمرشّحٍ رُقّي قبل أن تبدأ،
وأخرى لمرشّحٍ ردّته بوّابة السماع، وأخرى لمرشّحٍ أساسُه لم يعد الحيّ.
يعيد سببَ الامتناع أو None. لا يخفّض عتبةً ولا عدد ملوح؛ يمنع الإطلاق فقط، وكلُّ حارس الترقية باقٍ كما هو.
"""
import hashlib

import heard_gate as HG


def launch_skip_reason(key, hdr, body_sha, live_manifest, frozen_text, get_json):
    """key: مفتاح المسرح · hdr: الفهرس المفكوك · body_sha: sha256 كامل لجسمه ·
    live_manifest: {(riwaya, reciterId): sha256 الحيّ} طازجاً · frozen_text: نصّ frozen.txt طازجاً ·
    get_json(k): يقرأ مفتاحاً من الدلو (فهرساً مفكوكاً أو حكماً) أو يعيد None."""
    riw, rid = hdr.get("riwaya"), hdr.get("reciterId")
    live = live_manifest.get((riw, rid))
    # (أ) مرقّى أصلاً
    if body_sha[:8] in (frozen_text or "") or (live and live == body_sha):
        return "بصمتُه هي الحيّ الآن (مرقّى أصلاً)"
    # (ب) أساسُه لم يعد الحيّ ⇒ لن يُزرع ولن يُرقّى
    tr = hdr.get("transform") or {}
    fk, fs = tr.get("fromKey"), tr.get("fromSha256")
    if isinstance(fk, str) and fk.startswith("timings/") and fs and live and fs != live:
        return f"أساسُه {fs[:8]} لم يعد الحيّ ({live[:8]})"
    # (ج) حكمُ سماعٍ مردود على بصمته بعينها (الغيابُ ليس ردّاً هنا؛ يبقى ردّاً في الترقية)
    rep = get_json(HG.state_key(key))
    if isinstance(rep, dict) and rep.get("sha256") == body_sha:
        pub = get_json(f"timings/{riw}/{rid}.jz")
        try:
            why = HG.gate_error(hdr, pub if isinstance(pub, dict) else None, body_sha, rep)
        except Exception:                                # noqa: BLE001  عطبٌ في الحساب ⇒ لا منع
            why = None
        if why:
            return "ردّته بوّابة السماع: " + str(why)[:160]
    return None
