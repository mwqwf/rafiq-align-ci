#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تدقيق اكتمال مستقل، قارئ فقط، لا يرقّي ولا يغيّر حارساً.

    python tools/index_qa/completion_audit.py --live --out ops/out/completion-audit.json
    python tools/index_qa/completion_audit.py --snapshot snapshot.json --out ops/out/completion-offline.json

يعيد حساب المطالع والوسط والذيل من الخرائط المسموعة لكل سورة، ولا يثق بـok
أو sampleFindings. خريطة بصمة قديمة يعاد استعمالها فقط للصوت والسورة والقارئ
والرواية أنفسهم، مع إعادة مقارنة مداخل البصمة المنشورة الحالية. الشهادة محدودة
بمواضع البدء: نهاية anchor ليست شهادة endMs، وtotalMs القديم قد يكون ffprobe.
لذلك missingEndEvidence مانع صريح، لا ادعاء اكتمال من أداة تقيس البدايات وحدها.
--live يستعمل صلاحيات القراءة القائمة في promote.s3 فقط. لا صوت، نموذج، رفع،
أو cache جديد؛ المخرجات المحلية تحت ops/out وحده. 0=اكتمال مثبت، 2=عمل باق.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COUNTS = (7, 286, 200, 176, 120, 165, 206, 75, 129, 109, 123, 111, 43, 52,
          99, 128, 111, 110, 98, 135, 112, 78, 118, 64, 77, 227, 93, 88, 69,
          60, 34, 30, 73, 54, 45, 83, 182, 88, 75, 85, 54, 53, 89, 59, 37,
          35, 38, 29, 18, 45, 60, 49, 62, 55, 78, 96, 29, 22, 24, 13, 14,
          11, 11, 18, 12, 12, 30, 52, 52, 44, 28, 28, 20, 56, 40, 31, 50,
          40, 46, 42, 29, 19, 36, 25, 22, 17, 19, 26, 30, 20, 15, 21, 11,
          8, 8, 19, 5, 8, 8, 11, 11, 8, 3, 9, 5, 4, 7, 3, 6, 3, 5, 4, 5, 6)
EXPECTED_INDEXES = 180
TOL_MS, MIN_Q, REPEAT_SIM, REPEAT_NEAR_MS = 1500, 0.5, 0.7, 2000
SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def read_json(path):
    data = Path(path).read_bytes()
    return json.loads(gzip.decompress(data) if data.startswith(b"\x1f\x8b") else data)


def _index(record):
    if isinstance(record.get("index"), dict):
        return record["index"]
    idx = dict(record.get("header") or {})  # audit_export.py، بلا إعادة تصدير
    files = record.get("files") or []
    idx["entries"] = [{"ayahId": f"{s}:{a}", "startMs": st, "endMs": en,
                       "fileRef": files[f] if isinstance(f, int) and 0 <= f < len(files) else None}
                      for s, a, st, en, f in record.get("rows") or []]
    return idx


def _side(snapshot, key, default):
    value = (snapshot.get("side") or {}).get(key, default)
    return json.loads(value) if isinstance(value, str) and not key.endswith(".txt") else value


def _identity_maps(snapshot):
    manifest = _side(snapshot, "timings/manifest.json", {})
    rows = manifest.get("indexes", []) if isinstance(manifest, dict) else []
    by_key = {f"timings/{r['riwaya']}/{r['reciterId']}.jz": r for r in rows}
    frozen = _side(snapshot, "timings/frozen.txt", "")
    if isinstance(frozen, str):
        parsed = {}
        for line in frozen.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0].startswith("timings/"):
                parsed[parts[0]] = parts[1]
        frozen = parsed
    return by_key, frozen, len(rows) != len(by_key)


def report_matches(key, report):
    """لا تعيد خريطة قارئ آخر أو رواية أخرى ولو تكرر ملف الصوت."""
    riwaya, filename = key.split("/")[1:]
    stem = filename[:-3]
    src = report.get("src") or report.get("key") or ""
    return src == key or (src.startswith(f"timings-staging/{riwaya}/{stem}.") and src.endswith(".jz"))


