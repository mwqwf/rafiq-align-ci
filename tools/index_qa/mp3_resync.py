#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""فكُّ ملفّ MP3 فيه إطاراتٌ تالفةٌ قصيرة **بإعادة التزامن كما يفعل المشغّل** — وبزمنٍ لا ينزاح.

⭐ **سببُه مقيس (‏fixV 2026-10-05 · `hafs/mhsny` ملفّ 002):** في الملفّ ثلاثُ فجواتٍ في الإطارات
(‏691 بايتاً) قبل حدّ 2:218، فيُبلغ ffmpeg «Header missing» ويُرفض الإحصاءُ كلُّه بنافذةٍ واحدة
«تعذّر تفريغُها» — والمشغّلُ (‏والتطبيق) يتخطّاها فيُسمع ما بعدها في موضعه. فهذا **قياسٌ لما في
الملفّ فعلاً** لا تليينٌ للحارس، بشروطٍ تجعله أصعبَ خداعاً:

1. ‏ffmpeg يُسقط الإطاراتِ التالفةَ ويُلصق ما بعدها ⇒ **كلُّ ما بعد العطب ينزاح مبكّراً** بقدر ما سقط.
   ⇒ يُقاس الساقطُ عند كلّ عنقودِ عطبٍ **بفكّ بادئتين** (‏قبله · وبعده بعشرين إطاراً سليماً) ومقابلةِ
   المفكوك بعدد الخانات (‏الإطاراتُ المعدودة + خاناتُ البايتات المتخطّاة)، ويُحشى صمتاً **بقدره
   بالضبط** عند موضعه. فما بعد العطب يعود إلى موضعه بالعيّنة (‏اختبارٌ يقيسه بالارتباط).
2. ‏**العطبُ الطويلُ صوتٌ مفقودٌ حقّاً** ⇒ يُرفض: عنقودٌ يُسقط ≥ `MAX_LOSS_MS` (‏ثانية)، أو مجموعٌ
   ≥ ثانية، أو أكثرُ من `MAX_CLUSTERS` عنقوداً. ثوابتُ لا تُقرأ من البيئة.
3. ‏خطأُ فكٍّ **بلا فجوةٍ في الإطارات** يفسّره ⇒ يُرفض (‏علّةٌ مجهولة لا تُبرّأ).
4. ‏المعدّلُ حول كلّ فجوةٍ ثابت (‏CBR) وإلا رُفض: خاناتُ البايتات لا تُقدَّر في VBR.
5. ‏الطولُ النهائيّ يُقابَل بعدد الخانات بسماح الفكّ الكامل نفسِه (‏200م.ث) وإلا رُفض.

