#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""قصُّ نهايةِ آخر مدخلٍ في ملفّه إلى نهاية الملفّ **المقيسة بطول الفكّ** (2026-09-30).

    python tools/index_qa/clamp_file_end.py --key timings/hafs/a_alhazmi.jz --sha 5cc926a1 --surahs 93 [--yes]

⭐ **سببُه:** حارسُ نهاية الملفّ في الإحصاء (‏`run._eof_pad_ok`) صارمٌ: نهايةُ الآية ≤ نهايةُ الملفّ حرفاً.
   ونهايةُ a_alhazmi 93:11 = 53916 والملفُّ 53869 (‏+47م.ث — بقيّةُ تقديرٍ في المحاذاة). والعلاجُ **في البيانات
   لا في الحارس** (‏رُدّ سماحُ الحارس لأنّه أرخى شرطاً قديماً).
⛔ **حُرّاس:** يُقصّ **آخرُ مدخلٍ في ملفّه وحده**، و**التجاوزُ ≤ MAX_OVER_MS** — فما زاد تجاوزُه فعلامةُ بترٍ
   (‏الفهرسُ يدّعي صوتاً ليس في الملفّ) **يُردّ ولا يُقصّ**؛ والقصُّ لا يجعل النهايةَ قبل البداية. والمدّةُ تُقاس
   بتنزيل الملفّ وفكّه كاملاً (‏`run._full_decode_pcm` — مقياسُ الحارس نفسُه) لا من ترويسة. ثمّ يُرفع عبر `stage_transform` بحُرّاسه كلّها (‏op: file_end_clamp).
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

MAX_OVER_MS = 500
UA = {"User-Agent": "Mozilla/5.0 (QuranRafiq tools)"}


def plan(entries, surahs, dur_of):
    """(قائمةُ القصّ، الردود) — دالّةٌ صِرفةٌ مختبَرة. ‏dur_of(url) ⇒ م.ث."""
    last = {}
    for e in entries:
        if int(e["ayahId"].split(":")[0]) in surahs and e.get("endMs") is not None:
            u = e["fileRef"]
            if u not in last or e["startMs"] > last[u]["startMs"]:
                last[u] = e
    cuts, refused = [], []
    for u, e in sorted(last.items(), key=lambda kv: kv[1]["ayahId"]):
        fd = int(dur_of(u))
        over = int(e["endMs"]) - fd
        if over <= 0:
            continue
        if over > MAX_OVER_MS:
            refused.append(f"{e['ayahId']}: تتجاوز نهايةَ الملفّ بـ{over}م.ث (> {MAX_OVER_MS}) — علامةُ بترٍ لا تُقصّ")
        elif fd <= int(e["startMs"]):
            refused.append(f"{e['ayahId']}: نهايةُ الملفّ {fd} قبل بدء الآية {e['startMs']}")
        else:
            cuts.append((e["ayahId"], int(e["endMs"]), fd))
    return cuts, refused


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True)
    ap.add_argument("--sha", required=True)
    ap.add_argument("--surahs", required=True)
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    from run import s3
    cl, b = s3()
    body = cl.get_object(Bucket=b, Key=a.key)["Body"].read()
    live = hashlib.sha256(body).hexdigest()
    if not live.startswith(a.sha):
        sys.exit(f"⛔ البصمة لا تطابق: {live[:16]} لا {a.sha}")
    idx = json.loads(gzip.decompress(body).decode("utf-8"))
    surahs = {int(s) for s in a.surahs.split(",")}
    cache = {}
    # عدّاءُ الأوامر خفيفٌ (‏boto3 وحده) — فيُنصَّب ما يلزم الفكَّ هنا عند الحاجة لا في كلّ أمر.
    try:
        import numpy  # noqa: F401
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "numpy<2", "soundfile"], check=True)
    if subprocess.run(["which", "ffmpeg"], capture_output=True).returncode:
        subprocess.run("sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg", shell=True, check=True)

    def dur_of(u):
        if u not in cache:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f, \
                    urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=180) as r:
                f.write(r.read())
            # ⛔ **بمقياس الحارس نفسِه** (‏`run._full_decode_pcm`: طولُ الصوت بعد الفكّ) لا بعدّ الإطارات:
            #    الإطاراتُ تحمل حشوَ المُرمِّز فتطول (‏a_alhazmi/093: الإطارات ≥53916 والفكُّ 53869)،
            #    والحارسُ يحكم بالفكّ — فمقياسان مختلفان يجعلان القصَّ «لا شيء» والحارسَ «يردّ».
            import run
            cache[u] = len(run._full_decode_pcm(f.name)) * 1000.0 / 16000
        return cache[u]

    cuts, refused = plan(idx["entries"], surahs, dur_of)
    for r in refused:
        print("⛔", r)
    if refused:
        sys.exit(1)
    if not cuts:
        print("لا نهايةَ تتجاوز ملفّها — لا شيء يُقصّ")
        return 0
    by = {aid: fd for aid, _old, fd in cuts}
    for e in idx["entries"]:
        if e["ayahId"] in by:
            e["endMs"] = int(by[e["ayahId"]])
    for aid, old, fd in cuts:
        print(f"✂ {aid}: {old} ⇒ {int(fd)} (‏−{old - int(fd)}م.ث)")
    out = Path(tempfile.mkdtemp()) / "clamped.jz"
    out.write_bytes(gzip.compress(json.dumps(idx, ensure_ascii=False).encode("utf-8")))
    cmd = [sys.executable, str(HERE / "stage_transform.py"), "--file", str(out), "--parent", a.key,
           "--parent-sha", live[:16], "--op", "file_end_clamp",
           "--reason", "قصُّ نهاية آخر مدخلٍ إلى نهاية ملفّه المقيسة بطول الفكّ: "
           + " · ".join(f"{aid} −{old - int(fd)}م.ث" for aid, old, fd in cuts),
           "--by", "github-clamp"] + (["--yes"] if a.yes else [])
    return subprocess.run(cmd, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
