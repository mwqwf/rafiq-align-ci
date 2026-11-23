#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""زرع السور التامّة فقط من فهرس توقيت mp3quran الرسمي فوق الفهرس المنشور.

عندما تحوي خريطة عدّ الرواية (مثل الدوري) خاناتٍ واسعةً فتُسقَط دون تخمين
حدّ وسط (`count_map_wide_ayah`)، يتجاوز الغياب الكلّيّ سقف `stage_source` (2٪).
بدلاً من إرخاء أيّ حارس أو اختراع حدودٍ للخانات الواسعة، تستخرج هذه الأداة
السورَ التامّةَ عدّاً وحدها من مخرَج `ingest_mp3quran_timing.py` وتزرعها في
الأصل المنشور عبر `splice_surah.py` بمحرّك `mp3quran-timing-v1` (ما يفرض
إحصاءً صوتيّاً شاملاً واختبارَ السماع والمطالع والملوح لكلّ سورةٍ مزروعة).
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import drop_surah  # noqa: E402

ENGINE_TAG = "mp3quran-timing-v1"


def load_jz(path: Path) -> dict:
    return json.loads(gzip.decompress(Path(path).read_bytes()).decode("utf-8"))


def dump_jz(obj: dict, path: Path) -> str:
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with open(path, "wb") as fh:
        with gzip.GzipFile(fileobj=fh, mode="wb", compresslevel=9, mtime=0) as gz:
            gz.write(raw)
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def complete_official_surahs(parent: dict, official: dict) -> dict[int, list[dict]]:
    """يُرجع {سورة: مداخل مرتّبة} للسور المكتملة العدّ والصاعدة حدودها فقط."""
    counts = drop_surah.SURAH_AYAHS_OF(parent)
    by_surah: dict[int, dict[int, dict]] = {}
    for e in official.get("entries") or []:
        s_str, a_str = e["ayahId"].split(":", 1)
        s, a = int(s_str), int(a_str)
        by_surah.setdefault(s, {})[a] = e

    complete: dict[int, list[dict]] = {}
    for s in range(1, 115):
        want = counts[s - 1]
        got = by_surah.get(s) or {}
        if len(got) != want or set(got) != set(range(1, want + 1)):
            continue
        rows = [got[a] for a in range(1, want + 1)]
        prev = -1
        ok = True
        for r in rows:
            st, en = r.get("startMs"), r.get("endMs")
            if st is None or en is None or not (0 <= int(st) < int(en)) or int(st) < prev:
                ok = False
                break
            prev = int(en)
        if ok:
            complete[s] = rows
    return complete


def splice_complete(
    parent_path: Path,
    official_path: Path,
    url_template: str,
    read_id: int,
    out_path: Path,
    only_surahs: list[int] | None = None,
) -> list[int]:
    parent = load_jz(parent_path)
    official = load_jz(official_path)
    complete = complete_official_surahs(parent, official)
    if only_surahs:
        want = set(only_surahs)
        complete = {s: rows for s, rows in complete.items() if s in want}
    if not complete:
        raise SystemExit("⛔ لا سورة تامّة العدّ في مخرَج التوقيت الرسمي للزرع")

    surahs = sorted(complete)
    with tempfile.TemporaryDirectory(prefix="official_splice_") as td:
        tdir = Path(td)
        aligned_files: list[str] = []
        for s in surahs:
            af = tdir / f"s{s:03d}.json"
            payload = {
                "entries": [
                    {
                        "ayahId": r["ayahId"],
                        "startMs": int(r["startMs"]),
                        "endMs": int(r["endMs"]),
                        "conf": float(r.get("conf") or 0.7),
                    }
                    for r in complete[s]
                ]
            }
            af.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            aligned_files.append(str(af))

        cmd = [
            sys.executable,
            str(HERE / "splice_surah.py"),
            "--index", str(parent_path),
            "--surah", ",".join(str(s) for s in surahs),
            "--aligned", *aligned_files,
            "--url", url_template,
            "--engine-tag", ENGINE_TAG,
            "--out", str(out_path),
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit((r.stdout or "") + (r.stderr or "") or f"⛔ splice_surah خرج {r.returncode}")

    patched = load_jz(out_path)
    stbs = dict(patched.get("sourceTimingBySurah") or {})
    src_meta = {
        "api": "mp3quran.net/api/v3/ayat_timing",
        "readId": int(read_id),
    }
    for s in surahs:
        stbs[str(s)] = src_meta
    patched["sourceTimingBySurah"] = dict(sorted(stbs.items(), key=lambda kv: int(kv[0])))
    sha = dump_jz(patched, out_path)
    Path(str(out_path) + ".taken").write_text(",".join(str(s) for s in surahs), encoding="utf-8")
    print(f"سورٌ تامّةٌ مزروعة ({len(surahs)}): {','.join(str(s) for s in surahs)}")
    print(f"✅ {out_path} · sha256 {sha[:16]}…")
    return surahs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--parent", required=True)
    ap.add_argument("--official", required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--read", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--surahs", default="", help="حصر الزرع بسور محدّدة (اختياري)")
    a = ap.parse_args(argv)
    only = [int(x) for x in a.surahs.replace(",", " ").split() if x] if a.surahs.strip() else None
    splice_complete(Path(a.parent), Path(a.official), a.url, a.read, Path(a.out), only_surahs=only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
