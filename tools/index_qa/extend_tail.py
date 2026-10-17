#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مدُّ نهاية آخر آيةٍ إلى المدّة الحقيقية حين قصّتها المحاذاةُ عند مدّة الترويسة (e5 · 2026-10-17).

    python tools/index_qa/extend_tail.py --key timings/hafs/lahoni.jz --sha ffde642a --surahs 3,4,5 [--yes]

⭐ **العلّة:** مدّةُ ترويسة mp3 تقصر عن الصوت الحقيقيّ بنحو 0.5% في ملفّات mp3quran الطويلة (‏لحوني س3:
4253.8 مقابل 4273.7ث)، فكانت المحاذاةُ تقصّ الصوتَ عندها وتنتهي آخرُ آيةٍ عند الترويسة والكلامُ يتّصل بعدها.
أُصلح القياسُ في `common.ffprobe_duration_ms` (‏مجموع مدد الحزم)، وهذه الأداة تصلح **المنشورَ القديم** بأضيق تغيير:

لكلّ سورةٍ مسمّاة تمدّ `endMs` لآخر مدخلٍ فيها إلى المدّة الحقيقية **بشرطين معاً**:
  ١) endMs = مدّة الترويسة (‏±50م.ث)، و٢) في الذيل بعده كلامٌ (‏متوسّط الطاقة > −30dB).
وما لم يجتزهما يُترك ويُطبع السبب. لا يمسّ بدءَ أيّ آية ولا مدخلاً غير الأخير، ولا يُنقص عدداً.
الناتجُ يُرفع بـ`stage_transform` (‏op = file_end_extend) بحُرّاسه كلّها إلى `timings-staging/` ولا يُرقّى.
`--yes` يرفع؛ بدونه عرضٌ فقط.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "alignment"))

UA = {"User-Agent": "Mozilla/5.0 (QuranRafiq tools)"}
HDR_TOL_MS = 50
MIN_GAIN_MS = 3000
MIN_DB = -30.0


def last_entries(entries, surahs):
    last = {}
    for e in entries:
        s = int(e["ayahId"].split(":")[0])
        if s in surahs and e.get("endMs") is not None:
            if s not in last or int(e["ayahId"].split(":")[1]) > int(last[s]["ayahId"].split(":")[1]):
                last[s] = e
    return last


def decide(end_ms, hdr_ms, true_ms, tail_db):
    """(يمدّ؟، السبب) — دالّةٌ صِرفةٌ مختبَرة."""
    if abs(end_ms - hdr_ms) > HDR_TOL_MS:
        return False, f"endMs {end_ms} ليس عند الترويسة {hdr_ms}"
    if true_ms - end_ms <= MIN_GAIN_MS:
        return False, f"الفرق {true_ms - end_ms}م.ث ≤ {MIN_GAIN_MS}"
    if tail_db is None or tail_db <= MIN_DB:
        return False, f"طاقة الذيل {tail_db} ≤ {MIN_DB}dB — لا كلام بعده"
    return True, "ok"


def header_ms(path):
    import common
    out = subprocess.run([common.FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of",
                          "default=nw=1:nk=1", path], capture_output=True, text=True, errors="replace").stdout.strip()
    return int(float(out) * 1000)


def tail_db(path, from_s):
    out = subprocess.run(["ffmpeg", "-nostats", "-ss", f"{from_s:.3f}", "-i", path, "-vn", "-af", "volumedetect",
                          "-f", "null", "-"], capture_output=True, text=True, errors="replace").stderr
    for line in out.splitlines():
        if "mean_volume" in line:
            return float(line.split("mean_volume:")[1].split("dB")[0])
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--key", required=True)
    ap.add_argument("--sha", required=True)
    ap.add_argument("--surahs", required=True)
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    import common
    from run import s3
    # عدّاءُ الأوامر خفيفٌ: يُنصَّب ffmpeg عند الحاجة (كما في clamp_file_end)
    if subprocess.run(["which", "ffprobe"], capture_output=True).returncode:
        subprocess.run("sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg", shell=True, check=True)
    cl, b = s3()
    body = cl.get_object(Bucket=b, Key=a.key)["Body"].read()
    live = hashlib.sha256(body).hexdigest()
    if not live.startswith(a.sha):
        sys.exit(f"⛔ البصمة لا تطابق: {live[:16]} لا {a.sha}")
    idx = json.loads(gzip.decompress(body).decode("utf-8"))
    surahs = {int(s) for s in a.surahs.split(",")}
    last = last_entries(idx["entries"], surahs)
    changes = []
    for s in sorted(last):
        e = last[s]
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f, \
                urllib.request.urlopen(urllib.request.Request(e["fileRef"], headers=UA), timeout=300) as r:
            f.write(r.read())
        end = int(e["endMs"])
        hdr = header_ms(f.name)
        true = common.ffprobe_duration_ms(f.name)
        db = tail_db(f.name, end / 1000) if true > end else None
        ok, why = decide(end, hdr, true, db)
        print(f"{'✅' if ok else '·'} {e['ayahId']}: end={end} ترويسة={hdr} حقيقي={true} ذيل={db}dB — {why}")
        Path(f.name).unlink(missing_ok=True)
        if ok:
            changes.append((e["ayahId"], end, true))
    if not changes:
        print("لا شيء يُمدّ")
        return 0
    by = {aid: new for aid, _o, new in changes}
    for e in idx["entries"]:
        if e["ayahId"] in by:
            e["endMs"] = int(by[e["ayahId"]])
    out = Path(tempfile.mkdtemp()) / "extended.jz"
    out.write_bytes(gzip.compress(json.dumps(idx, ensure_ascii=False).encode("utf-8")))
    cmd = [sys.executable, str(HERE / "stage_transform.py"), "--file", str(out), "--parent", a.key,
           "--parent-sha", live[:16], "--op", "file_end_extend",
           "--reason", "مدُّ نهاية آخر مدخلٍ إلى المدّة الحقيقية (الترويسة تقصر عن الصوت): "
           + " · ".join(f"{aid} +{new - old}م.ث" for aid, old, new in changes),
           "--by", "github-extend"] + (["--yes"] if a.yes else [])
    return subprocess.run(cmd, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
