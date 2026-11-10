#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يثبت على **manifest الحيّ كلّه** أنّ حكمَ كلّ فهرسٍ منشورٍ في `index_gate` و`certify_catalog.declared_absent`
لا يتغيّر بتشديد العدّاد (#103) متى كُتبت صفوفُ «موروث قبل #103» (‏حكم القائد 2026-11-10، البند ٣).

    python tools/index_qa/verify_pre103_verdicts.py --rows ops/INHERITED_DROP_DECLARATIONS.json [--dir <مجلّد محلّي>]

القديم يُحسب كما كان قبل الطلب: المعفى = min(byReason.source_truncated, count)، و`declared_absent` = min(source_truncated, count).
والجديدُ بالحساب الحاليّ مع الصفوف. أيُّ فرقٍ في حكم البوّابة أو في عدد الغياب المعلَن ⇒ رمزُ خروجٍ 1 وسطرٌ لكلّ فرق.
والشهادةُ في `certify` لا تقرأ من الفهرس إلا `declared_absent` ⇒ تساويه في كلّ فهرسٍ يعني ألّا تنقص شهادةٌ كاملة.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
import urllib.request
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import certify_catalog                                           # noqa: E402
import promote                                                   # noqa: E402

PUB = "https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev/"


def _get(key, local):
    if local:
        p = Path(local) / key.replace("/", "_")
        if p.exists():
            return p.read_bytes()
    req = urllib.request.Request(PUB + key, headers={"User-Agent": "curl/8.5"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def legacy_excused(idx, *_a, **_k):
    miss = idx.get("missing") or {}
    return max(0, min(int((miss.get("byReason") or {}).get("source_truncated", 0) or 0), int(miss.get("count") or 0)))


def legacy_declared(d):
    tr = d.get("transform") if isinstance(d.get("transform"), dict) else {}
    if not certify_catalog.declared_op(tr) or not tr.get("reasonCode"):
        return 0
    miss = d.get("missing") if isinstance(d.get("missing"), dict) else {}
    n = (miss.get("byReason") or {}).get("source_truncated")
    if type(n) is not int or n <= 0:
        return 0
    return min(n, int(miss.get("count") or 0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True)
    ap.add_argument("--dir", help="نسخٌ محلّيّة بأسماء timings_<رواية>_<قارئ>.jz (‏تُتحقّق بصماتُها من manifest)")
    a = ap.parse_args()
    rows = promote.load_inherited_declarations(a.rows)
    man = json.loads(_get("timings/manifest.json", a.dir))
    diff, n = [], 0
    for x in man["indexes"]:
        key = f"timings/{x['riwaya']}/{x['reciterId']}.jz"
        body = _get(key, a.dir)
        if hashlib.sha256(body).hexdigest() != x.get("sha256"):
            raise SystemExit(f"⛔ {key}: البصمةُ لا تطابق manifest — لا حكمَ على غير الحيّ")
        idx = json.loads(gzip.decompress(body))
        n += 1
        new_gate = promote.index_gate(idx, inherited=rows)
        with mock.patch.object(promote, "gate_excused", legacy_excused):
            old_gate = promote.index_gate(idx, inherited=rows)
        new_d, old_d = certify_catalog.declared_absent(idx, inherited=rows), legacy_declared(idx)
        if new_gate != old_gate or new_d != old_d:
            diff.append(f"{key} ({x['sha256'][:8]}): index_gate {old_gate!r} ⇒ {new_gate!r} · declared_absent {old_d} ⇒ {new_d}")
    print(f"فهارس منشورة: {n} · تغيّر حكمُها: {len(diff)}")
    for d in diff:
        print("  ⛔ " + d)
    sys.exit(1 if diff else 0)


if __name__ == "__main__":
    main()