def _map(report, surah):
    maps = report.get("maps") or {}
    return maps.get(str(surah)) or maps.get(surah)


def start_row(entry, cmap):
    """موضع البدء وحده؛ فشل القياس لا يصير براءة، ولا نقبل NaN."""
    a = entry["ayahId"].split(":")[1]
    rec = (cmap.get("anchors") or {}).get(a)
    out = {"ayahId": entry["ayahId"], "startMs": entry["startMs"], "status": "unmeasured"}
    if not isinstance(rec, list) or len(rec) < 2:
        return out
    anchor, quality = rec[:2]
    if (not isinstance(anchor, list) or len(anchor) != 2 or not all(finite(x) for x in anchor)
            or anchor[0] < 0 or anchor[1] <= anchor[0] or not finite(quality) or quality < MIN_Q):
        return out
    out.update(anchorMs=anchor, quality=quality, deviationMs=entry["startMs"] - anchor[0])
    out["status"] = "ok" if abs(out["deviationMs"]) <= TOL_MS else "deviation"
    if out["status"] == "deviation":
        for occurrence in rec[2] if len(rec) > 2 and isinstance(rec[2], list) else []:
            if (isinstance(occurrence, list) and len(occurrence) >= 3
                    and all(finite(x) for x in occurrence[:3]) and occurrence[1] > occurrence[0] >= 0
                    and occurrence[2] >= REPEAT_SIM
                    and abs(entry["startMs"] - occurrence[0]) <= REPEAT_NEAR_MS):
                out["status"] = "repeat"
                break
    return out


