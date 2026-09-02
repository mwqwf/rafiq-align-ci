# -*- coding: utf-8 -*-
"""إعادة فحص السلبيات القابلة للشكّ بقطعٍ **متدرّج** (درس 7e: الغياب لا يُثبت
بنافذةٍ واحدة). لا يُعاد إلا ما `startMs` فيه < 3500م.ث — فما بدأ بعد نهاية
البسملة المقيسة (‏~3.2ث) **يستحيل أن يحويها**، وإعادته إنفاقٌ بلا معنى."""
import json, os, sys, time
sys.path.insert(0, 'tools/alignment'); sys.path.insert(0, 'tools/tasmi_bench')
from basmala_local import cut, text_of, fuzzy_seq, basmala_tail, WORK, BAS
from basmala_postpass import fetch_head
from pywhispercpp.model import Model

URLS = {'hawashi': 'https://server11.mp3quran.net/hawashi/{s:03d}.mp3',
        'koshi_warsh': 'https://server11.mp3quran.net/koshi/{s:03d}.mp3',
        'deban_qalun': 'https://server16.mp3quran.net/deban/Rewayat-Qalon-A-n-Nafi/{s:03d}.mp3'}
# ⛔ قفلٌ يمنع نسختين تكتبان مخرَجاً واحداً: وقع فعلاً (‏`pkill` من Git Bash
# لا يقتل عمليات ويندوز) فتداخلت نسخةٌ قبل الإصلاح وأخرى بعده على الملف نفسه،
# فقرأتُ صفّاً قديماً وحسبته جديداً. **وهو العطب الذي حذّرتُ منه غيري.**
_LOCK = 'tools/tasmi_bench/work/basmala_graded.lock'
if os.path.exists(_LOCK):
    age = time.time() - os.path.getmtime(_LOCK)
    if age < 900:
        sys.exit(f"⛔ نسخةٌ أخرى تعمل (‏قفلٌ عمره {age:.0f}ث). اقتلها أو احذف {_LOCK}")
open(_LOCK, 'w').write(str(os.getpid()))
import atexit
atexit.register(lambda: os.path.exists(_LOCK) and os.remove(_LOCK))

r = json.load(open('tools/tasmi_bench/work/basmala_local.json', encoding='utf-8'))
risky = [x for x in r if not x.get('basmala') and x['startMs'] < 3500]
out_path = 'tools/tasmi_bench/work/basmala_graded.json'
done = json.load(open(out_path, encoding='utf-8')) if os.path.exists(out_path) else []
seen = {(d['reciter'], d['surah']) for d in done}
m = Model('tools/tasmi_bench/work/ggml-q8.bin', n_threads=1, language='ar',
          print_progress=False, print_realtime=False)
clip = os.path.join(WORK, 'g.wav')
for n, x in enumerate(risky, 1):
    if (x['reciter'], x['surah']) in seen:
        continue
    mp3 = os.path.join(WORK, f"g_{x['reciter']}_{x['surah']:03d}.mp3")
    row = dict(reciter=x['reciter'], surah=x['surah'], startMs=x['startMs'])
    try:
        fetch_head(URLS[x['reciter']].format(s=x['surah']), mp3)
        seq = {}
        # درجةٌ سادسة بطلب 7e: قد يكتمل «الرحيم» عند 3ث ولا تظهر أول
        # كلمةٍ من السورة إلا عند 6ث، فمن وقف عند 4ث رأى بسملةً ناقصة.
        # ⛔ القاع يُختبر لا يُفترض (تنبيه 7e): تكدّس الاكتشافات عند أدنى
        # درجةٍ هو **شكل العيّنة المبتورة من طرفها**. فأُنزل القاع إلى ثانية
        # واحدة — وثلاثٌ من أربع حالاتٍ عنده كُشفت عند 1500 وكانت ستفوتني.
        for d in (1000, 1500, 2000, 3000, 4000, 6000):
            w = text_of(m, cut(mp3, x['startMs'], d, clip)).split()
            seq[d] = ' '.join(w[:6])
            if fuzzy_seq(w) is not None:
                row['basmala'] = True; row['at'] = d; break
            if basmala_tail(w):
                row['tail'] = True; row['at'] = d
        row['seq'] = seq
    except Exception as e:
        row['error'] = str(e)[:60]
    finally:
        if os.path.exists(mp3):
            os.remove(mp3)
    done.append(row)
    json.dump(done, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False)
    if row.get('basmala') or row.get('tail'):
        print(f"[{n}/{len(risky)}] ⚠️ {x['reciter']} س{x['surah']} · "
              f"{'بسملة' if row.get('basmala') else 'ذيل'} عند {row.get('at')}م.ث", flush=True)
    elif n % 10 == 0:
        print(f"[{n}/{len(risky)}] …", flush=True)
hits = [d for d in done if d.get('basmala') or d.get('tail')]
print(f"\nأُعيد فحص {len(done)} · **جديد مكتشَف: {len(hits)}**")
for h in hits:
    print(f"   {h['reciter']:13s} س{h['surah']:3d} · {'بسملة' if h.get('basmala') else 'ذيل'}")
