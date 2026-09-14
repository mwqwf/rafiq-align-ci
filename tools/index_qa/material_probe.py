#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مسبارُ المادّة — يقيس **مادّةَ المصدر** لقارئٍ منشورٍ أو راسبٍ بلا دلوٍ ولا سرّ.

⛔ **لماذا لم يصلح `reciter_probe.yml` لهذا؟** (‏مقيسٌ 2026-09-14، الشوط 34899892428):
   ذاك مسبارُ **المرشَّحين الجدد** وقائمتُه `new_reciters.tsv` ⇒ فردّ حرفاً:
   `⛔ معرّفاتٌ ليست في القائمة: ['bilal', 'f_khamery', 'hafz']` — وهؤلاء قرّاءُ
   `reciters_ci*.tsv`. **فالعطبُ في اختيار الأداة لا في المادّة.**

⛔ **ولا يحكم هذا المسبارُ شيئاً** — يطبع أرقاماً خاماً (معدّلَ البتّ وتردّدَ العيّنة
   والقنواتِ وطولَ الملفّ) ليُقارَن الراسبُ بناجحٍ ضابط. والحكمُ لمن يقرأ.

⭐ **ولا يُنزّل الملفَّ كاملاً**: `HEAD` للحجم ثمّ `Range` لأوّل 64 ك.ب فقط —
   فالمقارنةُ لا تحتاج أكثر، وشبكةُ العدّاء ليست مجّانيّةَ الوقت.
"""
import argparse, glob, os, re, struct, sys, urllib.request

BITRATES_V1L3 = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0]
BITRATES_V2L3 = [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0]
RATES = {0: (44100, 22050, 11025), 1: (48000, 24000, 12000), 2: (32000, 16000, 8000)}
MODES = ("stereo", "joint", "dual", "mono")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def templates():
    """يُجمع من كلّ `reciters_ci*.tsv` — والأحدثُ يغلب لأنّ الترتيبَ أبجديّ."""
    out = {}
    for p in sorted(glob.glob(os.path.join(ROOT, "ci_fleet", "reciters_ci*.tsv"))):
        for line in open(p, encoding="utf-8"):
            if line.startswith("#") or not line.strip():
                continue
            c = line.rstrip("\n").split("\t")
            if len(c) >= 3:
                out[c[0]] = (c[1], c[2])
    return out


def get(url, rng=None, method="GET"):
    r = urllib.request.Request(url, method=method)
    if rng:
        r.add_header("Range", f"bytes=0-{rng - 1}")
    with urllib.request.urlopen(r, timeout=60) as f:
        return f.headers, (b"" if method == "HEAD" else f.read())


def frame(buf):
    """أوّلُ ترويسةِ إطارٍ صالحة — ويُتخطّى ID3 لأنّه يسبقها غالباً."""
    i = 0
    if buf[:3] == b"ID3" and len(buf) > 10:
        sz = struct.unpack(">I", bytes([0]) + bytes(b & 0x7F for b in buf[6:10])[1:])[0]
        sz = sum(b & 0x7F for b in buf[6:10][::-1] and []) or (
            (buf[6] & 0x7F) << 21 | (buf[7] & 0x7F) << 14 | (buf[8] & 0x7F) << 7 | (buf[9] & 0x7F))
        i = 10 + sz
    while i + 4 <= len(buf):
        if buf[i] == 0xFF and (buf[i + 1] & 0xE0) == 0xE0:
            h = buf[i:i + 4]
            ver, layer = (h[1] >> 3) & 3, (h[1] >> 1) & 3
            bi, ri, mode = (h[2] >> 4) & 15, (h[2] >> 2) & 3, (h[3] >> 6) & 3
            if ver != 1 and layer == 1 and bi not in (0, 15) and ri != 3:
                br = (BITRATES_V1L3 if ver == 3 else BITRATES_V2L3)[bi]
                sr = RATES[ri][0 if ver == 3 else (1 if ver == 2 else 2)]
                return br, sr, MODES[mode]
        i += 1
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", help="معرّفات مفصولة بفاصلة")
    ap.add_argument("--surahs", default="1,18,36,114")
    a = ap.parse_args()
    tpl = templates()
    bad = [k for k in a.ids.split(",") if k.strip() and k.strip() not in tpl]
    if bad:
        sys.exit(f"⛔ لا قالبَ لهم في reciters_ci*.tsv: {bad}")
    for rid in [k.strip() for k in a.ids.split(",") if k.strip()]:
        riwaya, t = tpl[rid]
        print(f"\n▶ {rid} ({riwaya}) — {t}")
        for s in (int(x) for x in a.surahs.split(",")):
            url = t.replace("{surah:03d}", f"{s:03d}").replace("{s:03d}", f"{s:03d}")
            try:
                hh, _ = get(url, method="HEAD")
                n = int(hh.get("Content-Length") or 0)
                _, buf = get(url, rng=65536)
                f = frame(buf)
            except Exception as e:                       # noqa: BLE001
                print(f"  {s:03d}  ⛔ {type(e).__name__}: {e}")
                continue
            if not f:
                print(f"  {s:03d}  {n:>10,} ب  ⛔ لا ترويسةَ إطارٍ في أوّل 64ك.ب")
                continue
            br, sr, mode = f
            secs = (n * 8 / (br * 1000)) if br else 0
            print(f"  {s:03d}  {n:>10,} ب · {br:>3} ك.ب/ث · {sr} هرتز · {mode}"
                  f" · ≈{int(secs) // 60}:{int(secs) % 60:02d}")


if __name__ == "__main__":
    main()
