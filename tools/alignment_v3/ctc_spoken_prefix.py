#!/usr/bin/env python3
"""استرجاع مطلع حروف مقطعة بمرساة ثانية ثابتة، ونص الرواية دون تعديل.

محاذاة CTC على نافذة المطلع وحدها من الصوت الكامل المقيس. يرد اختلاف
بصمة الصوت أو انزياح المرساة أو ضعف الثقة؛ لا يحرك مدخلاً موجوداً.
المخرج محلي وبمحرك النوافذ ctc-gapsplit-1؛ stage_transform ثم المطالع
والملوح الأربعة وإحصاء كل آية في السور المعنية لازمة للاعتماد.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "alignment"))
sys.path.insert(0, str(HERE))
from common import load_index, load_text, norm, surah_slice, to_wav16k
from spoken_letters import alignment_text


def insert_first(idx, surah, source_sha, measured):
    """لا قبول لحد جديد إلا على الصوت نفسه وبمرساة لم تتحرك."""
    first_id, next_id = f"{surah}:1", f"{surah}:2"
    entries = idx["entries"]
    if any(e["ayahId"] == first_id for e in entries):
        raise ValueError("المطلع حاضر؛ ليست هذه أداة إعادة توقيت")
    anchors = [e for e in entries if e["ayahId"] == next_id]
    if len(anchors) != 1 or len(idx.get("audioSha256") or []) != 114:
        raise ValueError("المرساة أو سجل بصمات الصوت غير سوي")
    anchor = anchors[0]
    refs = {e["fileRef"] for e in entries if e["ayahId"].startswith(f"{surah}:")}
    if refs != {anchor["fileRef"]} or idx["audioSha256"][surah - 1] != source_sha:
        raise ValueError("الصوت الكامل لا يطابق أصل السورة")
    if min(measured["firstConf"], measured["anchorConf"]) < .45:
        raise ValueError("ثقة المحاذاة دون MED")
    if abs(measured["anchorStartMs"] - anchor["startMs"]) > 700:
        raise ValueError("المحاذاة لا تؤكد مرساة الآية الثانية")
    start, end = int(measured["firstStartMs"]), int(anchor["startMs"])
    if start < 0 or end - start < 1200:
        raise ValueError("مدة المطلع غير قابلة للاعتماد")
    conf = measured["firstConf"] if measured["snapped"] else min(.74, measured["firstConf"])
    row = {"ayahId": first_id, "fileRef": anchor["fileRef"],
           "startMs": start, "endMs": end, "conf": conf,
           "confBand": "HIGH" if conf >= .75 else "MED"}
    if not measured["snapped"]:
        row["startApprox"] = True
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--index", required=True)
    ap.add_argument("--surahs", required=True)
    ap.add_argument("--audio-dir", required=True, help="الصوت الكامل: <reciter>_<surah:03d>.mp3")
    ap.add_argument("--out", required=True)
    ap.add_argument("--omit-basmala", action="store_true", help="شاهد صوتي يثبت أن التسجيل يبدأ بالحروف دون بسملة؛ لا تغيير حراس المرساة")
    a = ap.parse_args()
    import numpy as np
    import ctc_seg as C
    from vad import read_wav, silences, snap_to_silence
    idx = json.loads(gzip.decompress(Path(a.index).read_bytes()))
    canonical = load_text(idx["riwaya"])
    surahs = sorted({int(s) for s in a.surahs.split(",")})
    if not surahs or any(not 1 <= s <= 114 for s in surahs):
        raise ValueError("سور غير صالحة")
    rows, evidence = [], {}
    for s in surahs:
        offset, _, _ = surah_slice(load_index(), s)
        raw_first = canonical[offset]
        if norm(raw_first) not in ("الم", "طه", "حم"):
            raise ValueError("هذا المطلع خارج نطاق الحروف المستقلة المدعومة")
        if any(e["ayahId"] == f"{s}:1" for e in idx["entries"]):
            raise ValueError("المطلع حاضر")
        anchor = next(e for e in idx["entries"] if e["ayahId"] == f"{s}:2")
        audio = Path(a.audio_dir) / f"{idx['reciterId']}_{s:03d}.mp3"
        sha = hashlib.sha256(audio.read_bytes()).hexdigest()
        if len(idx["audioSha256"]) != 114 or idx["audioSha256"][s - 1] != sha:
            raise ValueError("بصمة الصوت الكامل تخالف الأب؛ لا تفريغ")
        wav = to_wav16k(str(audio))
        x = read_wav(wav).astype(np.float32)[:(anchor["endMs"] + 1500) * C.SR // 1000]
        if len(x) * 1000 // C.SR < anchor["endMs"]:
            raise ValueError("الصوت لا يبلغ نهاية المرساة")
        spoken = alignment_text(s, 1, raw_first)
        lead = [] if a.omit_basmala else [C.BASMALA]
        segments = C._segment(C._emissions(x), len(x), lead + [spoken, norm(canonical[offset + 1])])[len(lead):]
        st, en, sc = segments[0]
        second_st, _, second_sc = segments[1]
        snap, on_sil = snap_to_silence(int(st * 1000), silences(wav), tolerance_ms=700)
        measured = {"firstStartMs": snap, "firstConf": C._conf(sc),
                    "firstAlignedEndMs": int(en * 1000), "anchorStartMs": int(second_st * 1000),
                    "anchorConf": C._conf(second_sc), "snapped": bool(on_sil),
                    "audioSha256": sha, "fileRef": anchor["fileRef"],
                    "phoneticAlignmentInput": spoken, "canonicalTextChanged": False}
        if a.omit_basmala:
            measured["basmalaOmitted"] = True
        rows.append(insert_first(idx, s, sha, measured))
        evidence[str(s)] = measured
    out = copy.deepcopy(idx)
    out["entries"] = sorted(out["entries"] + rows, key=lambda e: tuple(map(int, e["ayahId"].split(":"))))
    ebs = dict(out.get("engineBySurah") or {})
    for s in surahs:
        ebs[str(s)] = "ctc-gapsplit-1"
    out["engineBySurah"] = ebs
    miss = dict(out.get("missing") or {})
    added = {r["ayahId"] for r in rows}
    ids = set(miss.get("ids") or [])
    if not added <= ids or len(ids) != miss.get("count"):
        raise ValueError("بيان الغياب في الأب لا يطابق المداخل المسترجعة")
    gone = ids - added
    miss["count"] = len(gone)
    miss["ids"] = sorted(gone, key=lambda v: tuple(map(int, v.split(":"))))
    reasons = miss.get("byReason") or {}
    if len(reasons) == 1 and sum(reasons.values()) == len(ids):
        miss["byReason"] = {next(iter(reasons)): len(gone)} if gone else {}
    elif not gone:
        miss["byReason"] = {}
    else:
        raise ValueError("أسباب الغياب متعددة؛ يلزم نسب الاسترجاع قبل بناء المرشح")
    out["missing"] = miss
    out["spokenPrefixEvidence"] = evidence
    before = {e["ayahId"]: e for e in idx["entries"]}
    after = {e["ayahId"]: e for e in out["entries"]}
    if any(after[k] != v for k, v in before.items()):
        raise ValueError("تغير مدخل موجود؛ لا يكتب")
    blob = gzip.compress(json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode(), mtime=0)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_bytes(blob)
    print(json.dumps({"sha256": hashlib.sha256(blob).hexdigest(), "added": sorted(added),
                      "existingEntriesChanged": 0, "evidence": evidence}, ensure_ascii=False))


if __name__ == "__main__":
    main()
