#!/usr/bin/env python3
"""يبني مرشّحاً محلياً من مصادر صريحة مثبتة؛ الرفع والترقية بأدواتهما القائمة."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "alignment"))
sys.path.insert(0, str(ROOT / "tools" / "alignment_v3"))
from source_registry import registered_source
from common import fetch_retry


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parent-file", required=True)
    ap.add_argument("--catalog-file", required=True)
    ap.add_argument("--riwaya", required=True)
    ap.add_argument("--reciter", required=True)
    ap.add_argument("--surahs", required=True)
    ap.add_argument("--work-dir", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    idx = json.loads(gzip.decompress(Path(a.parent_file).read_bytes()))
    if idx.get("riwaya") != a.riwaya or idx.get("reciterId") != a.reciter:
        raise SystemExit("⛔ هوية الأصل لا تطابق المطلوب")
    cat = json.loads(Path(a.catalog_file).read_text(encoding="utf-8"))
    readers = [c for r in cat.get("riwayat", []) if r.get("id") == a.riwaya
               for c in r.get("reciters", []) if c.get("id") == a.reciter]
    if len(readers) != 1 or readers[0].get("mode") != "surah":
        raise SystemExit("⛔ القارئ ليس مصدر سور وحيداً في الكتالوج")
    surahs = [int(s) for s in a.surahs.split(",")]
    if not surahs or len(set(surahs)) != len(surahs) or any(not 1 <= s <= 114 for s in surahs):
        raise SystemExit("⛔ قائمة السور غير صالحة")
    # تثبت جميع المصادر قبل تحميل النموذج أو تنزيل أي صوت.
    rows = {s: registered_source(a.riwaya, a.reciter, s) for s in surahs}
    if any(not row.get("audio_sha256") for row in rows.values()):
        raise SystemExit("⛔ الإصلاح الصريح يحتاج بصمة صوت مقيسة لكل سورة")
    work = Path(a.work_dir).resolve()
    work.mkdir(parents=True, exist_ok=True)
    aligned = []
    from ctc_seg import run_surah, ENGINE
    for s, row in rows.items():
        audio = work / (row["audio_sha256"] + ".mp3")
        if not audio.exists():
            fetch_retry(row["url"], str(audio))
        sha = hashlib.sha256(audio.read_bytes()).hexdigest()
        if sha != row["audio_sha256"]:
            raise SystemExit(f"⛔ س{s}: تغيرت بصمة المصدر؛ لا محاذاة على ملف مختلف")
        print(f"س{s}: رابط مسجّل وبصمة كاملة مطابقة", flush=True)
        result = run_surah(str(audio), s, a.riwaya)
        result.update(sourceUrl=row["url"], audioSha256=sha)
        path = work / f"s{s}.json"
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        aligned.append(str(path))
    subprocess.run([sys.executable, str(ROOT / "tools/index_qa/splice_surah.py"),
                    "--index", a.parent_file, "--surah", a.surahs,
                    "--aligned", *aligned,
                    "--url", readers[0]["base"].rstrip("/") + "/{s:03d}.mp3",
                    "--registered-sources", "--alt-source", "--engine-tag", ENGINE,
                    "--out", a.out], check=True)
    print("مرشّح محلي فقط؛ لم يُرفع أو يُرقّ", flush=True)


if __name__ == "__main__":
    main()
