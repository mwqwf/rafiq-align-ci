#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""سبرٌ قارئٌ محضٌ لعطب إطارات ملفّ صوت: فجواتُه وعناقيدُه وما يُسقطه كلُّ عنقود.

    python tools/index_qa/resync_probe.py <رابط أو مسار> [--window 2:218]

⚖️ لا يكتب بايتاً في الدلو ولا يحكم على فهرس: يطبع ما يراه `mp3_resync` ليُعرف
**لمَ تعذّر الترميم** (‏عطبٌ طويل · لا فجوة · معدّلٌ غيرُ ثابت) بدل التخمين.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "alignment"))

import mp3_resync as M                                           # noqa: E402
import run as R                                                  # noqa: E402


def main():
    if len(sys.argv) < 2:
        sys.exit("الاستعمال: resync_probe.py <رابط|مسار>")
    src = sys.argv[1]
    path = R._local_audio(src) if src.startswith("http") else src
    inp = R._audio_input(path)
    with open(inp, "rb") as f:
        d = f.read()
    frames, gaps = M.scan(d)
    cl = M.clusters(frames, gaps)
    print(f"الملفّ: {path} · بايتات {len(d)} · إطارات {len(frames)} · فجوات {len(gaps)} · عناقيد {len(cl)}")
    print(f"مدّةُ الخانات: {M.slots_ms(frames, gaps, len(frames)) / 1000:.2f}ث · "
          f"عدُّ الإطارات: {R._file_duration_ms(path) / 1000:.2f}ث")
    for g in gaps:
        nxt = g[2]
        a, b = frames[nxt - 1], frames[min(nxt, len(frames) - 1)]
        print(f"  فجوة: بايت {g[0]} · {g[1]} بايتاً · عند {M.slots_ms(frames, gaps, nxt) / 1000:.2f}ث "
              f"· معدّلان {a[4] // 1000}/{b[4] // 1000}ك.ب · ترددان {a[3]}/{b[3]}")
    try:
        from channel_mix import mono_filter
        filt = tuple(mono_filter(inp))
        x, rep = M.resync_decode(inp, lambda b: M.ffmpeg_decode_bytes(b, filt))
        print(f"✅ الترميم: {rep} · العيّنات {len(x)}")
    except Exception as ex:                                      # noqa: BLE001
        print(f"⛔ تعذّر الترميم: {type(ex).__name__}: {ex}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