def audit_index(key, record, manifest, frozen, reports):
    idx = _index(record)
    sha = record.get("sha256")
    result = {"key": key, "sha256": sha, "ready": False, "errors": [], "surahs": [],
              "missingAyahs": [], "missingEndEvidence": 0, "endEvidenceSupported": False}
    errors = result["errors"]
    if not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
        errors.append("invalidIndexSha")
    for label, actual in (("public", record.get("publicSha")), ("frozen", frozen.get(key)),
                          ("manifest", (manifest.get(key) or {}).get("sha256"))):
        if actual != sha or not actual:
            errors.append(label + "ShaMismatchOrMissing")
    riwaya, filename = key.split("/")[1:]
    if idx.get("riwaya") != riwaya or idx.get("reciterId") != filename[:-3]:
        errors.append("headerKeyIdentityMismatch")
    entries = idx.get("entries") or []
    result["entries"] = len(entries)
    if (manifest.get(key) or {}).get("entries") != len(entries):
        errors.append("manifestEntryCountMismatch")
    per, seen = {}, set()
    for entry in entries:
        aid = entry.get("ayahId")
        try:
            s, a = map(int, aid.split(":"))
            if not 1 <= s <= 114 or not 1 <= a <= COUNTS[s - 1] or aid != f"{s}:{a}":
                raise ValueError("range")
        except (AttributeError, TypeError, ValueError):
            errors.append(f"invalidAyah:{aid}")
            continue
        if aid in seen:
            errors.append(f"duplicateAyah:{aid}")
        seen.add(aid)
        st, en = entry.get("startMs"), entry.get("endMs")
        if not finite(st) or not finite(en) or st < 0 or en <= st:
            errors.append(f"invalidBoundary:{aid}")
            continue
        if not isinstance(entry.get("fileRef"), str) or not entry["fileRef"]:
            errors.append(f"missingFileRef:{aid}")
        per.setdefault(s, {})[a] = entry
    present = sorted(per)
    audio = idx.get("audioSha256")
    # القائمة القياسية 114 موضعاً حتى بعد إسقاط سورة؛ لا تنزاح البصمات بعدها.
    # تُقرأ أيضاً الصيغة المضغوطة التي يستعملها heard_gate عند تطابق عدد الحاضر.
    if isinstance(audio, list) and len(audio) == 114:
        audio_map = {s: audio[s - 1] for s in present}
    elif isinstance(audio, list) and len(audio) == len(present):
        audio_map = dict(zip(present, audio))
    else:
        audio_map = {}
    if not audio_map:
        errors.append("audioShaShapeMissingOrInvalid")
    candidates = [(name, rep) for name, rep in reports if report_matches(key, rep) and isinstance(rep.get("maps"), dict)]
    result["heardReportsForReciter"] = len(candidates)
    on_sha = [(name, rep) for name, rep in reports if rep.get("sha256") == sha]
    openers = [(name, rep) for name, rep in on_sha if str(rep.get("kind") or "").lower() == "openers"]
    result["openers"] = {"exactShaReports": len(openers), "unresolved": [], "ready": False}
    if openers:
        name, op = max(openers, key=lambda pair: pair[1].get("ts") if finite(pair[1].get("ts")) else 0)
        result["openers"]["key"] = name
        for field in ("unknown", "suspect", "tail", "swallowed", "lateConfirmed"):
            if op.get(field):
                result["openers"]["unresolved"].append({"field": field, "surahs": op[field]})
        defects = (op.get("openers") or {}).get("defects") if isinstance(op.get("openers"), dict) else None
        if defects:
            result["openers"]["unresolved"].append({"field": "defects", "surahs": defects})
        late_trusted = not op.get("late") or op.get("_completionLateTrusted") is True
        result["openers"]["ready"] = (op.get("scope") == "full" and op.get("checked") == 114
                                              and op.get("_completionToolTrusted") is True
                                              and "late" in op and late_trusted
                                              and not result["openers"]["unresolved"])
    census = [(name, rep) for name, rep in on_sha if isinstance(rep.get("census"), dict)]
    result["census"] = {"exactShaReports": len(census), "unresolved": [], "checkedAyahs": 0}
    if census:
        name, rep = max(census, key=lambda pair: pair[1].get("ts") if finite(pair[1].get("ts")) else 0)
        cr = (rep.get("sample") or {}).get("rows") or []
        result["census"].update(key=name, checkedAyahs=len({r.get("aid") for r in cr}))
        result["census"]["unresolved"] = [{"ayahId": r.get("aid"), "kind": r.get("kind"), "verdict": r.get("verdict")}
                                              for r in cr if r.get("kind") in ("غير حاسم", "جسيم") or r.get("verdict") == "تعذّر"]
        if rep.get("fatal") or (rep.get("sample") or {}).get("errors"):
            errors.append("censusFatalOrReadError")
    for s, count in enumerate(COUNTS, 1):
        mine = per.get(s, {})
        missing = [f"{s}:{a}" for a in range(1, count + 1) if a not in mine]
        result["missingAyahs"].extend(missing)
        sr = {"surah": s, "expected": count, "present": len(mine), "missing": missing,
              "missingEndEvidence": len(mine), "unmeasured": [], "deviations": [],
              "conflictingEvidence": [], "evidence": [], "startsReady": False}
        result["missingEndEvidence"] += len(mine)
        sequence = [mine[a] for a in sorted(mine)]
        for left, right in zip(sequence, sequence[1:]):
            if left.get("fileRef") == right.get("fileRef") and right["startMs"] < left["endMs"] - 50:
                errors.append(f"overlapOrRegression:{left['ayahId']}:{right['ayahId']}")
        refs = {e.get("fileRef") for e in sequence}
        want_audio = audio_map.get(s)
        compatible = []
        for name, rep in candidates:
            cmap = _map(rep, s)
            if not isinstance(cmap, dict):
                continue
            if (cmap.get("surah") != s or not isinstance(want_audio, str) or not SHA_RE.fullmatch(want_audio)
                    or cmap.get("sha256") != want_audio or len(refs) != 1 or cmap.get("fileRef") not in refs):
                continue
            compatible.append((name, rep, cmap))
        compatible.sort(key=lambda item: (item[1].get("sha256") == sha,
                                          item[1].get("ts") if finite(item[1].get("ts")) else 0), reverse=True)
        if compatible:
            name, rep, cmap = compatible[0]
            sr["evidenceIndexSha"] = rep.get("sha256")
            sr["evidenceAudioSha"] = want_audio
            sr["evidenceBinding"] = "exactIndexSha" if rep.get("sha256") == sha else "recomputedOnSameAudioSha"
            judged = [start_row(entry, cmap) for entry in sequence]
            sr["unmeasured"] = [r["ayahId"] for r in judged if r["status"] == "unmeasured"]
            sr["deviations"] = [r for r in judged if r["status"] == "deviation"]
            sr["measuredStarts"] = sum(r["status"] in ("ok", "repeat") for r in judged)
            # لا نختار الخريطة التي تبرئ ونسكت عن شاهد مخالف على الصوت نفسه.
            for evidence_name, other, other_map in compatible:
                sr["evidence"].append({"key": evidence_name, "indexSha": other.get("sha256"),
                                       "run": other.get("run"), "ts": other.get("ts")})
                deviations = [r for e in sequence if (r := start_row(e, other_map))["status"] == "deviation"]
                if deviations:
                    sr["conflictingEvidence"].append({"key": evidence_name,
                                                     "ayahIds": [r["ayahId"] for r in deviations]})
        else:
            sr["unmeasured"] = [e["ayahId"] for e in sequence]
            sr["measuredStarts"] = 0
            sr["evidenceBinding"] = "missing"
        sr["startsReady"] = bool(mine) and not any((missing, sr["unmeasured"], sr["deviations"], sr["conflictingEvidence"]))
        result["surahs"].append(sr)
    result["startsReady"] = not errors and all(s["startsReady"] for s in result["surahs"])
    result["unmeasuredStarts"] = sum(len(s["unmeasured"]) for s in result["surahs"])
    result["deviations"] = sum(len(s["deviations"]) for s in result["surahs"])
    result["missingAyahCount"] = len(result["missingAyahs"])
    # ⛔ الدليل الحالي للبدء وحده؛ لا تصبح شهادة البدء شهادة النهاية.
    result["ready"] = (result["startsReady"] and result["missingEndEvidence"] == 0 and not result["missingAyahs"]
                       and result["openers"]["ready"] and not result["census"]["unresolved"])
    return result


