# -*- coding: utf-8 -*-
"""قياس القاعدة البديلة: هل آيات «البرهان الكامل» توقيتها صحيح فعلاً؟

نولّد بالقاعدة الجديدة آياتٍ **ترفضها العتبة النسبية وتقبلها قاعدة البرهان
الكامل**، ثم نمرّرها على بوابة الدورة الكاملة (قصّ مدى الكلمة وتفريغه وحده).
إن لم تبلغ سقف الأداة − 5 نقاط فلا تُعتمد القاعدة.
"""
import os, sys, json, random
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, "."); sys.path.insert(0, ".."); sys.path.insert(0, "../../alignment")
from common import read_jz, load_index, load_text, norm
from build_index import fetch_verified, QALUN_URL, MIRROR_URL, local_onset
from generate import ayah_word_times
from roundtrip import transcribe_clip, verdict

ti = read_jz("../../alignment/work/timings_qalun_husary_qalun.jz")
idx = load_index(); text = load_text("qalun")
starts = {s["n"]: s["start"] for s in idx["surahs"]}
have = set(e["ayahId"] for e in read_jz("../out/wordtimings_husary_qalun.jz")["entries"])
os.makedirs("work/audio", exist_ok=True)

rows = []
for sn in (91, 100, 82, 87, 93):
    cand = [e for e in ti["entries"] if e.get("confBand") == "HIGH"
            and e["ayahId"].startswith("%d:" % sn) and e["ayahId"] not in have]
    if not cand:
        continue
    mp3 = "work/audio/%03d.mp3" % sn
    if not os.path.exists(mp3):
        try:
            fetch_verified(QALUN_URL.format(surah=sn), mp3)
        except IOError:
            print("  المصدر الأصلي تعذّر — مرآة R2", flush=True)
            fetch_verified(MIRROR_URL.format(surah=sn), mp3)
    for e in cand:
        an = int(e["ayahId"].split(":")[1]); raw = text[starts[sn] + an - 1]
        on = local_onset(mp3, e["startMs"], "work/audio", e["ayahId"].replace(":", "_"))
        w, m = ayah_word_times(mp3, e["startMs"], e["endMs"], raw,
                               "sd_%03d_%03d" % (sn, an), onset_ms=on)
        if not w or not m.get("fullEvidence") or m["acc"] >= 0.75:
            continue                      # نريد ما قبلته القاعدة الجديدة وحدها
        rw = raw.split()
        for i, x in enumerate(w):
            rows.append((e["ayahId"], i, x, mp3, norm(rw[i]),
                         norm(rw[i-1]) if i else None,
                         norm(rw[i+1]) if i+1 < len(rw) else None))
print("كلمات من آيات قبلتها القاعدة الجديدة وحدها: %d" % len(rows), flush=True)
random.Random(7).shuffle(rows); rows = rows[:40]

def lenient(t, h):
    if not h: return False
    for x in h.split():
        if x == t: return True
        a, b = (x, t) if len(x) < len(t) else (t, x)
        if a in b and len(a) >= max(3, 0.6 * len(b)): return True
    return False

strict = soft = 0
for aid, i, x, mp3, tgt, prv, nxt in rows:
    heard = transcribe_clip(mp3, x["startMs"], x["endMs"], "sd_%s_%d" % (aid.replace(":", "_"), i))
    v = verdict(heard, tgt, prv, nxt)
    if v in ("EXACT", "CONTAINS"): strict += 1
    if lenient(tgt, heard): soft += 1
    print("  %s ك%d %s هدف«%s» سُمع«%s»" % (aid, i+1, v, tgt, heard), flush=True)
n = len(rows) or 1
print("\n=== النتيجة على %d كلمة ===" % n)
print("صارم %d/%d = %.1f%% (سقف QUL 20.0%%)" % (strict, n, strict/n*100))
print("متسامح %d/%d = %.1f%% (سقف QUL 35.0%%)" % (soft, n, soft/n*100))
# ⛔ كان هنا خطأ: قارنت **العدد** بعتبة **نسبة** (18>=15 صح، 23>=30 خطأ) فطبع
# حكماً معكوساً على بيانات ناجحة. البوابة على النسب لا الأعداد.
sp, lp = strict / n * 100, soft / n * 100
ok = sp >= 20.0 - 5 and lp >= 35.0 - 5
print("الحكم: %s (صارم %.1f%% ≥ %.1f · متسامح %.1f%% ≥ %.1f)"
      % ("✅ تُعتمد" if ok else "⛔ لا تُعتمد", sp, 15.0, lp, 30.0))
