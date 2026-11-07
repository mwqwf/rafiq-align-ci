#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""بوابة كتالوج الحزم: لا يمر timing_index إلا بشهادة حية وبصمة متسقة."""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import math
import re
from pathlib import Path

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
# أرضيّةُ التغطية الخام للشهادة (‏= MIN_RAW_COV في certify_catalog)؛ ثابتٌ واحدٌ هنا لا يُخفَّض.
MIN_RAW_COV = 0.90
# عددُ آيات كلّ سورة بالعدّ الكوفيّ (‏ayahCounting في الفهارس، 6236) — لشرط «الإعلانُ يفسّر الخروج وحده».
SURAH_AYAHS = (7, 286, 200, 176, 120, 165, 206, 75, 129, 109, 123, 111, 43, 52, 99, 128, 111, 110, 98, 135, 112, 78, 118, 64, 77, 227, 93, 88, 69, 60, 34, 30, 73, 54, 45, 83, 182, 88, 75, 85, 54, 53, 89, 59, 37, 35, 38, 29, 18, 45, 60, 49, 62, 55, 78, 96, 29, 22, 24, 13, 14, 11, 11, 18, 12, 12, 30, 52, 52, 44, 28, 28, 20, 56, 40, 31, 50, 40, 46, 42, 29, 19, 36, 25, 22, 17, 19, 26, 30, 20, 15, 21, 11, 8, 8, 19, 5, 8, 8, 11, 11, 8, 3, 9, 5, 4, 7, 3, 6, 3, 5, 4, 5, 6)
TOTAL_AYAHS = sum(SURAH_AYAHS)
_CERTIFIER = "certify_catalog-1.2"


def _finite_coverage(value, package_id: str) -> float:
    # bool is an int subclass in Python; a certificate must never accept it.
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{package_id}: certified مع تغطية غير محدودة {value!r}")
    if not MIN_RAW_COV <= value <= 1.0:
        raise ValueError(f"{package_id}: certified مع تغطية خارج [{MIN_RAW_COV}, 1] {value!r}")
    return float(value)


def _timing_id(package: dict) -> tuple[str, dict]:
    files = package.get("files") or []
    pid = str(package.get("id") or "")
    if len(files) != 1:
        raise ValueError(f"{pid}: عدد ملفات timing_index ليس واحداً")
    key = str(files[0].get("key") or "")
    parts = key.split("/")
    if len(parts) != 3 or parts[0] != "timings" or not parts[2].endswith(".jz"):
        raise ValueError(f"{pid}: مفتاح timing_index غير صالح {key!r}")
    return f"{parts[1]}/{parts[2][:-3]}", files[0]


def _snapshot_indexes(snapshot: dict) -> dict:
    if snapshot.get("schema") != 1 or snapshot.get("certifier") != _CERTIFIER:
        raise ValueError("snapshot الشهادة غير معروف")
    if not _SHA256.fullmatch(str(snapshot.get("catalogSha256") or "")):
        raise ValueError("snapshot الشهادة بلا بصمة كتالوج كاملة")
    indexes = snapshot.get("indexes")
    if not isinstance(indexes, dict):
        raise ValueError("snapshot الشهادة بلا خريطة indexes")
    return indexes


def certified_only(doc: dict, min_timing: int = 0,
                   certificate_snapshot: dict | None = None) -> tuple[dict, dict]:
    failures = doc.get("failures") or []
    if failures:
        raise ValueError(f"البناء فيه {len(failures)} فشلاً؛ يُمنع النشر")
    out = copy.deepcopy(doc)
    kept, rejected = [], list(out.get("rejected") or [])
    snapshot = _snapshot_indexes(certificate_snapshot or {})
    seen, certified, dropped = set(), 0, 0
    kept_ids = set()
    for package in out.get("packages") or []:
        pid = str(package.get("id") or "")
        if not pid or pid in seen:
            raise ValueError(f"معرّف حزمة غائب/مكرر: {pid!r}")
        seen.add(pid)
        if package.get("kind") != "timing_index":
            kept.append(package)
            continue
        timing_id, file_doc = _timing_id(package)
        quality = package.get("quality") or {}
        cert = snapshot.get(timing_id)
        # The catalog booleans are only a redundant consistency signal.  The
        # independent certificate snapshot is the authority for inclusion.
        if cert is None:
            rejected.append({"key": (package.get("files") or [{}])[0].get("key"),
                             "reason": "NOT_IN_CERTIFICATE_SNAPSHOT"})
            dropped += 1
            continue
        if quality.get("ayahCertified") is not True:
            raise ValueError(f"{pid}: snapshot مصدّق لكن علم الحزمة ليس true")
        coverage = _finite_coverage(quality.get("ayahCoverage"), pid)
        cert_coverage = _finite_coverage(cert.get("coverage"), timing_id)
        if coverage != cert_coverage:
            raise ValueError(f"{pid}: تغطية الحزمة لا تطابق snapshot الشهادة")
        if cert.get("rejected") is not False:
            raise ValueError(f"{pid}: snapshot الشهادة لا يثبت rejected=false")
        sha = str(file_doc.get("sha256") or "")
        if not _SHA256.fullmatch(sha):
            raise ValueError(f"{pid}: sha256 غير صالح")
        certified_sha = str(cert.get("sha256") or "")
        if not _SHA256.fullmatch(certified_sha) or certified_sha != sha:
            raise ValueError(f"{pid}: بصمة الملف لا تطابق شهادة SHA-256 الكاملة")
        if quality.get("sha8") != sha[:8]:
            raise ValueError(f"{pid}: sha8 لا يطابق ملف الحزمة")
        kept.append(package)
        kept_ids.add(timing_id)
        certified += 1
    missing = sorted(set(snapshot) - kept_ids)
    if missing:
        raise ValueError(f"مرشح البناء أسقط {len(missing)} معرّفاً مصدقاً: {missing[:5]}")
    if certified < min_timing:
        raise ValueError(f"الكتالوج المصدق {certified} < الحد المحافظ {min_timing}")
    out["packages"] = kept
    out["rejected"] = rejected
    out["certifiedGate"] = {
        "timingCertified": certified,
        "timingDroppedUncertified": dropped,
        "nonTimingKept": sum(p.get("kind") != "timing_index" for p in kept),
    }
    return out, out["certifiedGate"]