وحدودُه المعلنة: داخل العنقود نفسِه (‏≤ ثانية) يقع الصمتُ عند بدئه بدقّة حشو الترميز (‏≤ ~50م.ث).
"""
from __future__ import annotations

import os
import subprocess
import tempfile

BR = {1: [0, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448],
      2: [0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384],
      3: [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320]}
BR2 = {1: [0, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256],
       2: [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160]}
SR = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000]}

MAX_LOSS_MS = 1000          # ⛔ ثابت: عطبٌ يُسقط ثانيةً فأكثر صوتٌ مفقود لا إطارٌ تالف
MAX_CLUSTERS = 8            # ⛔ ثابت: ملفٌّ معطوبٌ في مواضع كثيرة لا يُرمَّم
CLUSTER_FRAMES = 40         # فجواتٌ بينها أقلّ من 40 إطاراً (~1ث) عنقودٌ واحد
SETTLE_FRAMES = 20          # إطاراتٌ سليمةٌ بعد العنقود يستقرّ فيها مخزونُ البِتّات
FULL_TOL_MS = 200           # سماحُ الفكّ الكامل نفسُه في `run._full_decode_pcm`
GAP_SLOT_MAX_MS = 300       # ⛔ ثابت: فجوةٌ أكبرُ من هذا لا يُقدَّر زمنُها من حجمها
RATE = 16000


class Unrecoverable(RuntimeError):
    """عطبٌ لا يُرمَّم بإعادة التزامن — يبقى خطأً «غير حاسم» كما كان."""


def _hdr(d, i):
    """(طولُ الإطار، عيّناتُه، معدّلُ العيّنة، معدّلُ البِتّ) أو None."""
    if d[i] != 0xFF or (d[i + 1] & 0xE0) != 0xE0:
        return None
    ver = (d[i + 1] >> 3) & 3
    layer = (d[i + 1] >> 1) & 3
    bri = (d[i + 2] >> 4) & 0xF
    sri = (d[i + 2] >> 2) & 3
    pad = (d[i + 2] >> 1) & 1
    if ver == 1 or layer == 0 or bri in (0, 15) or sri == 3:
        return None
    lay = 4 - layer
    br = (BR if ver == 3 else BR2)[lay if ver == 3 else (1 if lay == 1 else 2)][bri] * 1000
    sr = SR[ver][sri]
    if lay == 1:
        return (12 * br // sr + pad) * 4, 384, sr, br
    spf = 1152 if (lay == 2 or ver == 3) else 576
    flen = (spf // 8 * br) // sr + pad
    return (flen, spf, sr, br) if flen > 0 else None


def scan(d):
    """الإطاراتُ `[(إزاحة، طول، عيّنات، معدّل عيّنة، معدّل بِتّ)]` والفجواتُ الداخليّة
    `[(إزاحة، بايتات، فهرسُ الإطار التالي)]` — بمنطق `mp3dur` نفسِه (‏تخطّي البايتات حتى رأسٍ صالح).
    ⛔ ما قبل أوّل إطارٍ (‏ID3) وما بعد آخره (‏TAG) ليسا فجوتين."""
    i = 0
    if d[:3] == b"ID3" and len(d) >= 10:
        i = 10 + ((d[6] & 0x7f) << 21 | (d[7] & 0x7f) << 14 | (d[8] & 0x7f) << 7 | (d[9] & 0x7f))
    frames, gaps, skip_from = [], [], None
    while i < len(d) - 4:
        h = _hdr(d, i)
        if h is None:
            if skip_from is None:
                skip_from = i
            i += 1
            continue
        if skip_from is not None and frames:
            gaps.append((skip_from, i - skip_from, len(frames)))
        skip_from = None
        frames.append((i, h[0], h[1], h[2], h[3]))
        i += h[0]
    return frames, gaps


def frames_ms(frames, upto_frame):
    """زمنُ **الإطارات الصحيحة** وحدَها حتى `upto_frame` (‏غيرَ داخل) — معلومٌ بالضبط من ترويساتها.

    ⭐ (‏fixV 2026-10-05 · `hafs/mhsny` ملفّ 002): البايتاتُ التالفةُ ليست إطاراتٍ ناقصةً بل
    **حشوٌ لا صوتَ فيه** (‏في هذا الملفّ ترويساتٌ بمعدّلاتٍ وترددات غريبة: 320 ثمّ 64 ك.ب/ث
    و32000 ثمّ 22050 هز وسط ملفٍّ 192ك.ب/44.1ك.هز) ⇒ **لا تُقدَّر زمناً من حجمها**، وقياسُ
    الساقط يكون بزمن الإطارات الصحيحة مقابلَ المفكوك. وبه زال رفضٌ كاذبٌ («المعدّلُ غيرُ ثابت»)
    بلا أيّ تخمين: مجموعُ الإطارات الصحيحة هو مقياسُ `mp3dur` نفسُه الذي يحكم به الحارس."""
    return sum(f[2] / f[3] for f in frames[:upto_frame]) * 1000.0


def slots_ms(frames, gaps, upto_frame):
    """زمنُ الخانات حتى الإطار `upto_frame` (‏غيرَ داخل): الإطاراتُ المعدودة وخاناتُ الفجوات قبله."""
    t = sum(f[2] / f[3] for f in frames[:upto_frame]) * 1000.0
    for off, nbytes, nxt in gaps:
        if nxt >= upto_frame or nxt == 0:     # الفجوةُ بعد آخر إطارٍ في البادئة ليست منها
            continue
        prev = frames[nxt - 1]
        t += round(nbytes / prev[1]) * prev[2] / prev[3] * 1000.0
    return t


def clusters(frames, gaps):
    """تجميعُ الفجوات المتقاربة: `[[فجوة، ...], ...]`."""
    out = []
    for g in gaps:
        if out and g[2] - out[-1][-1][2] < CLUSTER_FRAMES:
            out[-1].append(g)
        else:
            out.append([g])
    return out


def gap_slot_ms(frames, g):
    """زمنُ خانةِ فجوةٍ بتقديرها من حجمها بمعدّل الإطار السابق — دالّةٌ صِرفةٌ مختبَرة."""
    nxt = g[2]
    if nxt == 0:
        return 0.0
    prev = frames[nxt - 1]
    return round(g[1] / prev[1]) * prev[2] / prev[3] * 1000.0


def resync_decode(path, decode_bytes):
    """يُرجع `(pcm، تقرير)`؛ و`decode_bytes(bytes) -> numpy float32 16ك.هز` (‏الفكُّ نفسُه بلا رفضٍ للخطأ).

    ⛔ يرفع `Unrecoverable` في كلّ حالةٍ لا يُثبت فيها أنّ الزمنَ بعد العطب في موضعه."""
    import numpy as np
    with open(path, "rb") as f:
        d = f.read()
    frames, gaps = scan(d)
    if not gaps:
        raise Unrecoverable("خطأُ فكٍّ بلا فجوةٍ في الإطارات تفسّره — علّةٌ مجهولة لا تُرمَّم")
    cl = clusters(frames, gaps)
    if len(cl) > MAX_CLUSTERS:
        raise Unrecoverable(f"{len(cl)} عنقودَ عطبٍ > {MAX_CLUSTERS} — ملفٌّ معطوبٌ لا يُرمَّم")
    # ⛔ **بدلَ شرط «ثباتِ المعدّل حول الفجوة»** (‏كان يردّ صادقاً: ملفُّ `mhsny/002` فيه ثلاثُ
    #    فجواتٍ حشوُها ترويساتٌ غريبةُ المعدّل 320/64ك.ب و32000/22050هز وسط ملفٍّ 192ك.ب/44.1ك.هز)
    #    ⇒ **حدٌّ على التقدير نفسِه**: خانةُ أيّ فجوةٍ لا تتجاوز `GAP_SLOT_MAX_MS`، فيبقى خطأُ
    #    التقدير أصغرَ من سماح الفكّ الكامل؛ ومعه شاهدُ الاتّساق: مجموعُ الخانات يطابق زمنَ
    #    الإطارات الصحيحة (‏مقياسَ `mp3dur` الذي يحكم به الحارس) بالسماح نفسِه. وإلا رُدّ.
    for g in gaps:
        nxt = g[2]
        if nxt == 0:
            continue
        est = gap_slot_ms(frames, g)
        if est > GAP_SLOT_MAX_MS:
            raise Unrecoverable(f"فجوةُ {g[1]} بايتاً عند {g[0]} تُقدَّر {est:.0f}م.ث > "
                                f"{GAP_SLOT_MAX_MS} — لا يُقدَّر زمنٌ بهذا الحجم")
    if abs(slots_ms(frames, gaps, len(frames)) - frames_ms(frames, len(frames))) > FULL_TOL_MS:
        raise Unrecoverable("خاناتُ الفجوات تخالف زمنَ الإطارات الصحيحة بأكثر من السماح")

    def dec_ms(nframe):
        """فكُّ البادئة حتى نهاية الإطار nframe−1 (‏حدُّ إطار) ⇒ مدّتُها المفكوكة."""
        end = frames[nframe - 1][0] + frames[nframe - 1][1]
        return len(decode_bytes(d[:end])) * 1000.0 / RATE

    base_f0 = cl[0][0][2]                    # أوّلُ إطارٍ سليمٍ بعد أوّل فجوة
    # البادئةُ المرجعيّة: الإطاراتُ قبل الفجوة الأولى
    s1 = dec_ms(base_f0)
    s1_slots = slots_ms(frames, gaps, base_f0)
    whole = decode_bytes(d)
    inserts, prev_loss, rep = [], 0.0, []
    for c in cl:
        first, last = c[0][2], c[-1][2]
        after = min(last + SETTLE_FRAMES, len(frames))
        a_ms = dec_ms(after)
        loss = (slots_ms(frames, gaps, after) - s1_slots) - (a_ms - s1)
        delta = loss - prev_loss
        if delta >= MAX_LOSS_MS:
            raise Unrecoverable(f"عنقودٌ عند {slots_ms(frames, gaps, first) / 1000:.1f}ث يُسقط "
                                f"{delta:.0f}م.ث ≥ {MAX_LOSS_MS} — صوتٌ مفقودٌ حقّاً لا إطارٌ تالف")
        if delta < -FULL_TOL_MS / 4:
            raise Unrecoverable(f"عنقودٌ أخرج صوتاً زائداً {-delta:.0f}م.ث — لا يُفسَّر بإطارٍ ساقط")
        pos = int(round((dec_ms(first) if first != base_f0 else s1) * RATE / 1000.0))
        inserts.append((pos, max(0, int(round(delta * RATE / 1000.0)))))
        rep.append({"atMs": round(slots_ms(frames, gaps, first)), "gapBytes": sum(g[1] for g in c),
                    "lostMs": round(delta, 1)})
        prev_loss = loss
    if prev_loss >= MAX_LOSS_MS:
        raise Unrecoverable(f"مجموعُ الساقط {prev_loss:.0f}م.ث ≥ {MAX_LOSS_MS} — صوتٌ مفقود")
    x = np.asarray(whole, dtype="float32")
    for pos, n in sorted(inserts, reverse=True):
        x = np.concatenate([x[:pos], np.zeros(n, dtype="float32"), x[pos:]])
    want = slots_ms(frames, gaps, len(frames))
    got = len(x) * 1000.0 / RATE
    if abs(got - want) > FULL_TOL_MS:
        raise Unrecoverable(f"المرمَّم {got:.0f}م.ث والخاناتُ {want:.0f}م.ث — لا يطابق الملفّ")
    return x, {"clusters": rep, "slotsMs": round(want), "decodedMs": round(got)}


def ffmpeg_decode_bytes(b, extra_filter=()):
    """فكُّ بايتاتٍ إلى f32 أحاديّ 16ك.هز بـffmpeg، **متسامحاً مع أخطاء الإطار** (‏rc≠0 وحده يُرفض)."""
    import numpy as np
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as t:
        t.write(b)
        p_in = t.name
    try:
        p = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", p_in, *extra_filter,
                            "-f", "f32le", "-ac", "1", "-ar", str(RATE), "pipe:1"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=1800, check=False)
    finally:
        os.unlink(p_in)
    if p.returncode != 0:
        raise Unrecoverable(f"ffmpeg فشل ({p.returncode}): {p.stderr.decode('utf-8', 'replace')[-200:]}")
    if len(p.stdout) % 4:
        raise Unrecoverable("ffmpeg أخرج float32 غير محاذى")
    x = np.frombuffer(p.stdout, dtype="<f4").copy()
    if not np.isfinite(x).all():
        raise Unrecoverable("ffmpeg أخرج عينات NaN/Inf")
    return x
