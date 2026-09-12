# -*- coding: utf-8 -*-
"""🔪 **بناءُ G3 محلياً — تلاواتٌ مُخطئةٌ بحقيقةٍ أرضية معلومة بالبناء**.

`remote_inject.py` يحتاج `whisper-cli` على خادمٍ لم يعد قائماً؛ وهذا يبني الملفات **صوتاً**
فقط (بلا تفريغ)، فتُفرَّغ بعدُ بأيِّ مسار: المحاكي (`emu_sweep.py`) أو المرآة (`local_whisper.py`).

**ولماذا الآن:** بوّابةُ الضجيج (‏D-257) رفعت **التتبّع** رفعاً كبيراً — والقاعدةُ في خارطة الطريق
أن **لا يُعتمد شيءٌ يرفع التتبّع ويخفض الكشف**. فلا بدّ من عيّنة أخطاءٍ **مضجَّجةٍ ومنقّاة** ليُقاس
أثرُ البوّابة على الكشف لا على الإنذار الكاذب وحده.

المجموعاتُ الثلاث (البنودُ نفسُها في الثلاث — المقارنةُ عادلةٌ بالبناء):
| المجلد | ما فيه |
|---|---|
| `work/g3/clean` | الآيةُ بعد الجراحة (حذفٌ · إبدال · تبديل · إقحام) بصوتٍ نظيف |
| `work/g3/noisy` | نفسُها + مروحةٌ عند SNR 10 |
| `work/g3/dn-noisy` | نفسُها مضجَّجةً ثم منقّاةً بالبوّابة |

    python tools/tasmi_bench/inject_local.py --limit 60
"""
import argparse
import json
import os
import subprocess
import sys

import numpy as np
import soundfile as sf
from decode import run_decode

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))

WORK = os.path.join(HERE, "work")
G3 = os.path.join(WORK, "g3")
CACHE = os.path.join(WORK, "g3_src")
SR = 16_000


def to_wav(src, dst, ffmpeg):
    run_decode([ffmpeg, "-y", "-v", "error", "-i", src, "-vn", "-ar", str(SR), "-ac", "1", dst],
               src, dst)


def fetch(url, dst, ffmpeg):
    """ينزّل mp3 ويحوّله wav 16ك.هز (مرةً واحدة — الكاشُ خارج git)."""
    if os.path.exists(dst):
        return True
    from common import fetch_retry
    mp3 = dst + ".mp3"
    try:
        fetch_retry(url, mp3)
        to_wav(mp3, dst, ffmpeg)
        return True
    except Exception as e:
        print(f"  ⚠️ تعذّر {os.path.basename(dst)}: {str(e)[:70]}", flush=True)
        return False
    finally:
        if os.path.exists(mp3):
            os.remove(mp3)


def surgery(x, item, donors):
    """يطبّق العمليةَ الموصوفة في البند. [donors]: مقاطعُ كلماتٍ من بنودٍ أخرى للإبدال/الإقحام."""
    a, b = item["cutMs"]
    ia, ib = int(a * SR / 1000), int(b * SR / 1000)
    ia = max(0, min(ia, len(x)))
    ib = max(ia, min(ib, len(x)))
    op = item["op"]
    if op == "OMIT":
        return np.concatenate([x[:ia], x[ib:]]).astype(np.float32)
    if op in ("SUBSTITUTE", "INSERT"):
        if not donors:
            return None
        d = donors[hash(item["id"]) % len(donors)]
        lvl = max(np.abs(x).max(), 1e-6) / max(np.abs(d).max(), 1e-6)
        d = (d * lvl).astype(np.float32)
        if op == "SUBSTITUTE":
            return np.concatenate([x[:ia], d, x[ib:]]).astype(np.float32)
        return np.concatenate([x[:ia], d, x[ia:]]).astype(np.float32)
    if op == "SWAP":
        c, dms = item.get("cut2Ms", (None, None))
        if c is None:
            return None
        ic, idd = int(c * SR / 1000), int(dms * SR / 1000)
        if not (ib <= ic <= idd <= len(x)):
            return None
        return np.concatenate([x[:ia], x[ic:idd], x[ib:ic], x[ia:ib], x[idd:]]).astype(np.float32)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", default=os.path.join(HERE, "inject_plan.json"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--snr", type=float, default=10.0)
    args = ap.parse_args()

    from common import FFMPEG
    import augment as ag
    import denoise as dn

    plan = json.load(open(args.plan, encoding="utf-8"))
    items = plan["items"]
    if args.limit:
        # توزيعٌ متوازنٌ على أنواع الخطأ لا أولَ ما جاء
        by_op = {}
        for it in items:
            by_op.setdefault(it["op"], []).append(it)
        per = max(1, args.limit // max(1, len(by_op)))
        items = [it for v in by_op.values() for it in v[:per]]

    for d in (CACHE, os.path.join(G3, "clean"), os.path.join(G3, "noisy"), os.path.join(G3, "dn-noisy")):
        os.makedirs(d, exist_ok=True)

    # مانحو الكلمات للإبدال/الإقحام: مقاطعُ مقصوصةٌ من بنودٍ أخرى
    donors = []
    ok = fail = 0
    print(f"▶ {len(items)} بنداً", flush=True)
    for n, it in enumerate(items, 1):
        src = os.path.join(CACHE, f"{it['surah']:03d}{it['ayah']:03d}.wav")
        if not fetch(it["url"], src, FFMPEG):
            fail += 1
            continue
        x, sr = sf.read(src, dtype="float32")
        if sr != SR or len(x) == 0:
            fail += 1
            continue
        a, b = it["cutMs"]
        ia, ib = int(a * SR / 1000), int(b * SR / 1000)
        if 0 <= ia < ib <= len(x) and len(donors) < 12:
            donors.append(x[ia:ib].copy())
        y = surgery(x, it, donors)
        if y is None or len(y) < SR // 2:
            fail += 1
            continue
        rng = np.random.default_rng(abs(hash(it["id"])) % (2**32))
        noisy = ag.mix_at_snr(y, ag.pink_noise(len(y), rng), args.snr)
        sf.write(os.path.join(G3, "clean", it["id"] + ".wav"), y, SR, subtype="PCM_16")
        sf.write(os.path.join(G3, "noisy", it["id"] + ".wav"), noisy, SR, subtype="PCM_16")
        sf.write(os.path.join(G3, "dn-noisy", it["id"] + ".wav"), dn.denoise(noisy), SR, subtype="PCM_16")
        ok += 1
        if n % 20 == 0:
            print(f"  {n}/{len(items)} (نجح {ok})", flush=True)

    meta = {"snrDb": args.snr, "built": ok, "failed": fail,
            "ops": sorted({i["op"] for i in items}),
            "note": "الحقيقةُ الأرضية: op وwordIndex في inject_plan.json"}
    json.dump(meta, open(os.path.join(G3, "meta.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"✅ بُني {ok} · تعذّر {fail} ⇒ {G3}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