def declared_removal(timing_id: str, index_bytes: bytes, approvals: list) -> dict:
    """يُثبت أنّ خروج قارئٍ مصدَّقٍ من الكتالوج إسقاطٌ معلَنٌ معتمد، وإلا ValueError.

    ⭐ بإذن المالك نصّاً («موافق بالتاكيد» 2026-11-07 11:09Z · cmsg_01SnWBBbg8UvScqE3YMKdPHaHkVmDDbLeDnbx5ubMMJs16).
    الشروطُ الثلاثةُ مجتمعة:
    1. صفُّ موافقةٍ في `ops/OWNER_DROP_APPROVALS.json` لمفتاح **الفهرس المنشور نفسه**
       (‏`timings-staging/<riw>/<id>.<sha8>.jz` ببصمة البايتات المقروءة) وسورُه هي المعلَنةُ حرفاً.
    2. ترويسةُ الفهرس `drop_surah:<سور>` معها `reasonCode` و`reasonUser` غيرُ فارغَين،
       وكلُّ سورةٍ معلَنةٍ غائبةٌ فعلاً، ولا سورةَ غائبةٌ بلا إعلان (‏لا حجبَ صامت).
    3. يُسجَّل في تقرير id_diff تحت `removedDeclared` (‏يتولّاه id_diff).
    4. (‏تقسيةُ مراجعة القائد) **الإعلانُ يفسّر الخروج وحده**: التغطيةُ الخام للحاضر دون MIN_RAW_COV،
       والحاضرُ مع آيات السور المعلنة يبلغها — فلا يمرّ قارئٌ خرج من الشهادة لعلّةٍ أخرى وله إعلانٌ قديم.
    لا يمسّ certified_only ولا أرضيّة التغطية: الفهرسُ يبقى غيرَ مصدَّقٍ وخارجَ الحزم."""
    parts = timing_id.split("/")
    if len(parts) != 2 or not all(re.fullmatch(r"[a-z0-9_]+", x) for x in parts):
        raise ValueError(f"{timing_id}: معرّفٌ غير صالح للإسقاط المعلن")
    riw, rid = parts
    sha = hashlib.sha256(index_bytes).hexdigest()
    try:
        idx = json.loads(gzip.decompress(index_bytes).decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"{timing_id}: الفهرس لا يُقرأ ({type(exc).__name__})") from None
    if not isinstance(idx, dict):
        raise ValueError(f"{timing_id}: الفهرس ليس كائناً")
    if idx.get("reciterId") not in (None, rid) or idx.get("riwaya") not in (None, riw):
        raise ValueError(f"{timing_id}: الفهرس يصف قارئاً آخر")
    tr = idx.get("transform")
    if not isinstance(tr, dict):
        raise ValueError(f"{timing_id}: لا ترويسةَ تحويلٍ فيها إعلان")
    m = re.fullmatch(r"drop_surah:([0-9]+(?:,[0-9]+)*)", str(tr.get("op") or ""))
    if not m:
        raise ValueError(f"{timing_id}: لا إعلانَ drop_surah في الترويسة")
    declared = {int(x) for x in m.group(1).split(",")}
    if not declared <= set(range(1, 115)):
        raise ValueError(f"{timing_id}: سورٌ معلنةٌ خارج المصحف")
    for k in ("reasonCode", "reasonUser"):
        if not isinstance(tr.get(k), str) or not tr[k].strip():
            raise ValueError(f"{timing_id}: الإعلان بلا {k}")
    if idx.get("ayahCount") != TOTAL_AYAHS:
        raise ValueError(f"{timing_id}: عدّ الآيات {idx.get('ayahCount')!r} غيرُ {TOTAL_AYAHS}")
    present, ayahs = set(), set()
    for e in idx.get("entries") or []:
        try:
            su, ay = (int(x) for x in str(e.get("ayahId")).split(":"))
        except (ValueError, AttributeError):
            raise ValueError(f"{timing_id}: مدخلٌ بلا ayahId صالح") from None
        if not (1 <= su <= 114 and 1 <= ay <= SURAH_AYAHS[su - 1]):
            raise ValueError(f"{timing_id}: مدخلٌ خارج المصحف {su}:{ay}")
        present.add(su)
        ayahs.add((su, ay))
    if declared & present:
        raise ValueError(f"{timing_id}: سورٌ معلنةٌ وهي حاضرة {sorted(declared & present)}")
    silent = set(range(1, 115)) - present - declared
    if silent:
        raise ValueError(f"{timing_id}: سورٌ غائبةٌ بلا إعلان {sorted(silent)}")
    raw = len(ayahs) / TOTAL_AYAHS
    with_declared = (len(ayahs) + sum(SURAH_AYAHS[x - 1] for x in declared)) / TOTAL_AYAHS
    if raw >= MIN_RAW_COV:
        raise ValueError(f"{timing_id}: إسقاطُه لا يفسّره الإعلان (التغطية الخام {raw:.4f} ≥ {MIN_RAW_COV})")
    if with_declared < MIN_RAW_COV:
        raise ValueError(f"{timing_id}: ناقصٌ خارج المعلَن (الحاضر مع المعلن {with_declared:.4f} < {MIN_RAW_COV})")
    want = f"timings-staging/{riw}/{rid}.{sha[:8]}.jz"
    rows = [a for a in approvals or [] if isinstance(a, dict) and a.get("key") == want]
    if not rows:
        raise ValueError(f"{timing_id}: لا صفَّ موافقةٍ للمفتاح المنشور {want}")
    if not any({int(x) for x in a.get("surahs") or []} == declared for a in rows):
        raise ValueError(f"{timing_id}: صفُّ الموافقة لا يطابق السور المعلنة {sorted(declared)}")
    return {"id": timing_id, "sha256": sha, "approvalKey": want,
            "declaredSurahs": sorted(declared), "reasonCode": tr["reasonCode"],
            "rawCoverage": round(raw, 4), "coverageWithDeclared": round(with_declared, 4)}


