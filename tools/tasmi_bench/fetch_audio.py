# -*- coding: utf-8 -*-
"""تجهيز صوت العيّنة: كل بند → `work/wav/{id}.wav` بـ16ك.هز أحادي (مدخل whisper).

ملفات السور القالونية تُنزَّل مؤقتاً وتُقصّ ثم **تُحذف** (لا نملك الصوت ولا
نعيد نشره — D-024)، والنواتج wav خارج git.

    python tools/tasmi_bench/fetch_audio.py [--only qalun]
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))
from common import FFMPEG, fetch_retry, ffprobe_duration_ms  # noqa: E402

WORK = os.path.join(HERE, "work")
WAV = os.path.join(WORK, "wav")
TMP = os.path.join(WORK, "tmp")


def r2_client():
    import boto3
    c = json.load(open(os.path.join(ROOT, "secure", "r2_credentials.json")))
    return boto3.client("s3", endpoint_url=c["endpoint"], aws_access_key_id=c["accessKeyId"],
                        aws_secret_access_key=c["secretAccessKey"], region_name="auto"), c["bucket"]


def to_wav(src, dst, start_ms=None, end_ms=None):
    cmd = [FFMPEG, "-y", "-v", "error"]
    if start_ms is not None:
        cmd += ["-ss", f"{start_ms/1000:.3f}"]
    cmd += ["-i", src]
    if end_ms is not None:
        cmd += ["-t", f"{(end_ms-start_ms)/1000:.3f}"]
    cmd += ["-ar", "16000", "-ac", "1", dst]
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["hafs", "warsh", "qalun"])
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    for d in (WAV, TMP):
        os.makedirs(d, exist_ok=True)
    data = json.load(open(os.path.join(HERE, "sample.json"), encoding="utf-8"))
    items = [i for i in data["items"] if not args.only or i["riwaya"] == args.only]

    # 1) الآيات المفردة
    singles = [i for i in items if i["source"]["kind"] == "ayah_file"]
    for n, it in enumerate(singles, 1):
        dst = os.path.join(WAV, it["id"] + ".wav")
        if os.path.exists(dst) and not args.force:
            continue
        mp3 = os.path.join(TMP, it["id"] + ".mp3")
        fetch_retry(it["source"]["url"], mp3)
        to_wav(mp3, dst)
        os.remove(mp3)
        if n % 20 == 0:
            print(f"  آيات مفردة {n}/{len(singles)}", flush=True)

    # 2) القصّ من ملفات السور (تُنزَّل مرة لكل سورة ثم تُحذف)
    cuts = [i for i in items if i["source"]["kind"] == "cut_from_surah"]
    if cuts:
        s3, bucket = r2_client()
        by_surah = {}
        for it in cuts:
            by_surah.setdefault(it["surah"], []).append(it)
        for k, (surah, group) in enumerate(sorted(by_surah.items()), 1):
            todo = [i for i in group if args.force or not os.path.exists(os.path.join(WAV, i["id"] + ".wav"))]
            if not todo:
                continue
            src = os.path.join(TMP, f"qalun_{surah:03d}.mp3")
            s3.download_file(bucket, group[0]["source"]["r2Key"], src)
            dur = ffprobe_duration_ms(src)
            for it in todo:
                s0, s1 = it["source"]["startMs"], min(it["source"]["endMs"], dur)
                to_wav(src, os.path.join(WAV, it["id"] + ".wav"), s0, s1)
            os.remove(src)
            print(f"  سورة {surah}: {len(todo)} قصاصة ({k}/{len(by_surah)})", flush=True)

    n = len([f for f in os.listdir(WAV) if f.endswith(".wav")])
    print(f"✅ {n} ملف wav في {WAV}")


if __name__ == "__main__":
    main()