def audit(snapshot, reports=()):
    errors = list(snapshot.get("errors") or [])
    try:
        manifest, frozen, duplicates = _identity_maps(snapshot)
    except (TypeError, ValueError, KeyError) as ex:
        manifest, frozen, duplicates = {}, {}, False
        errors.append(f"invalidIdentityDocuments:{type(ex).__name__}")
    if duplicates:
        errors.append("duplicateManifestKeys")
    indexes = snapshot.get("indexes") or {}
    if set(indexes) != set(manifest):
        errors.append("snapshotManifestKeySetMismatch")
    if len(indexes) != EXPECTED_INDEXES or len(manifest) != EXPECTED_INDEXES:
        errors.append("expected180Indexes")
    if not snapshot.get("stableRead"):
        errors.append("liveStabilityNotVerified")
    rows = []
    for key, record in sorted(indexes.items()):
        try:
            rows.append(audit_index(key, record, manifest, frozen, reports))
        except (TypeError, ValueError, KeyError, IndexError) as ex:
            rows.append({"key": key, "ready": False, "errors": [f"invalidIndex:{type(ex).__name__}"]})
    summary = {"indexes": len(rows), "expectedIndexes": EXPECTED_INDEXES,
               "manifestIndexes": len(manifest), "readyIndexes": sum(r["ready"] for r in rows),
               "startsReadyIndexes": sum(bool(r.get("startsReady")) for r in rows),
               "missingAyahs": sum(r.get("missingAyahCount", 0) for r in rows),
               "unmeasuredStarts": sum(r.get("unmeasuredStarts", 0) for r in rows),
               "deviations": sum(r.get("deviations", 0) for r in rows),
               "missingEndEvidence": sum(r.get("missingEndEvidence", 0) for r in rows)}
    return {"version": "completion-audit-1", "ready": not errors and bool(rows) and all(r["ready"] for r in rows),
            "timestampUtc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "snapshotTimestampUtc": snapshot.get("ts"), "errors": errors, "summary": summary, "indexes": rows,
            "measurementPolicy": {"startToleranceMs": TOL_MS, "minimumAnchorQuality": MIN_Q,
                                  "repeatSimilarity": REPEAT_SIM, "repeatNearMs": REPEAT_NEAR_MS,
                                  "unmeasuredStartsAllowed": 0, "endEvidenceSupported": False},
            "limits": ["تغطية البدء وحدها لا تثبت صحة endMs؛ لا شاهد نهاية مدعوم حالياً",
                       "موضع البدء مقارن بتقدير CTC بهامش 1500م.ث؛ ليس شهادة دقة سمعية مطلقة",
                       "لا قياس جديد للصوت ولا إثبات صوت القارئ من CTC",
                       "لا يتجاوز هذا التقرير بوابات المطالع والملوح والإحصاء والترقية القائمة",
                       "النتيجة تخص البصمات المقروءة؛ أي ترقية لاحقة تستلزم إعادة التدقيق"]}


