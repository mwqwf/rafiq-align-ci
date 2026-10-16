#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""إلغاءُ أحكامِ سائق CTC **المنتظرة** على مرشّحاتٍ تجاوزها مرشّحٌ أحدثُ للقارئ نفسِه (2026-10-16).

    python tools/ci_fleet/cancel_superseded_ctc_qa.py [--yes]

سببُه (قِيس 2026-10-16 ‏01:4xZ): سلاسلُ الإصلاح المتسلسلة (‏ctc_splice دفعةً فوق دفعة) تُنتج في كلّ
خطوةٍ بصمةً وسيطة، فيطلق `ctc_driver.py` لكلٍّ منها مطالعَ وأربعةَ ملوح (k1–k4) ⇒ 60 تشغيلةً منتظرةً
لـ12 بصمةً وسيطة، والأسطولُ يُجري نحو ستٍّ فقط، فتجوع خطواتُ السلاسل خلفها.

⛔ حدودُه: يُلغي **المنتظرَ وحده** (queued/pending/waiting، لا الجاري ولا المكتمل) · من `audio_qa.yml`
بملحٍ من k1–k4 ومن `openers.yml` بـ`n=1` (‏إطلاقُ السائق نفسِه بعنوانه الحرفيّ) · ومفتاحُه في المسرح
**وله في المسرح بصمةٌ أحدثُ للقارئ والرواية نفسَيهما**. لا يمسّ دلواً ولا حكماً ولا فهرساً؛ والأحدثُ
يُحكم عليه كاملاً كما كان. وبلا `--yes` عرضٌ فقط.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

PENDING = ("queued", "pending", "waiting")
QA_RE = re.compile(r"^qa (timings-staging/[a-z]+/[A-Za-z0-9_-]+\.[0-9a-f]{8}\.jz) · salt=(k[1-4]) · n=20$")
OP_RE = re.compile(r"^openers (timings-staging/[a-z]+/[A-Za-z0-9_-]+\.[0-9a-f]{8}\.jz) · n=1$")


def run_key(run):
    """مفتاحُ المرشّح إن كانت التشغيلةُ من إطلاق السائق ومنتظرة، وإلا None — دالّةٌ صِرفة."""
    if run.get("status") not in PENDING or run.get("event") != "workflow_dispatch":
        return None
    title, path = run.get("display_title", ""), run.get("path", "")
    m = (QA_RE.match(title) if path == ".github/workflows/audio_qa.yml"
         else OP_RE.match(title) if path == ".github/workflows/openers.yml" else None)
    return m.group(1) if m else None


def who(key):
    p = key.split("/")
    return p[1], p[2].split(".")[0]


def superseded(key, staged):
    """صحيحٌ إذا كان للقارئ في المسرح بصمةٌ أحدثُ من `key`. ‏staged: {مفتاح: زمن}."""
    if key not in staged:
        return False
    return any(who(k) == who(key) and t > staged[key] for k, t in staged.items() if k != key)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    from qa_recover_stalled import gh
    sys.path.insert(0, str(HERE.parent / "index_qa"))
    from run import s3
    cl, b = s3()
    staged = {}
    for pg in cl.get_paginator("list_objects_v2").paginate(Bucket=b, Prefix="timings-staging/"):
        for o in pg.get("Contents", []):
            if o["Key"].endswith(".jz"):
                staged[o["Key"]] = o["LastModified"].timestamp()
    n = 0
    for st in PENDING:
        for run in gh(f"actions/runs?status={st}&per_page=100").get("workflow_runs", []):
            k = run_key(run)
            if not k or not superseded(k, staged):
                continue
            n += 1
            print(json.dumps({"run": run["id"], "title": run["display_title"], "cancel": a.yes},
                             ensure_ascii=False), flush=True)
            if a.yes:
                gh(f"actions/runs/{run['id']}/cancel", {})
    print(f"تشغيلاتٌ منتظرةٌ على مرشّحاتٍ متجاوَزة: {n}" + ("" if a.yes else " (عرضٌ فقط — أضف --yes)"))


if __name__ == "__main__":
    main()
