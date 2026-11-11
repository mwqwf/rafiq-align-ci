#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""قياسُ سورةٍ واحدةٍ للباب المزدوج في بوّابة السماع: خريطتان على الصوت نفسِه + شاهدُ Whisper لما تطلبه الخريطتان.

    python tools/index_qa/heard_dual_probe.py --url <mp3> --surah 36 --riwaya hafs --out-dir hg/x --cand <cand.json>

`cand.json`: {"sha": بصمةُ المرشّح, "ends": {"آية": [بدء, نهاية]}}. يكتب في `--out-dir`:
  heard_sNNN.json (‏العامّة G · float32) · q/heard_sNNN.json (‏نموذجُ التلاوة R · float32) ·
  w/whisper_sNNN.json (‏شاهدُ Whisper medium float32 لآياتٍ تحدّدها `heard_gate.dual_witness_plan` من الخريطتين — لا من المُطلِق).
⛔ لا رفعَ ولا كتابةَ في دلو؛ العمليتان منفصلتان لأنّ نموذجين لا يُحمَّلان في عمليةٍ واحدة (‏`quran_ctc_model.configure`).
والحكمُ يُعاد في `heard_gate.judge` من الملفّات هذه، ولا يُقرأ منها حكمٌ."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import heard_gate as H  # noqa: E402


def run(cmd, env_extra, err_path):
    env = dict(os.environ, **env_extra)
    with open(err_path, "w", encoding="utf-8") as ef:
        return subprocess.run(cmd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=ef).returncode


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--url", required=True)
    ap.add_argument("--surah", type=int, required=True)
    ap.add_argument("--riwaya", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--cand", required=True, help="ملفُّ JSON: sha وends")
    ap.add_argument("--witness-model", default="medium", choices=("small", "medium", "large-v3"))
    a = ap.parse_args()
    cand = json.load(open(a.cand, encoding="utf-8"))
    ends = {int(k): v for k, v in cand["ends"].items()}
    starts = {k: v[0] for k, v in ends.items()}
    s3 = f"{a.surah:03d}"
    d, dq, dw = Path(a.out_dir), Path(a.out_dir) / "q", Path(a.out_dir) / "w"
    for p in (d, dq, dw):
        p.mkdir(parents=True, exist_ok=True)
    hm = ROOT / "tools" / "alignment_v3" / "ctc_heard_map.py"
    base = [sys.executable, str(hm), "--url", a.url, "--surah", str(a.surah), "--riwaya", a.riwaya, "--probe"]
    rc = run(base + ["--out-dir", str(d), "--report", str(d / f"heard_s{s3}.txt")], {"CTC_INT8": "0"}, d / f"err_{a.surah}.txt")
    if rc:
        print(f"⚠️ س{a.surah}: خريطةُ العامّة أخفقت ({rc})")
        return rc
    shutil.copy(d / f"{s3}.mp3", dq / f"{s3}.mp3")      # الصوتُ نفسُه بلا إعادة تنزيل — بصمةٌ واحدةٌ للخريطتين
    rc = run(base + ["--out-dir", str(dq), "--quran-model", "--report", str(dq / f"heard_s{s3}.txt")],
             {"CTC_INT8": "0"}, dq / f"err_{a.surah}.txt")
    if rc:
        print(f"⚠️ س{a.surah}: خريطةُ نموذج التلاوة أخفقت ({rc})")
        return rc
    gm = H.compact_map(json.load(open(d / f"heard_s{s3}.json", encoding="utf-8")))
    rm = H.compact_map(json.load(open(dq / f"heard_s{s3}.json", encoding="utf-8")))
    if gm["sha256"] != rm["sha256"]:
        print(f"⛔ س{a.surah}: بصمتا الخريطتين مختلفتان")
        return 3
    plan = H.dual_witness_plan(starts, gm, rm, cand["sha"], a.surah)
    print(f"✓ س{a.surah}: خريطتان · آياتُ الشاهد {len(plan)}: {plan[:40]}")
    if plan:
        rc = run([sys.executable, str(HERE / "whisper_witness.py"), "--url", a.url, "--surah", str(a.surah),
                  "--riwaya", a.riwaya, "--ayahs", H.witness_windows(ends, plan), "--model", a.witness_model,
                  "--out", str(dw)], {}, dw / f"err_{a.surah}.txt")
        if rc:
            print(f"⚠️ س{a.surah}: شاهدُ Whisper أخفق ({rc}) — يُحكم بلا شاهد (‏المتنازَعةُ تُردّ)")
    for p in (d, dq, dw):
        for f in list(p.glob("*.mp3")) + list(p.glob("*.wav")):
            f.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main())
