# -*- coding: utf-8 -*-
"""اختبار القاع: هل تنقلب مبرَّأةٌ عند 700م.ث؟ — المبرَّأ وحده يُختبر."""
import json, os, sys, time
sys.path.insert(0, 'tools/alignment'); sys.path.insert(0, 'tools/tasmi_bench')
from basmala_local import cut, text_of, fuzzy_seq, basmala_tail, WORK
from basmala_postpass import fetch_head
from pywhispercpp.model import Model
URLS = {'hawashi': 'https://server11.mp3quran.net/hawashi/{s:03d}.mp3',
        'koshi_warsh': 'https://server11.mp3quran.net/koshi/{s:03d}.mp3',
        'deban_qalun': 'https://server16.mp3quran.net/deban/Rewayat-Qalon-A-n-Nafi/{s:03d}.mp3'}
d = json.load(open('tools/tasmi_bench/work/basmala_graded.json', encoding='utf-8'))
clean = [x for x in d if not (x.get('basmala') or x.get('tail'))]
out_p = 'tools/tasmi_bench/work/basmala_floor700.json'
out = json.load(open(out_p, encoding='utf-8')) if os.path.exists(out_p) else []
seen = {(o['reciter'], o['surah']) for o in out}
m = Model('tools/tasmi_bench/work/ggml-q8.bin', n_threads=1, language='ar',
          print_progress=False, print_realtime=False)
clip = os.path.join(WORK, 'f.wav')
flip = 0
for n, x in enumerate(clean, 1):
    if (x['reciter'], x['surah']) in seen:
        continue
    mp3 = os.path.join(WORK, f"f_{x['reciter']}_{x['surah']:03d}.mp3")
    row = dict(reciter=x['reciter'], surah=x['surah'], startMs=x['startMs'])
    try:
        fetch_head(URLS[x['reciter']].format(s=x['surah']), mp3)
        w = text_of(m, cut(mp3, x['startMs'], 700, clip)).split()
        row['heard700'] = ' '.join(w[:5])
        row['flip'] = bool(fuzzy_seq(w) or basmala_tail(w))
        flip += row['flip']
    except Exception as e:
        row['error'] = str(e)[:60]
    finally:
        if os.path.exists(mp3):
            os.remove(mp3)
    out.append(row)
    json.dump(out, open(out_p, 'w', encoding='utf-8'), ensure_ascii=False)
    if row.get('flip'):
        print(f"⚠️ انقلبت: {x['reciter']} س{x['surah']} · {row['heard700']}", flush=True)
    elif n % 15 == 0:
        print(f"[{n}/{len(clean)}] …", flush=True)
print(f"\nاختبار القاع 700م.ث: **{sum(1 for o in out if o.get('flip'))} انقلبت من {len(out)}**")
