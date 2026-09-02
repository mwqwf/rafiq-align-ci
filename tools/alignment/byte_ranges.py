# -*- coding: utf-8 -*-
"""ممر لاحق: إضافة byteStart/byteEnd لعناصر TimingIndex لملفات CBR (للتنزيل الجزئي بـRange).

python byte_ranges.py --index work/timings_qalun_husary_qalun.jz
يعيد تنزيل كل ملف سورة (مؤقتاً)، يتحقق من ثبات معدل البت، ويكتب الفهرس محدثاً.
VBR ⇒ يُترك العنصر بلا مدى بايتي (cbr=false) — جدول الإطارات مؤجل (RESEARCH_BACKLOG).
"""
import argparse
import json
import os
import subprocess
import urllib.request

from common import FFPROBE, WORK, read_jz, write_jz


def probe(path):
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "a:0",
         "-show_entries", "format=duration,bit_rate,size",
         "-of", "json", path],
        capture_output=True, text=True, check=True).stdout
    f = json.loads(out)["format"]
    return float(f["duration"]) * 1000, int(f["bit_rate"]), int(f["size"])


def is_cbr(path, dur_ms, bit_rate, size):
    """CBR إذا كان الحجم ≈ المدة×معدل البت (±2% — يسمح بترويسة ID3 صغيرة)."""
    expected = dur_ms / 1000 * bit_rate / 8
    return abs(size - expected) / expected < 0.02


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    args = ap.parse_args()
    ti = read_jz(args.index)
    by_file = {}
    for e in ti["entries"]:
        by_file.setdefault(e["fileRef"], []).append(e)
    tmp = os.path.join(WORK, "byterange_tmp.mp3")
    cbr_files = vbr_files = 0
    for url, entries in by_file.items():
        urllib.request.urlretrieve(url, tmp)
        dur_ms, bit_rate, size = probe(tmp)
        header = size - int(dur_ms / 1000 * bit_rate / 8)  # حجم الترويسة التقريبي
        if is_cbr(tmp, dur_ms, bit_rate, size):
            bytes_per_ms = bit_rate / 8 / 1000
            for e in entries:
                e["byteStart"] = max(0, int(header + e["startMs"] * bytes_per_ms) - 1024)
                e["byteEnd"] = min(size, int(header + e["endMs"] * bytes_per_ms) + 1024)
                e["cbr"] = True
            cbr_files += 1
        else:
            for e in entries:
                e["cbr"] = False
            vbr_files += 1
        os.remove(tmp)
        print(f"{'CBR' if entries[0].get('cbr') else 'VBR'} {url.rsplit('/',1)[-1]}", flush=True)
    write_jz(args.index, ti)
    print(f"تم: {cbr_files} ملف CBR بمدى بايتي، {vbr_files} ملف VBR بدونه ← {args.index}")


if __name__ == "__main__":
    main()