def collect_live():
    """GET/LIST/HEAD فقط. فشل قراءة أو تغير أثناء الجمع يمنع جاهزية الجرد."""
    import promote as P  # الصلاحيات موجودة في بيئة agent_cmd، لا تُنقل أو تُطبع
    client, bucket = P.s3()
    errors, etags = [], {}

    def get(key):
        response = client.get_object(Bucket=bucket, Key=key)
        etags[key] = response.get("ETag")
        return response["Body"].read()

    def list_keys(prefix):
        return sorted(o["Key"] for pg in client.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix)
                      for o in pg.get("Contents", []))

    side = {}
    for key in ("timings/manifest.json", "timings/frozen.txt"):
        try:
            side[key] = get(key).decode("utf-8")
        except Exception as ex:
            errors.append(f"readError:{key}:{type(ex).__name__}")
    keys = [k for k in list_keys("timings/") if k.endswith(".jz") and k.count("/") == 2]
    indexes = {}

    def fetch_index(key):
        try:
            raw = get(key)
            request = urllib.request.Request(P.PUBLIC.rstrip("/") + "/" + key,
                                             headers={"User-Agent": "Mozilla/5.0 (rafiq-completion-audit/1)"})
            with urllib.request.urlopen(request, timeout=90) as response:
                public_sha = hashlib.sha256(response.read()).hexdigest()
            return key, {"sha256": hashlib.sha256(raw).hexdigest(), "publicSha": public_sha,
                         "index": json.loads(gzip.decompress(raw))}, None
        except Exception as ex:
            return key, None, f"readError:{key}:{type(ex).__name__}"

    with ThreadPoolExecutor(max_workers=8) as pool:
        for key, record, error in pool.map(fetch_index, keys):
            if error:
                errors.append(error)
            else:
                indexes[key] = record
    print(f"قُرئ {len(indexes)}/{len(keys)} فهرساً منشوراً؛ تُجمع خرائط السماع", flush=True)
    reports = []

    def fetch_report(key):
        try:
            return key, json.loads(get(key)), None
        except Exception as ex:
            return key, None, f"readError:{key}:{type(ex).__name__}"

    report_keys = [k for k in list_keys("state-heard/") if k.endswith(".json")]
    report_keys += [k for k in list_keys("state-census/") if k.endswith(".json")]
    for prefix in P.STATE_PREFIXES:
        report_keys += [k for k in list_keys(prefix) if "openers" in k and k.endswith(".json")]
    current_shas = {r["sha256"] for r in indexes.values()}
    with ThreadPoolExecutor(max_workers=8) as pool:
        for key, report, error in pool.map(fetch_report, sorted(set(report_keys))):
            if error:
                errors.append(error)
            else:
                for rep in report if isinstance(report, list) else [report]:
                    if not isinstance(rep, dict):
                        errors.append(f"invalidEvidenceReport:{key}")
                        continue
                    # التقارير القديمة غير اللازمة لا تستدعي حراس المطالع. الخطأ
                    # في تقرير لازم يبقى تشخيصاً ولا يمحو الفهارس التي قُرئت.
                    if not key.startswith("state-heard/") and rep.get("sha256") not in current_shas:
                        continue
                    try:
                        if key.startswith("state-heard/"):
                            if rep.get("version") != "heard-gate-1" or not isinstance(rep.get("maps"), dict):
                                raise ValueError("heard-schema")
                            if rep.get("kind") not in (None, "heard", "heard-gate", "heard_gate"):
                                raise ValueError("heard-kind")
                        elif key.startswith("state-census/"):
                            sample = rep.get("sample")
                            if (not isinstance(rep.get("census"), dict) or not isinstance(sample, dict)
                                    or not isinstance(sample.get("rows"), list)
                                    or any(not isinstance(r, dict) for r in sample["rows"])):
                                raise ValueError("census-schema")
                        else:
                            if str(rep.get("kind") or "").lower() != "openers":
                                raise ValueError("openers-kind")
                            rep["_completionToolTrusted"] = P.openers_tool_ok(rep)
                            rep["_completionLateTrusted"] = P.late_ctc_trusted(rep)
                    except Exception as ex:
                        errors.append(f"invalidEvidenceReport:{key}:{type(ex).__name__}")
                        continue
                    reports.append((key, rep))
    print(f"قُرئت {len(reports)} خريطة/حزمة سماع؛ تُراجع ثبات البصمات", flush=True)

    def check_stable(item):
        key, etag = item
        try:
            current = client.head_object(Bucket=bucket, Key=key).get("ETag")
            return None if etag and current == etag else f"changedDuringAudit:{key}"
        except Exception as ex:
            return f"stabilityError:{key}:{type(ex).__name__}"

    with ThreadPoolExecutor(max_workers=8) as pool:
        errors.extend(e for e in pool.map(check_stable, list(etags.items())) if e)
    if keys != [k for k in list_keys("timings/") if k.endswith(".jz") and k.count("/") == 2]:
        errors.append("indexKeySetChangedDuringAudit")
    return {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "indexes": indexes,
            "side": side, "errors": errors, "stableRead": not errors}, reports


