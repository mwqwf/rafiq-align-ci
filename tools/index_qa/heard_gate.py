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
  (‏تشابه ≥ 0.7) يبدأ على بُعد ≤ 2000م.ث من البدء المنشور ⇒ «تكرار» (‏التسجيلُ أعاد الآية).
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
    return {"surah": heard.get("surah"), "sha256": heard.get("sha256"), "fileRef": heard.get("fileRef"),
            "totalMs": heard.get("totalMs"), "engine": heard.get("engine"),
            "anchors": {k: [v.get("anchorMs"), v.get("anchorQuality"),
                            [o[:3] for o in (v.get("occurrences") or [])]]
                        for k, v in hm.items()}}


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
            alt = any(abs(st - int(o[0])) <= REPEAT_NEAR_MS and float(o[2]) >= REPEAT_SIM for o in occ or [])
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


def judge(cand_idx: dict, pub_idx: dict | None, cand_sha: str, maps: dict) -> dict:
    """حكمُ البوّابة كاملاً من المرشّح والمنشور والخرائط ({سورة: compact_map}).
    يُرجع {"ok": bool, "reason": str|None, "required": [...], "modified": [...], "sample": [...],
            "surahs": {س: {"reason":..., "rows":[...]}}}."""
    ents = cand_idx.get("entries") or []
    cs = by_surah(ents)
    modified = modified_surahs(ents, (pub_idx or {}).get("entries") or []) if pub_idx else sorted(cs)
    sample = sample_surahs(cand_sha, [s for s in cs if s not in modified])
    required = sorted(set(modified) | set(sample))
    present = sorted(cs)
    shas = cand_idx.get("audioSha256")
    out = {"ok": False, "reason": None, "required": required, "modified": modified,
           "sample": sample, "surahs": {}, "sampleFindings": [], "version": VERSION}
    bad = []
    for s in required:
        # ⚖️ العيّنةُ (غيرُ المعدّلة) للتقرير وحده: ما يُوجد فيها يُسجَّل ولا يردّ.
        sink = bad if s in modified else out["sampleFindings"]
        m = maps.get(s) or maps.get(str(s))
        if not m:
            sink.append(f"س{s}: لا خريطةَ سماع")
            continue
        if isinstance(shas, list) and len(shas) == len(present):
            want = shas[present.index(s)]
            if want and m.get("sha256") != want:
                sink.append(f"س{s}: الصوتُ المسموع ({str(m.get('sha256'))[:8]}) غيرُ صوت المرشّح ({str(want)[:8]})")
                continue
        refs = {v[2] for v in cs[s].values()}
        if m.get("fileRef") and refs and m["fileRef"] not in refs:
            sink.append(f"س{s}: سُمع {m['fileRef']} والمرشّحُ يشير إلى {sorted(refs)[0]}")
            continue
        rows = surah_rows({a: v[0] for a, v in cs[s].items()}, m)
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
    j = judge(cand_idx, pub_idx, cand_sha, maps)
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
