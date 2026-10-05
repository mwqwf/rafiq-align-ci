#!/usr/bin/env python3
"""يبني مرشح سورة أو سور مسجّلة من أصل واحد؛ لا شبكة ولا أسرار ولا كتابة إلى الدلو.

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


def selected_surahs(surah):
    """قائمة صريحة بلا تكرار؛ يبقى رقم السورة المفرد مقبولاً."""
    surahs = [surah] if type(surah) is int else list(surah)
    require(surahs and all(type(s) is int and 1 <= s <= 114 for s in surahs),
            "أرقام السور غير صالحة")
    require(len(surahs) == len(set(surahs)), "لا يجوز تكرار سورة في البناء")
    return surahs


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
    surahs = selected_surahs(surah)
    sources = {surahs[0]: source} if type(surah) is int else source
    named = {str(s) for s in surahs}
    def outside(entries):
        return [e for e in entries if e["ayahId"].split(":")[0] not in named]
    old, new = parent.get("entries") or [], candidate.get("entries") or []
    require(outside(old) == outside(new), "تغير مدخل خارج السورة المطلوبة")
    old_shas, new_shas = parent.get("audioSha256"), candidate.get("audioSha256")
    require(isinstance(old_shas, list) and len(old_shas) == 114
            and isinstance(new_shas, list) and len(new_shas) == 114,
            "المصدر المسجّل يتطلب قائمة بصمات أصلية من 114 سورة")
    expected_shas = list(old_shas)
    for s in surahs:
        expected_shas[s - 1] = sources[s]["audio_sha256"]
    require(new_shas == expected_shas,
            "تغيرت بصمة صوت خارج السورة المطلوبة")
    for field in sorted(set(parent) | set(candidate)):
        if not field.endswith("BySurah"):
            continue
        before, after = parent.get(field) or {}, candidate.get(field) or {}
        require(isinstance(before, dict) and isinstance(after, dict), f"حقل {field} ليس قاموساً")
        require({k: v for k, v in before.items() if k not in named}
                == {k: v for k, v in after.items() if k not in named},
                f"تغير إعلان {field} خارج السورة المطلوبة")
    for field in ("riwaya", "reciterId", "engineVersion", "refineVersion", "ayahCount"):
        require(parent.get(field) == candidate.get(field), f"تغير حقل الأصل {field}")
    for s in surahs:
        require((candidate.get("sourceBySurah") or {}).get(str(s)) == sources[s]["url"],
                "المصدر البديل غير معلن كما قيس")
        old_refs = {e.get("fileRef") for e in old if e["ayahId"].startswith(f"{s}:")}
        require(sources[s]["url"] not in old_refs
                or (parent.get("sourceBySurah") or {}).get(str(s)) == sources[s]["url"],
                "المصدر لم يتغير ولا يحمل إعلانه السابق؛ لا يُسمى بديلاً بصمت")
        if candidate.get("engineVersion") != ENGINE:
            require((candidate.get("engineBySurah") or {}).get(str(s)) == ENGINE,
                    "محرك السورة غير معلن")
    old_ids, new_ids = {e["ayahId"] for e in old}, {e["ayahId"] for e in new}
    recovered = len(new_ids - old_ids)
    old_reasons = (parent.get("missing") or {}).get("byReason") or {}
    new_reasons = (candidate.get("missing") or {}).get("byReason") or {}
    for reason in old_reasons.keys() | new_reasons.keys():
        decrease = old_reasons.get(reason, 0) - new_reasons.get(reason, 0)
        require(0 <= decrease <= recovered,
                "تغير تفسير غياب لا تبرره المداخل المسترجعة؛ يلزم قياس منفصل")
    why = stage_transform.realigned_coverage_error(old_ids, new_ids, surahs)
    require(not why, why)
    for s in surahs:
        require({e["ayahId"] for e in new if e["ayahId"].startswith(f"{s}:")}
                == {f"{s}:{a}" for a in range(1, splice_surah.COUNTS[s - 1] + 1)},
                "معرفات السورة لا تطابق العدد الكامل")
    require(stage_transform.entries_sha(old) != stage_transform.entries_sha(new),
            "المداخل لم تتغير؛ لا إصلاح هنا")


def repaired_transform(parent, candidate, surah, parent_sha, parent_key):
    """يحفظ أثر الأصل كتاريخ، ويزيل إعلانات السور المسترجعة وحدها."""
    transform = copy.deepcopy(candidate.get("transform") or {})
    surahs = selected_surahs(surah)
    # الأثر السابق كامل ومحفوظ ببصمة ملفه، ولا يصف حالة المرشح الحالية.
    transform["provenance"] = {
        "kind": "historical-parent-transform",
        "parentSha256": parent_sha,
        "parentKey": parent_key,
        "parentTransform": copy.deepcopy(parent.get("transform")),
        "parentMissing": copy.deepcopy(parent.get("missing")),
    }
    if isinstance(transform.get("truncatedTail"), dict):
        for s in surahs:
            transform["truncatedTail"].pop(str(s), None)
    if isinstance(transform.get("dropSurah"), list):
        transform["dropSurah"] = [s for s in transform["dropSurah"] if s not in surahs]
    # العدّادان يخصّان عملية إسقاط قديمة؛ أعداد التحويل الحالي تحسب من المداخل.
    for field in ("droppedEntries", "gapAyahs"):
        transform.pop(field, None)
    # بيان الغياب المشترك مطلوب ما دام عطب مصدر سورة أخرى قائماً، ولا يرثه فهرس كامل.
    missing_reasons = (candidate.get("missing") or {}).get("byReason") or {}
    remaining_source_problem = (transform.get("truncatedTail") or transform.get("dropSurah")
                                or missing_reasons.get("source_truncated", 0)
                                or missing_reasons.get("source_corrupt", 0))
    if transform.get("reasonCode") in ("SOURCE_TRUNCATED", "SOURCE_CORRUPT") and not remaining_source_problem:
        transform.pop("reasonCode", None)
        transform.pop("reasonUser", None)
    return transform


def build(parent_path, parent_sha, aligned_path, surah, out_path, *, parent_key=None):
    require(SHA_RE.fullmatch(str(parent_sha)), "بصمة الأصل يجب أن تكون كاملة")
    surahs = selected_surahs(surah)
    aligned_paths = list(aligned_path) if isinstance(aligned_path, (list, tuple)) else [aligned_path]
    require(len(aligned_paths) == len(surahs), "عدد ملفات المحاذاة لا يطابق عدد السور")
    selection = ",".join(str(s) for s in surahs)
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
    aligned_blobs = {s: Path(path).read_bytes() for s, path in zip(surahs, aligned_paths)}
    sources = {s: source_registry.registered_source(parent["riwaya"], parent["reciterId"], s)
               for s in surahs}
    adapted = {s: checked_alignment(parent, json.loads(aligned_blobs[s]), s, sources[s])
               for s in surahs}
    require(stage_transform.promote.SPLICE_OPS.get(OP) == ENGINE,
            "محرك التحويل لا يطابق سجل حارس الترقية")
    # النسخ المؤقتة تثبت المدخلات خلال استدعاء الأداة القائمة، ولا تعيد تنزيل الصوت.
    with tempfile.TemporaryDirectory(prefix="registered-candidate-") as tmp:
        tmp = Path(tmp)
        saved_parent, merged = tmp / "parent.jz", tmp / "merged.jz"
        saved_parent.write_bytes(parent_blob)
        saved_aligned = []
        for s in surahs:
            path = tmp / f"aligned-{s}.json"
            path.write_text(json.dumps(adapted[s], ensure_ascii=False, allow_nan=False), encoding="utf-8")
            saved_aligned.append(str(path))
        previous_args = sys.argv
        sys.argv = [splice_surah.__file__, "--index", str(saved_parent), "--surah", selection,
                    "--aligned", *saved_aligned, "--url", sources[surahs[0]]["url"], "--out", str(merged),
                    "--registered-sources", "--alt-source", "--engine-tag", ENGINE]
        try:
            splice_surah.main()
        finally:
            sys.argv = previous_args
        require(Path(str(merged) + ".taken").read_text(encoding="utf-8") == selection,
                "الدمج لم يأخذ السور المطلوبة وحدها")
        candidate = json.loads(gzip.decompress(merged.read_bytes()))
    require(all(source_registry.registered_source(parent["riwaya"], parent["reciterId"], s) == sources[s]
                for s in surahs),
            "تغير سجل المصدر أثناء البناء")
    require(sha256(Path(parent_path).read_bytes()) == parent_sha
            and all(Path(path).read_bytes() == aligned_blobs[s] for s, path in zip(surahs, aligned_paths)),
            "تغيرت مدخلات البناء أثناء العمل")
    # اكتمال المعرفات يزيل أسباب الغياب الحالية؛ نسخة الأصل باقية في النسب التاريخي.
    expected_ids = {f"{s}:{a}" for s, n in enumerate(splice_surah.COUNTS, 1) for a in range(1, n + 1)}
    if {e["ayahId"] for e in candidate["entries"]} == expected_ids:
        require(candidate["missing"]["count"] == 0 and not candidate["missing"].get("ids"),
                "وسم الغياب لا يطابق المعرفات الكاملة")
        candidate["missing"]["byReason"] = {}
    check_preserved(parent, candidate, surahs, sources)
    old_entries, new_entries = parent["entries"], candidate["entries"]
    # هذا عدّاد مشتق لا حكم جديد على الثقة؛ تبقى الأشرطة والحدود كما قيسَت.
    if "lowCount" in candidate:
        candidate["lowCount"] = sum(e.get("confBand") == "LOW" for e in new_entries)
    moved, added, removed = stage_transform.entry_change_counts(old_entries, new_entries)
    transform = repaired_transform(parent, candidate, surahs, parent_sha, key)
    source_repairs = {str(s): {"surah": s, "sourceUrl": sources[s]["url"],
                               "audioSha256": sources[s]["audio_sha256"],
                               "alignedSha256": sha256(aligned_blobs[s]),
                               "registryEvidence": sources[s]["evidence"]} for s in surahs}
    source_repair = (source_repairs[str(surahs[0])] if len(surahs) == 1
                     else {"surahs": surahs, "bySurah": source_repairs})
    transform.update(op=f"{OP}:{selection}", fromSha256=parent_sha, fromKey=key,
                     entriesSha256=stage_transform.entries_sha(new_entries),
                     parentEntriesSha256=stage_transform.entries_sha(old_entries),
                     movedEntries=moved, addedEntries=added, removedEntries=removed,
                     reason=f"إعادة قياس السور {selection} كاملة من مصادر مسجّلة مطابقة لبصمات الصوت",
                     by="build_registered_candidate", at=int(time.time() * 1000),
                     note="مرشح محلي غير منشور؛ يلزمه حكم الجودة والسماع على بصمته.",
                     unpublishedLocalCandidate=True,
                     sourceRepair=source_repair)
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
    report = {"path": str(target.relative_to(ROOT)), "sha256": digest,
              "key": f"timings-staging/{parent['riwaya']}/{parent['reciterId']}.{digest[:8]}.jz",
              "parentSha256": parent_sha, "surahs": surahs,
              "alignedSha256BySurah": {str(s): sha256(aligned_blobs[s]) for s in surahs},
              "unpublishedLocalCandidate": True, "qualityChecks": "pending", "heardGate": "pending"}
    if len(surahs) == 1:
        report.update(surah=surahs[0], alignedSha256=sha256(aligned_blobs[surahs[0]]))
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parent", required=True, help="ملف الأصل المحلي .jz")
    ap.add_argument("--parent-sha", required=True)
    ap.add_argument("--parent-key", help="مفتاح الأصل الموثق؛ الافتراضي timings/<رواية>/<قارئ>.jz")
    ap.add_argument("--aligned", required=True, nargs="+", help="ملفات المحاذاة بترتيب السور")
    ap.add_argument("--surah", required=True, help="سورة واحدة أو أكثر بفواصل، مثل 3,4")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    try:
        surahs = [int(s) for s in a.surah.split(",")]
        report = build(a.parent, a.parent_sha, a.aligned, surahs, a.out, parent_key=a.parent_key)
    except (ValueError, OSError, KeyError, TypeError) as ex:
        raise SystemExit(f"⛔ {ex}") from ex
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