def ayah_ranges(ids):
    """ضغط بلا فقد: [السورة، أول آية، آخر آية شامل]، مع حفظ الترتيب والتكرار."""
    ranges = []
    for aid in ids:
        s, a = map(int, aid.split(":"))
        if ranges and ranges[-1][0] == s and ranges[-1][2] + 1 == a:
            ranges[-1][2] = a
        else:
            ranges.append([s, a, a])
    return ranges


def compact_report(report):
    """يُضغط تمثيل المواضع فقط؛ لا يُسقط unknown أو انحراف أو دليل متناقض."""
    report["rangeEncoding"] = {"format": "[surah,firstAyah,lastAyahInclusive]", "lossless": True}
    for index in report["indexes"]:
        if "missingAyahs" in index:
            index["missingAyahRanges"] = ayah_ranges(index.pop("missingAyahs"))
        for surah in index.get("surahs") or []:
            for field in ("missing", "unmeasured"):
                ids = surah.pop(field)
                surah[field + "Count"] = len(ids)
                surah[field + "Ranges"] = ayah_ranges(ids)
            for conflict in surah.get("conflictingEvidence") or []:
                ids = conflict.pop("ayahIds")
                conflict["ayahCount"] = len(ids)
                conflict["ayahRanges"] = ayah_ranges(ids)
        # حافظ على ترتيب أحكام الإحصاء، واجمع الصفوف المتجاورة المتساوية فقط.
        census = index.get("census") or {}
        if "unresolved" in census:
            unresolved = census.pop("unresolved")
            groups = []
            for row in unresolved:
                signature = {k: v for k, v in row.items() if k != "ayahId"}
                aid = row.get("ayahId")
                if not isinstance(aid, str) or not re.fullmatch(r"\d+:\d+", aid):
                    groups.append({"raw": row})
                    continue
                if groups and groups[-1].get("status") == signature:
                    groups[-1]["ids"].append(aid)
                else:
                    groups.append({"status": signature, "ids": [aid]})
            for group in groups:
                if "ids" in group:
                    ids = group.pop("ids")
                    group.update(ayahCount=len(ids), ayahRanges=ayah_ranges(ids))
            census.update(unresolvedCount=len(unresolved), unresolvedGroups=groups)
    return report


