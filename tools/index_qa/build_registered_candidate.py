#!/usr/bin/env python3
"""يبني مرشح سورة مسجّلة محلياً؛ لا شبكة ولا أسرار ولا كتابة إلى الدلو.

الملف الناتج غير منشور، ويحتاج فحوص الجودة والسماع القائمة على بصمته.
لا يصنع هذا الأمر حدوداً أو نصاً؛ ينقل حدود ctc_heard_map المقيسة بعد التحقق
من هوية المصدر، ويستعمل splice_surah وحراس التحويل المحلية القائمة.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import math
import os
import re
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/ci_fleet"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import source_registry
import splice_surah
import stage_transform

ENGINE = "ctc-heardmap-1"
OP = "ctc_heardmap_splice"
SHA_RE = re.compile(r"[0-9a-f]{64}")


def sha256(blob):
    return hashlib.sha256(blob).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def checked_output(path):
    """لا يكتب المرشح خارج مجلده، ولا يستبدل ملفاً أو يتبع رابطاً رمزياً."""
    supplied = Path(path)
    target = supplied if supplied.is_absolute() else Path.cwd() / supplied
    target = Path(os.path.abspath(target))
    allowed = ROOT / "ops/source-repair/candidates"
    require(target.parent == allowed and target.suffix == ".jz",
            "المخرج يجب أن يكون ops/source-repair/candidates/<اسم>.jz")
    require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*\.jz", target.name),
            "اسم المرشح غير صالح")
    require(not any(p.is_symlink() for p in (target, *target.parents)),
            "مسار المرشح لا يقبل الروابط الرمزية")
    require(not target.exists(), "ملف المرشح موجود؛ لا يُستبدل")
    return target


def checked_parent_key(parent, parent_sha, key=None):
    riwaya, reciter = parent.get("riwaya"), parent.get("reciterId")
    require(all(isinstance(v, str) and re.fullmatch(r"[A-Za-z0-9_-]+", v)
                for v in (riwaya, reciter)), "هوية الأصل غير صالحة")
    published = f"timings/{riwaya}/{reciter}.jz"
    staged = f"timings-staging/{riwaya}/{reciter}.{parent_sha[:8]}.jz"
    require(key is None or key in (published, staged),
            "مفتاح الأصل لا يطابق هويته وبصمته")
    return key or published


def checked_alignment(parent, aligned, surah, source):
    """تطابق القياس مع السجل؛ الأسماء البديلة تنقل البيانات نفسها فقط."""
    require(type(surah) is int and 1 <= surah <= 114, "رقم السورة غير صالح")
    require(aligned.get("surah") == surah and type(aligned.get("surah")) is int,
            "المحاذاة تخص سورة أخرى")
    require(aligned.get("riwaya") == parent.get("riwaya"), "رواية المحاذاة تختلف عن الأصل")
    require(aligned.get("engine") == ENGINE, "المحاذاة ليست ناتج ctc_heard_map")
    require(SHA_RE.fullmatch(str(source.get("audio_sha256") or "")),
            "المصدر المسجّل يحتاج بصمة صوت كاملة")
    require(aligned.get("fileRef") == source["url"], "رابط القياس لا يطابق المصدر المسجّل")
    require(aligned.get("sha256") == source["audio_sha256"],
            "بصمة القياس لا تطابق المصدر المسجّل")
    for alias, measured in (("sourceUrl", "fileRef"), ("audioSha256", "sha256")):
        require(alias not in aligned or aligned[alias] == aligned[measured],
                "بيانات القياس تحمل هويتين مختلفتين للمصدر")
    n = splice_surah.COUNTS[surah - 1]
    rows = aligned.get("entries")
    require(isinstance(rows, list) and len(rows) == n,
            "المطلوب محاذاة كاملة؛ خريطة الاستكشاف وحدها لا تبني مرشحاً")
    require(isinstance(aligned.get("heardMap"), dict)
            and set(aligned["heardMap"]) == {str(i) for i in range(1, n + 1)},
            "خريطة القياس غائبة أو ناقصة")
    duration = aligned.get("totalMs")
    require(type(duration) in (int, float) and math.isfinite(duration) and duration > 0,
            "مدة الصوت غير صالحة")
    previous = -1
    for i, row in enumerate(rows):
        require(isinstance(row, dict) and type(row.get("ayahIdx")) is int
                and row["ayahIdx"] == i, "ترتيب آيات القياس غير متصل")
        start, end, conf = row.get("startMs"), row.get("endMs"), row.get("conf")
        require(type(start) is int and type(end) is int
                and 0 <= start < end <= duration and start >= previous,
                f"حدود الآية {i + 1} ناقصة أو متداخلة أو خارج الصوت")
        require(type(conf) in (int, float) and math.isfinite(conf) and 0 <= conf <= 1,
                f"ثقة الآية {i + 1} غير صالحة")
        previous = end
    adapted = copy.deepcopy(aligned)
    adapted.update(sourceUrl=aligned["fileRef"], audioSha256=aligned["sha256"])
    return adapted


def check_preserved(parent, candidate, surah, source):
    """لا تتبدل مداخل أو بصمات أو إعلانات السور الأخرى ولو مر الدمج."""
    def outside(entries):
        return [e for e in entries if int(e["ayahId"].split(":")[0]) != surah]
    old, new = parent.get("entries") or [], candidate.get("entries") or []
    require(outside(old) == outside(new), "تغير مدخل خارج السورة المطلوبة")
    old_shas, new_shas = parent.get("audioSha256"), candidate.get("audioSha256")
    require(isinstance(old_shas, list) and len(old_shas) == 114
            and isinstance(new_shas, list) and len(new_shas) == 114,
            "المصدر المسجّل يتطلب قائمة بصمات أصلية من 114 سورة")
    require(new_shas == old_shas[:surah - 1] + [source["audio_sha256"]] + old_shas[surah:],
            "تغيرت بصمة صوت خارج السورة المطلوبة")
    for field in sorted(set(parent) | set(candidate)):
        if not field.endswith("BySurah"):
            continue
        before, after = parent.get(field) or {}, candidate.get(field) or {}
        require(isinstance(before, dict) and isinstance(after, dict), f"حقل {field} ليس قاموساً")
        require({k: v for k, v in before.items() if k != str(surah)}
                == {k: v for k, v in after.items() if k != str(surah)},
                f"تغير إعلان {field} خارج السورة المطلوبة")
    for field in ("riwaya", "reciterId", "engineVersion", "refineVersion", "ayahCount"):
        require(parent.get(field) == candidate.get(field), f"تغير حقل الأصل {field}")
    require((candidate.get("sourceBySurah") or {}).get(str(surah)) == source["url"],
            "المصدر البديل غير معلن كما قيس")
    old_refs = {e.get("fileRef") for e in old if e["ayahId"].startswith(f"{surah}:")}
    require(source["url"] not in old_refs
            or (parent.get("sourceBySurah") or {}).get(str(surah)) == source["url"],
            "المصدر لم يتغير ولا يحمل إعلانه السابق؛ لا يُسمى بديلاً بصمت")
    if candidate.get("engineVersion") != ENGINE:
        require((candidate.get("engineBySurah") or {}).get(str(surah)) == ENGINE,
                "محرك السورة غير معلن")
    old_ids, new_ids = {e["ayahId"] for e in old}, {e["ayahId"] for e in new}
    recovered = len(new_ids - old_ids)
    old_reasons = (parent.get("missing") or {}).get("byReason") or {}
    new_reasons = (candidate.get("missing") or {}).get("byReason") or {}
    for reason in old_reasons.keys() | new_reasons.keys():
        decrease = old_reasons.get(reason, 0) - new_reasons.get(reason, 0)
        require(0 <= decrease <= recovered,
                "تغير تفسير غياب لا تبرره المداخل المسترجعة؛ يلزم قياس منفصل")
    why = stage_transform.realigned_coverage_error(old_ids, new_ids, [surah])
    require(not why, why)
    require({e["ayahId"] for e in new if e["ayahId"].startswith(f"{surah}:")}
            == {f"{surah}:{a}" for a in range(1, splice_surah.COUNTS[surah - 1] + 1)},
            "معرفات السورة لا تطابق العدد الكامل")
    require(stage_transform.entries_sha(old) != stage_transform.entries_sha(new),
            "المداخل لم تتغير؛ لا إصلاح هنا")


def repaired_transform(parent, candidate, surah, parent_sha, parent_key):
    """يحفظ أثر الأصل كتاريخ، ويزيل إعلان السورة المسترجعة وحدها."""
    transform = copy.deepcopy(candidate.get("transform") or {})
    # الأثر السابق كامل ومحفوظ ببصمة ملفه، ولا يصف حالة المرشح الحالية.
    transform["provenance"] = {
        "kind": "historical-parent-transform",
        "parentSha256": parent_sha,
        "parentKey": parent_key,
        "parentTransform": copy.deepcopy(parent.get("transform")),
    }
    if isinstance(transform.get("truncatedTail"), dict):
        transform["truncatedTail"].pop(str(surah), None)
    # العدّادان يخصّان عملية إسقاط قديمة؛ أعداد التحويل الحالي تحسب من المداخل.
    for field in ("droppedEntries", "gapAyahs"):
        transform.pop(field, None)
    # بيان الغياب المشترك مطلوب ما دام بتر سورة أخرى قائماً، ولا يرثه فهرس كامل.
    missing_reasons = (candidate.get("missing") or {}).get("byReason") or {}
    remaining_truncation = (transform.get("truncatedTail") or transform.get("dropSurah")
                            or missing_reasons.get("source_truncated", 0))
    if transform.get("reasonCode") == "SOURCE_TRUNCATED" and not remaining_truncation:
        transform.pop("reasonCode", None)
        transform.pop("reasonUser", None)
    return transform


def build(parent_path, parent_sha, aligned_path, surah, out_path, *, parent_key=None):
    require(SHA_RE.fullmatch(str(parent_sha)), "بصمة الأصل يجب أن تكون كاملة")
    target = checked_output(out_path)
    parent_blob = Path(parent_path).read_bytes()
    require(sha256(parent_blob) == parent_sha, "بصمة ملف الأصل لا تطابق المطلوبة")
    parent = json.loads(gzip.decompress(parent_blob))
    key = checked_parent_key(parent, parent_sha, parent_key)
    require(isinstance(parent.get("audioSha256"), list)
            and len(parent["audioSha256"]) == 114,
            "الأصل لا يحمل قائمة بصمات من 114 سورة")
    require(parent.get("transform") is None or isinstance(parent["transform"], dict),
            "صيغة أثر التحويل القديمة تحتاج مراجعة قبل الدمج المسجّل")
    aligned_blob = Path(aligned_path).read_bytes()
    aligned = json.loads(aligned_blob)
    source = source_registry.registered_source(parent["riwaya"], parent["reciterId"], surah)
    adapted = checked_alignment(parent, aligned, surah, source)
    require(stage_transform.promote.SPLICE_OPS.get(OP) == ENGINE,
            "محرك التحويل لا يطابق سجل حارس الترقية")
    # النسخ المؤقتة تثبت المدخلات خلال استدعاء الأداة القائمة، ولا تعيد تنزيل الصوت.
    with tempfile.TemporaryDirectory(prefix="registered-candidate-") as tmp:
        tmp = Path(tmp)
        saved_parent, saved_aligned, merged = tmp / "parent.jz", tmp / "aligned.json", tmp / "merged.jz"
        saved_parent.write_bytes(parent_blob)
        saved_aligned.write_text(json.dumps(adapted, ensure_ascii=False, allow_nan=False), encoding="utf-8")
        previous_args = sys.argv
        sys.argv = [splice_surah.__file__, "--index", str(saved_parent), "--surah", str(surah),
                    "--aligned", str(saved_aligned), "--url", source["url"], "--out", str(merged),
                    "--registered-sources", "--alt-source", "--engine-tag", ENGINE]
        try:
            splice_surah.main()
        finally:
            sys.argv = previous_args
        require(Path(str(merged) + ".taken").read_text(encoding="utf-8") == str(surah),
                "الدمج لم يأخذ السورة المطلوبة وحدها")
        candidate = json.loads(gzip.decompress(merged.read_bytes()))
    require(source_registry.registered_source(parent["riwaya"], parent["reciterId"], surah) == source,
            "تغير سجل المصدر أثناء البناء")
    require(sha256(Path(parent_path).read_bytes()) == parent_sha
            and sha256(Path(aligned_path).read_bytes()) == sha256(aligned_blob),
            "تغيرت مدخلات البناء أثناء العمل")
    check_preserved(parent, candidate, surah, source)
    old_entries, new_entries = parent["entries"], candidate["entries"]
    # هذا عدّاد مشتق لا حكم جديد على الثقة؛ تبقى الأشرطة والحدود كما قيسَت.
    if "lowCount" in candidate:
        candidate["lowCount"] = sum(e.get("confBand") == "LOW" for e in new_entries)
    moved, added, removed = stage_transform.entry_change_counts(old_entries, new_entries)
    transform = repaired_transform(parent, candidate, surah, parent_sha, key)
    transform.update(op=f"{OP}:{surah}", fromSha256=parent_sha, fromKey=key,
                     entriesSha256=stage_transform.entries_sha(new_entries),
                     parentEntriesSha256=stage_transform.entries_sha(old_entries),
                     movedEntries=moved, addedEntries=added, removedEntries=removed,
                     reason=f"إعادة قياس السورة {surah} كاملة من مصدر مسجّل مطابق لبصمة الصوت",
                     by="build_registered_candidate", at=int(time.time() * 1000),
                     note="مرشح محلي غير منشور؛ يلزمه حكم الجودة والسماع على بصمته.",
                     unpublishedLocalCandidate=True,
                     sourceRepair={"surah": surah, "sourceUrl": source["url"],
                                   "audioSha256": source["audio_sha256"],
                                   "alignedSha256": sha256(aligned_blob),
                                   "registryEvidence": source["evidence"]})
    candidate["transform"] = transform
    why = stage_transform.promote.index_gate(candidate, parent=parent, parent_sha=parent_sha)
    require(not why, f"حارس بنية الفهرس: {why}")
    payload = gzip.compress(json.dumps(candidate, ensure_ascii=False, allow_nan=False,
                                       separators=(",", ":")).encode("utf-8"), compresslevel=9, mtime=0)
    target.parent.mkdir(parents=True, exist_ok=True)
    checked_output(target)
    # نشر محلي ذري بلا استبدال؛ الفحص أو النشر الخارجي ليسا جزءاً من هذه الأداة.
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".candidate-", delete=False) as fh:
        temporary = Path(fh.name)
        try:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
            os.link(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    digest = sha256(payload)
    return {"path": str(target.relative_to(ROOT)), "sha256": digest,
            "key": f"timings-staging/{parent['riwaya']}/{parent['reciterId']}.{digest[:8]}.jz",
            "parentSha256": parent_sha, "alignedSha256": sha256(aligned_blob),
            "surah": surah, "unpublishedLocalCandidate": True,
            "qualityChecks": "pending", "heardGate": "pending"}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parent", required=True, help="ملف الأصل المحلي .jz")
    ap.add_argument("--parent-sha", required=True)
    ap.add_argument("--parent-key", help="مفتاح الأصل الموثق؛ الافتراضي timings/<رواية>/<قارئ>.jz")
    ap.add_argument("--aligned", required=True)
    ap.add_argument("--surah", required=True, type=int)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    try:
        report = build(a.parent, a.parent_sha, a.aligned, a.surah, a.out, parent_key=a.parent_key)
    except (ValueError, OSError, KeyError, TypeError) as ex:
        raise SystemExit(f"⛔ {ex}") from ex
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
