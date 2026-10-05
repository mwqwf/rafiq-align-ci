#!/usr/bin/env python3
"""مرشح محلي لتصحيح توقيت سورة أو سور كاملة من صوت أصل واحد، بلا شبكة أو رفع.

يثبت بصمة الأصل والصوت ومرجع الملف، ويستعمل الدمج والحراس القائمة.
لا يسترجع مداخل مفقودة ولا يسجل مصدراً بديلاً؛ تبقى فحوص الجودة معلقة.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_registered_candidate as shared

require = shared.require
sha256 = shared.sha256
splice_surah = shared.splice_surah
stage_transform = shared.stage_transform
ENGINE, OP = shared.ENGINE, shared.OP


def parent_source(parent, surah):
    """يؤخذ المصدر من المداخل والبصمة الأصلية، ولا يُستنتج من اسم القارئ."""
    require(type(surah) is int and 1 <= surah <= 114, "رقم السورة غير صالح")
    shas = parent.get("audioSha256")
    require(isinstance(shas, list) and len(shas) == 114
            and all(shared.SHA_RE.fullmatch(str(s)) for s in shas),
            "الأصل يحتاج 114 بصمة صوت كاملة")
    rows = [e for e in parent.get("entries", []) if e["ayahId"].startswith(f"{surah}:")]
    wanted = {f"{surah}:{a}" for a in range(1, splice_surah.COUNTS[surah - 1] + 1)}
    require(len(rows) == len(wanted) and {e["ayahId"] for e in rows} == wanted,
            "المسار خاص بسورة أصلية كاملة بلا مداخل مفقودة أو مكررة")
    refs = splice_surah.parent_refs(parent["entries"], [surah])
    return {"url": refs[surah], "audio_sha256": shas[surah - 1]}


def check_preserved(parent, candidate, surah, source):
    """لا تغيير خارج السور المختارة أو في هوية أصواتها أو أعداد الفهرس والغياب."""
    surahs = shared.selected_surahs(surah)
    sources = {surahs[0]: source} if type(surah) is int else source
    named = {str(s) for s in surahs}
    old, new = parent["entries"], candidate["entries"]
    outside = lambda rows: [e for e in rows if e["ayahId"].split(":")[0] not in named]
    require(outside(old) == outside(new), "تغير مدخل خارج السورة المطلوبة")
    require(len(old) == len(new)
            and [e["ayahId"] for e in old] == [e["ayahId"] for e in new],
            "تغير عدد المداخل أو ترتيب معرفاتها")
    require(candidate.get("audioSha256") == parent.get("audioSha256"),
            "تغيرت قائمة بصمات الصوت")
    require(candidate.get("sourceBySurah") == parent.get("sourceBySurah"),
            "تغير إعلان مصدر رغم ثبات الصوت")
    for s in surahs:
        require({e["fileRef"] for e in new if e["ayahId"].startswith(f"{s}:")}
                == {sources[s]["url"]}, f"تغير مرجع ملف السورة {s}")
    for field in ("riwaya", "reciterId", "engineVersion", "refineVersion", "ayahCount", "missing"):
        require(candidate.get(field) == parent.get(field), f"تغير حقل الأصل {field}")
    for field in sorted(set(parent) | set(candidate)):
        if field.endswith("BySurah"):
            before, after = parent.get(field) or {}, candidate.get(field) or {}
            require(isinstance(before, dict) and isinstance(after, dict), f"حقل {field} ليس قاموساً")
            require({k: v for k, v in before.items() if k not in named}
                    == {k: v for k, v in after.items() if k not in named},
                    f"تغير إعلان {field} خارج السورة المطلوبة")
    if candidate.get("engineVersion") != ENGINE:
        for s in surahs:
            require((candidate.get("engineBySurah") or {}).get(str(s)) == ENGINE,
                    f"محرك السورة {s} غير معلن")
    require(stage_transform.entries_sha(old) != stage_transform.entries_sha(new),
            "المداخل لم تتغير؛ لا إصلاح هنا")


def build(parent_path, parent_sha, aligned_path, surah, out_path, *, parent_key=None):
    require(shared.SHA_RE.fullmatch(str(parent_sha)), "بصمة الأصل يجب أن تكون كاملة")
    surahs = shared.selected_surahs(surah)
    aligned_paths = list(aligned_path) if isinstance(aligned_path, (list, tuple)) else [aligned_path]
    require(len(aligned_paths) == len(surahs), "عدد ملفات المحاذاة لا يطابق عدد السور")
    selection = ",".join(str(s) for s in surahs)
    target = shared.checked_output(out_path)
    parent_blob = Path(parent_path).read_bytes()
    require(sha256(parent_blob) == parent_sha, "بصمة ملف الأصل لا تطابق المطلوبة")
    parent = json.loads(gzip.decompress(parent_blob))
    key = shared.checked_parent_key(parent, parent_sha, parent_key)
    require(parent.get("transform") is None or isinstance(parent["transform"], dict),
            "صيغة أثر التحويل القديمة تحتاج مراجعة")
    sources = {s: parent_source(parent, s) for s in surahs}
    # الأخذ من الأب في الدمج القائم يحتاج مجلداً واحداً؛ لا نوسّع مرجع المصدر ضمنياً.
    folders = {source["url"].rsplit("/", 1)[0] + "/" for source in sources.values()}
    require(len(folders) == 1, "مصادر السور في مجلدات مختلفة؛ هذا المسار يحتاج مجلداً مشتركاً واحداً")
    aligned_blobs = {s: Path(path).read_bytes() for s, path in zip(surahs, aligned_paths)}
    # التحقق المشترك يضيف اسمي المصدر المستعارين فقط؛ لا يغير الحدود أو بصمة القياس.
    adapted = {s: shared.checked_alignment(parent, json.loads(aligned_blobs[s]), s, sources[s])
               for s in surahs}
    require(stage_transform.promote.SPLICE_OPS.get(OP) == ENGINE,
            "محرك التحويل لا يطابق سجل حارس الترقية")
    with tempfile.TemporaryDirectory(prefix="same-source-candidate-") as tmp:
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
                    "--aligned", *saved_aligned, "--url", next(iter(folders)),
                    "--refs-from-parent", "--engine-tag", ENGINE, "--out", str(merged)]
        try:
            splice_surah.main()
        finally:
            sys.argv = previous_args
        require(Path(str(merged) + ".taken").read_text(encoding="utf-8") == selection,
                "الدمج لم يأخذ السور المطلوبة وحدها")
        candidate = json.loads(gzip.decompress(merged.read_bytes()))
    require(sha256(Path(parent_path).read_bytes()) == parent_sha
            and all(Path(path).read_bytes() == aligned_blobs[s] for s, path in zip(surahs, aligned_paths)),
            "تغيرت مدخلات البناء أثناء العمل")
    # الدمج العام يحذف إعلان المصدر عند عدم طلب بديل؛ هنا الصوت ثابت فيبقى إعلانه نفسه.
    if "sourceBySurah" in parent:
        candidate["sourceBySurah"] = copy.deepcopy(parent["sourceBySurah"])
    else:
        candidate.pop("sourceBySurah", None)
    check_preserved(parent, candidate, surahs, sources)
    old_entries, new_entries = parent["entries"], candidate["entries"]
    if "lowCount" in candidate:
        candidate["lowCount"] = sum(e.get("confBand") == "LOW" for e in new_entries)
    moved, added, removed = stage_transform.entry_change_counts(old_entries, new_entries)
    require(added == removed == 0, "تصحيح التوقيت لا يضيف مداخل ولا يسقطها")
    transform = shared.repaired_transform(parent, candidate, surahs, parent_sha, key)
    # سجل تغيير المصدر السابق محفوظ كاملاً داخل النسب التاريخي ولا يصف هذه العملية.
    transform.pop("sourceRepair", None)
    source_repairs = {str(s): {"surah": s, "sourceUrl": sources[s]["url"],
                               "audioSha256": sources[s]["audio_sha256"],
                               "alignedSha256": sha256(aligned_blobs[s])} for s in surahs}
    source_repair = (source_repairs[str(surahs[0])] if len(surahs) == 1
                     else {"surahs": surahs, "bySurah": source_repairs})
    transform.update(op=f"{OP}:{selection}", fromSha256=parent_sha, fromKey=key,
                     entriesSha256=stage_transform.entries_sha(new_entries),
                     parentEntriesSha256=stage_transform.entries_sha(old_entries),
                     movedEntries=moved, addedEntries=added, removedEntries=removed,
                     reason=f"تصحيح توقيت السور {selection} كاملة من أصوات الأصل نفسه المثبتة بالبصمات",
                     by="build_same_source_candidate", at=int(time.time() * 1000),
                     note="مرشح محلي غير منشور؛ يلزمه حكم الجودة والسماع على بصمته.",
                     unpublishedLocalCandidate=True,
                     sameSourceRepair=source_repair)
    candidate["transform"] = transform
    why = stage_transform.promote.index_gate(candidate, parent=parent, parent_sha=parent_sha)
    require(not why, f"حارس بنية الفهرس: {why}")
    payload = gzip.compress(json.dumps(candidate, ensure_ascii=False, allow_nan=False,
                                       separators=(",", ":")).encode("utf-8"), compresslevel=9, mtime=0)
    target.parent.mkdir(parents=True, exist_ok=True)
    shared.checked_output(target)
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
    report = {"path": str(target.relative_to(shared.ROOT)), "sha256": digest,
              "key": f"timings-staging/{parent['riwaya']}/{parent['reciterId']}.{digest[:8]}.jz",
              "parentSha256": parent_sha, "surahs": surahs,
              "alignedSha256BySurah": {str(s): sha256(aligned_blobs[s]) for s in surahs},
              "unpublishedLocalCandidate": True, "sourceChanged": False,
              "qualityChecks": "pending", "heardGate": "pending"}
    if len(surahs) == 1:
        report.update(surah=surahs[0], alignedSha256=sha256(aligned_blobs[surahs[0]]))
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parent", required=True)
    ap.add_argument("--parent-sha", required=True)
    ap.add_argument("--parent-key")
    ap.add_argument("--aligned", required=True, nargs="+", help="ملفات المحاذاة بترتيب السور")
    ap.add_argument("--surah", required=True, help="سورة واحدة أو أكثر بفواصل، مثل 25,41,42,82")
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