def id_diff(previous: dict, candidate: dict, declared: dict | None = None) -> dict:
    before = set()
    for package in previous.get("packages") or []:
        if package.get("kind") != "timing_index":
            continue
        if (package.get("quality") or {}).get("ayahCertified") is True:
            before.add(_timing_id(package)[0])
    after = {_timing_id(p)[0] for p in candidate.get("packages") or []
             if p.get("kind") == "timing_index"}
    report = {
        "beforeCertified": sorted(before),
        "afterCertified": sorted(after),
        "added": sorted(after - before),
        "removed": sorted(before - after),
    }
    declared = declared or {}
    stale = sorted(set(declared) - set(report["removed"]))
    if stale:
        raise ValueError(f"إعلانُ إسقاطٍ لقارئٍ لم يُسقَط: {stale[:5]}")
    undeclared = [r for r in report["removed"] if r not in declared]
    if undeclared:
        raise ValueError(f"المرشح أسقط قارئاً مخدوماً مصدقاً: {undeclared[:5]}")
    if declared:
        report["removedDeclared"] = [declared[r] for r in report["removed"]]
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--min-timing", type=int, default=0)
    ap.add_argument("--certificate-snapshot", required=True)
    ap.add_argument("--previous")
    ap.add_argument("--id-diff")
    ap.add_argument("--declared-index", action="append", default=[],
                    help="معرّف=مسار فهرسه المنشور (‏.jz): إسقاطٌ معلنٌ معتمد يُفحص بـdeclared_removal")
    ap.add_argument("--approvals", help="ops/OWNER_DROP_APPROVALS.json — يلزم مع --declared-index")
    args = ap.parse_args()
    if args.declared_index and not (args.approvals and args.previous):
        raise ValueError("--declared-index يلزمه --approvals و--previous")
    approvals = json.loads(Path(args.approvals).read_text(encoding="utf-8")) if args.approvals else []
    declared = {}
    for item in args.declared_index:
        tid, sep, path = item.partition("=")
        if not sep or tid in declared:
            raise ValueError(f"--declared-index غير صالح أو مكرر: {item!r}")
        declared[tid] = declared_removal(tid, Path(path).read_bytes(), approvals)
    doc = json.loads(Path(args.input).read_text(encoding="utf-8"))
    snapshot = json.loads(Path(args.certificate_snapshot).read_text(encoding="utf-8"))
    out, stat = certified_only(doc, args.min_timing, snapshot)
    if bool(args.previous) != bool(args.id_diff):
        raise ValueError("--previous و--id-diff يُعطيان معاً")
    if args.previous:
        previous = json.loads(Path(args.previous).read_text(encoding="utf-8"))
        diff = id_diff(previous, out, declared)
        Path(args.id_diff).write_text(
            json.dumps(diff, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        stat["beforeCertified"] = len(diff["beforeCertified"])
        stat["added"] = len(diff["added"])
        stat["removed"] = len(diff["removed"])
        stat["removedDeclared"] = len(diff.get("removedDeclared") or [])
    Path(args.output).write_text(
        json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(json.dumps(stat, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