def markdown(report):
    s = report["summary"]
    lines = ["# تدقيق اكتمال الفهرسة", "", f"- الجاهزية: **{'مثبتة' if report['ready'] else 'غير مكتملة الإثبات'}**.",
             f"- الفهارس المقروءة: {s['indexes']}/180؛ جاهزية البدء: {s['startsReadyIndexes']}.",
             f"- الآيات الناقصة: {s['missingAyahs']}؛ البدء غير المقيس: {s['unmeasuredStarts']}؛ الانحراف: {s['deviations']}.",
             f"- مداخل بلا شهادة نهاية: {s['missingEndEvidence']}؛ لا تُستنتج النهاية من شهادة البدء.", "",
             "| الفهرس | البصمة | نقص | بدء غير مقيس | انحراف | بلا شهادة نهاية |", "|---|---|---:|---:|---:|---:|"]
    for r in report["indexes"]:
        lines.append(f"| {r['key']} | {(r.get('sha256') or '')[:12]} | {r.get('missingAyahCount', '?')} | "
                     f"{r.get('unmeasuredStarts', '?')} | {r.get('deviations', '?')} | {r.get('missingEndEvidence', '?')} |")
    lines += ["", "الأخطاء العامة: " + ("، ".join(report["errors"]) or "لا أخطاء في القراءة والهوية العامة"), ""]
    lines += ["- " + limit for limit in report["limits"]]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="قارئ اكتمال مستقل؛ لا كتابة في الدلو أو تشغيل صوتي")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--live", action="store_true")
    mode.add_argument("--snapshot", help="تصدير audit_export أو حزمة جمع محفوظة")
    parser.add_argument("--evidence", action="append", default=[], help="ملف JSON/JSON.gz لحكم state-heard؛ قابل للتكرار")
    parser.add_argument("--out", default="ops/out/completion-audit.json")
    args = parser.parse_args()
    path = (ROOT / args.out).resolve()
    if not path.is_relative_to((ROOT / "ops/out").resolve()) or path.suffix != ".json":
        parser.error("المخرَج JSON تحت ops/out وحده")
    if args.live:
        try:
            snapshot, reports = collect_live()
        except Exception as ex:
            snapshot, reports = {"errors": [f"collectionFailed:{type(ex).__name__}"], "indexes": {}}, []
    else:
        snapshot, reports = read_json(args.snapshot), []
    for evidence in args.evidence:
        reports.append((str(evidence), read_json(evidence)))
    report = compact_report(audit(snapshot, reports))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    path.with_suffix(".md").write_text(markdown(report), encoding="utf-8")
    print(json.dumps({"ready": report["ready"], "summary": report["summary"], "errors": report["errors"],
                      "out": str(path.relative_to(ROOT))}, ensure_ascii=False), flush=True)
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
