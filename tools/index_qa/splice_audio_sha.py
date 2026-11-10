#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""بصماتُ الصوت بعد دمج `ctc_splice` — تُكتب المقيسةُ للسورة المعاد محاذاتُها **كلِّها** وحدَها (‏2026-11-10).

العلّة التي يسدّها (‏الكردي س55 · المرشّح bd3c5d89): ملفُّ المصدر `055.mp3` تبدّل عند الناشر، فأُعيدت
محاذاةُ السورة كلِّها 1..78 بالسماع (‏`mode=heard`) على الملفّ الحاليّ — لكنّ خطوةَ الدمج القديمة لا تكتب
البصمةَ المقيسة إلا إذا ساوى طولُ `audioSha256` عددَ السور **الحاضرة**؛ وقائمةُ الكردي ثابتةٌ من 114 موضعاً
(‏تُبقي موضعَ النساء المحجوبة) والحاضرةُ 113، فتُركت البصمةُ القديمة (5f498f57) فردّت بوّابةُ السماع بحقّ:
«الصوتُ المسموع (60b66c8b) غيرُ صوت المرشّح (5f498f57)».

⭐ القاعدة (‏أداةُ البناء لا الحارس — البوّابةُ كما هي حرفاً):
  - تُكتب البصمةُ المقيسة (‏`sha256` من الملفّ الذي نُزّل وحوذي في التشغيلة نفسِها) **فقط** إذا:
    ① كان الوضعُ وضعَ محاذاةٍ للسورة كلّها (‏`full` أو `heard`) بلا ذيلٍ مبتورٍ ولا غائباتٍ مسمّاة؛
    ② وفي `heard` بـ`rewindow` يُسمّي السورةَ: المدى المسمّى هو 1..N تماماً؛
    ③ وصفوفُ المحاذاة N صفّاً كلُّها بحدود، ومداخلُ السورة في المدموج N مدخلاً **هي صفوفُ المحاذاة نفسُها**
       (‏بدءاً ونهايةً) — فلا مدخلَ موروثٌ من الأب يبقى تحت بصمةٍ جديدة؛
    ④ و`fileRef` لكلّ مدخلٍ من السورة = `fileRef` الملفّ الذي حوذي (‏وإلا ردٌّ كما كان).
  - وما سوى ذلك (‏نافذةٌ أو مدىً جزئيّ أو dualfix) لا تُمسّ بصمتُه؛ وإن خالفت المقيسةَ قيل ذلك صراحةً،
    فتردّه البوّابةُ كما ينبغي (‏مداخلُ قديمةٌ على ملفٍّ تبدّل).
  - الموضع: قائمةٌ من 114 ⇒ `shas[s-1]`؛ وقائمةٌ مضغوطةٌ على الحاضرة ⇒ موضعُ السورة بين الحاضرة؛
    وغيرُ ذلك يُترك كما هو ويُقال (‏كما كان).
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from splice_surah import COUNTS  # noqa: E402

WHOLE_MODES = ("full", "heard")


def parse_rewindow(txt: str) -> dict:
    """«55:1-78,89:1-2/nb» ⇐ {55: [(1, 78)], 89: [(1, 2)]}؛ والمفردةُ «38:44» ⇐ (44، 44)."""
    out: dict = {}
    for part in (txt or "").replace("،", ",").split(","):
        part = part.strip().split("/")[0]
        if ":" not in part:
            continue
        s, rng = part.split(":", 1)
        a, _, b = rng.partition("-")
        out.setdefault(int(s), []).append((int(a), int(b or a)))
    return out


def whole_surah_reason(s: int, rec: dict, entries: list, mode: str, rewin: dict,
                       truncated: bool = False, absent: bool = False):
    """None إن كانت السورةُ أُعيدت محاذاتُها كلُّها من هذا القياس؛ وإلا سببُ الجزئيّة نصّاً."""
    n = COUNTS[s - 1]
    if mode not in WHOLE_MODES:
        return f"وضعُ {mode} يُعيد بعضَ السورة"
    if truncated:
        return "ذيلٌ مبتورٌ معلَن"
    if absent:
        return "غائباتٌ مسمّاة"
    if s in rewin and rewin[s] != [(1, n)]:
        return f"rewindow يُسمّي {rewin[s]} لا 1..{n}"
    rows = rec.get("entries") or []
    if len(rows) != n or any(r.get("startMs") is None or r.get("endMs") is None for r in rows):
        return f"صفوفُ المحاذاة {sum(1 for r in rows if r.get('startMs') is not None)}/{n} بحدود"
    mine = {int(e["ayahId"].split(":")[1]): (e.get("startMs"), e.get("endMs"))
            for e in entries if int(e["ayahId"].split(":")[0]) == s}
    if len(mine) != n:
        return f"مداخلُ السورة في المدموج {len(mine)}/{n}"
    moved = [i + 1 for i, r in enumerate(rows) if mine.get(i + 1) != (r["startMs"], r["endMs"])]
    if moved:
        return f"{len(moved)} مدخلاً ليست من هذه المحاذاة (أوّلها الآية {moved[0]})"
    return None


