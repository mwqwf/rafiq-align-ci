#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يفرّز حكم بوّابة السماع إلى مدى rewindow مقترَح — بلا إطلاق سير.

    python tools/index_qa/triage_heard_gate.py ops/out/heard-gate/45087799407.txt

يقرأ السور المعدَّلة المردودة فقط. عيّنة التقرير («لا تردّ») تُذكر ولا تدخل الاقتراح.
لا يُطلَق workflow، ولا يُقترَح إعادة مطابقة، ولا يُتخطّى «لا يُعاد heard مطابق».
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# س14: ⛔ 11 آيةً … (أقصاها الآية 21: -848.6ث) · الآيات 5,6,13,17,21,22,23,27,28,31,32
ROW = re.compile(
    r"س(\d+):\s*⛔.*?الآيات\s+([0-9،,]+)",
    re.MULTILINE,
)
SAMPLE = re.compile(r"عيّنةٌ للتقرير|عيّنة للتقرير")
MODIFIED = re.compile(r"معدّلة\s*\[([0-9,\s]+)\]")


def collapse_ranges(ayahs: list[int]) -> str:
    """5,6,13,17,21,22,23 → 5-6,13,17,21-23"""
    if not ayahs:
        return ""
    ayahs = sorted(set(ayahs))
    ranges = []
    start = prev = ayahs[0]
    for a in ayahs[1:]:
        if a == prev + 1:
            prev = a
            continue
        ranges.append(f"{start}-{prev}" if start != prev else f"{start}")
        start = prev = a
    ranges.append(f"{start}-{prev}" if start != prev else f"{start}")
    return ",".join(ranges)


def parse_ayahs(blob: str) -> list[int]:
    return [int(x) for x in re.split(r"[،,\s]+", blob) if x.strip().isdigit()]


def triage(text: str) -> dict:
    modified = []
    m = MODIFIED.search(text)
    if m:
        modified = [int(x) for x in re.split(r"[,\s]+", m.group(1)) if x.strip().isdigit()]
    rejected = []
    samples = []
    for line in text.splitlines():
        if "⛔" not in line or "الآيات" not in line:
            continue
        mm = ROW.search(line)
        if not mm:
            continue
        rec = {"surah": int(mm.group(1)), "ayahs": parse_ayahs(mm.group(2))}
        rec["rewindow"] = f"{rec['surah']}:{collapse_ranges(rec['ayahs'])}"
        if SAMPLE.search(line) or (modified and rec["surah"] not in modified and "معدّلة" not in line):
            # سطر العيّنة الصريح، أو سورة ليست في قائمة المعدَّلة
            if "معدّلة" in line:
                rejected.append(rec)
            else:
                samples.append(rec)
        else:
            # إن وُجدت قائمة معدَّلة فالسورة يجب أن تكون فيها كي تُقترَح
            if modified and rec["surah"] not in modified:
                samples.append(rec)
            else:
                rejected.append(rec)
    rewindow = ",".join(r["rewindow"] for r in rejected)
    return {
        "modified_surahs": modified,
        "rejected": rejected,
        "sample_only": samples,
        "suggested_rewindow": rewindow,
        "n_rejected_surahs": len(rejected),
        "launch": False,
        "note": "اقتراح فقط — لا إطلاق تلقائي ولا إعادة مطابقة",
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)
    reports = []
    for f in args.files:
        p = Path(f)
        rec = triage(p.read_text(encoding="utf-8", errors="replace"))
        rec["file"] = str(p)
        reports.append(rec)
        print(f"{p.name}: rejected={rec['n_rejected_surahs']} rewindow={rec['suggested_rewindow'] or '—'}")
    if args.out:
        Path(args.out).write_text(json.dumps(reports, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