def apply(idx: dict, taken: list, recs: dict, mode: str, rewindow: str = "",
          truncated: bool = False, absent: bool = False, log=print) -> dict:
    """يعدّل `idx["audioSha256"]` في موضعه ويُعيد {سورة: "written"|"kept"|"partial:<سبب>"}."""
    entries = idx.get("entries") or []
    rewin = parse_rewindow(rewindow)
    present = sorted({int(e["ayahId"].split(":")[0]) for e in entries})
    sha = idx.get("audioSha256")
    if isinstance(sha, list) and len(sha) == 114:
        pos = {s: s - 1 for s in present}
    elif isinstance(sha, list) and len(sha) == len(present):
        pos = {s: i for i, s in enumerate(present)}
    else:
        pos = None
    out = {}
    for s in taken:
        rec = recs[s]
        # ⛔ الفهرسُ يُشير إلى ملفّ الكتالوج نفسِه — والبصمةُ من الملفّ الذي نُزّل وحوذي فعلاً.
        for e in entries:
            if int(e["ayahId"].split(":")[0]) == s and e["fileRef"] != rec.get("fileRef"):
                raise SystemExit(f"⛔ س{s}: fileRef المدموج {e['fileRef']} ≠ المحاذى {rec.get('fileRef')}")
        new = rec.get("sha256")
        if not new:
            out[s] = "kept"
            continue
        if pos is None or s not in pos:
            log(f"⚠️ قائمةُ البصمات {len(sha) if isinstance(sha, list) else '—'} "
                f"والسورُ {len(present)} — تُترك كما هي (س{s})")
            out[s] = "kept"
            continue
        old = sha[pos[s]]
        why = whole_surah_reason(s, rec, entries, mode, rewin, truncated, absent)
        if why:
            if old and old != new:
                log(f"⚠️ س{s}: بصمةُ الملفّ المحاذى ({new[:8]}) غيرُ المسجّلة ({str(old)[:8]}) "
                    f"والمحاذاةُ جزئيّة ({why}) — تُترك المسجّلة، وتردّها بوّابةُ السماع إن تبدّل الملفّ")
            out[s] = f"partial:{why}"
            continue
        if old and old != new:
            log(f"🔄 س{s}: بصمةُ الصوت تبدّلت عند المصدر ({str(old)[:8]} → {new[:8]}) — "
                f"والسورةُ أُعيدت كلُّها 1..{COUNTS[s - 1]} على الملفّ نفسِه فتُكتب المقيسة")
        sha[pos[s]] = new
        out[s] = "written"
    if pos is not None:
        idx["audioSha256"] = sha
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--index", required=True, help="المدموج (patched.jz) — يُعاد كتابتُه في موضعه")
    ap.add_argument("--batch-dir", required=True)
    ap.add_argument("--mode", default="full")
    ap.add_argument("--rewindow", default="")
    ap.add_argument("--truncated", action="store_true")
    ap.add_argument("--absent", action="store_true")
    a = ap.parse_args(argv)
    p = Path(a.index)
    idx = json.loads(gzip.decompress(p.read_bytes()).decode("utf-8"))
    taken = [int(x) for x in Path(str(p) + ".taken").read_text().split(",") if x]
    recs = {s: json.loads((Path(a.batch_dir) / f"s{s:03d}.json").read_text(encoding="utf-8")) for s in taken}
    res = apply(idx, taken, recs, a.mode, a.rewindow, a.truncated, a.absent)
    p.write_bytes(gzip.compress(json.dumps(idx, ensure_ascii=False).encode("utf-8")))
    print("بصماتُ الصوت:", res)
    print("المأخوذ:", taken, "· engineBySurah:", idx.get("engineBySurah"),
          "· sourceBySurah:", idx.get("sourceBySurah"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
