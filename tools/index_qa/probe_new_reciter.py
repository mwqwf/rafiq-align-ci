#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مسبارُ القارئ الجديد — **نصفُ الشبكة**، ويُشغَّل على CI لا على شبكة المالك.

    python tools/index_qa/probe_new_reciter.py --self-test
    python tools/index_qa/probe_new_reciter.py --id gharbi_warsh --riwaya warsh \\
        --base "https://archive.org/download/XXX/" --license "archive.org — …" \\
        --witness 89,104 --model <ggml.bin> --out work/probe.json --upload

## ما يفعله بالضبط

| الخطوة | الكلفة الشبكية | لماذا هنا لا محلّيّاً |
|---|---|---|
| 114 × `HEAD` ⇒ `status` + `Content-Length` | ‏114 طلباً بلا جسم | نتُ المالك ضعيفٌ متقطّع (القاعدة ٧) |
| 114 × `Range: 0-16383` ⇒ رأسُ MP3 | ‏≈1.8 م.ب | المدّةُ تُشتقّ من الترويسة بلا تنزيل الملفّ |
| تنزيلُ سورتَي الشاهد + تفريغُهما | ‏≈3–15 م.ب + حسابٌ ثقيل | whisper على عدّاءٍ مجانيّ |

⛔ **ولا يحكم هذا الملفُّ شيئاً:** يكتب مسباراً خاماً، والدرجاتُ تُبنى محلّيّاً
بـ`reciter_evidence.py --assemble` (‏حيث المرجعان على القرص والطيُّ شرطُ صحّة)،
والحكمُ للحُرّاس السبعة في `add_surah_reciter.py`. **فصلُ القياس عن الحكم مقصود.**

## ⛔ المدّةُ تُقرأ ولا تُقسَم على معدّلٍ مظنون

كثيرٌ من مصاحف المسح **VBR بترويسة `Xing`/`Info`** (‏جدولُ المسح يسمّيها
«Info(VBR)» في نصف الصفوف). فالقسمةُ على معدّل بِتٍّ ثابتٍ **تكذب فيها**، ولذلك:

1. إن وُجدت `Xing`/`Info` ⇒ **عدّادُ الإطارات فيها** ⇒ مدّةٌ دقيقة.
2. وإلّا (‏CBR) ⇒ `(الحجم − ID3) × 8 ÷ معدّل البِتّ` من أوّل إطار.

وطريقةُ الاشتقاق تُكتب في `durationFrom` لكلّ ملفّ، **فلا تختلط دقّةٌ بتقدير**.

## ⛔ درسٌ مستعارٌ بثمنه — الترويسةُ إلزامية

`r2.dev` يردّ **403** لـ`Python-urllib` و**200** لـ`Mozilla/5.0` (‏قِيس
2026-09-06)، وarchive.org كذلك يميّز العملاء. فـ`User-Agent` هنا **في مكان
الاستعمال** لا في جارٍ — «المعرفةُ التي لا تسكن مكانَ الاستعمال لا تحرس».
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:                                     # noqa: BLE001
        pass

TOOL = "probe_new_reciter-1.0"
UA = {"User-Agent": "Mozilla/5.0 (QuranRafiq probe)"}
HEAD_BYTES = 16384          # يسع ID3 معتاداً + أوّلَ إطارٍ + ترويسة Xing
TAG_WINDOW = 8192           # نافذةٌ ثانيةٌ **عند حدّ الوسم** — انظر أدناه

# ⛔⛔ **درسٌ مقيسٌ بثمنه (2026-09-08، جنديّ الفهرسة): النافذةُ الأولى وحدَها
#     تُجمّد ذراعَ «القرّاء الجدد» كلَّها.** ستّةُ مرشّحين (‏ثلاثةُ ورشٍ وثلاثةُ
#     قالون، من خمسة عناصرِ archive.org لرافعين مختلفين) خرجت مسابيرُهم
#     **684 ملفّاً كلُّها `status: 200`** ومع ذلك **`durationMs: null` في كلِّ
#     ملفّ** بحجّة «لا إطارَ صالحاً في الرأس» ⇒ فيسقط الحارسُ الثاني (‏ومعه
#     الخامسُ إذ لا مدّة) **لكلِّ مرشَّحٍ إلى الأبد**.
#
#     والسببُ في الأداة لا في المحتوى، مقيسٌ بالبايتات لا مظنوناً:
#       · `rabbani_warsh/104` — وسمُ ID3v2.3 جسمُه **39,150** ⇒ الصوتُ عند 39,160
#       · `sultani_warsh/104` — وسمُ ID3v2.3 جسمُه **66,731** ⇒ الصوتُ عند 66,741
#     و`first_frame(head, skip)` تبدأ البحثَ عند `skip` وهو **أبعدُ من طول
#     المخزن** (16,384) ⇒ الحلقةُ لا تدور دورةً واحدة، فيرجع `None` دائماً.
#     (‏وما يبدو إطاراً في أوّل 64 بايتاً `ff fe …` إنما هو **علامةُ ترتيبِ
#     بايتٍ UTF-16 داخل حقلٍ نصّيٍّ من الوسم**، فتوسيعُ النافذة وحدَه يستبدل
#     بالعمى **مزامنةً كاذبة**.)
#
# ⇒ **والعلاجُ نافذةٌ ثانيةٌ عند حدّ الوسم لا توسيعُ الأولى**: توسيعُ الأولى إلى
#   64ك.ب يضرب الكلفةَ الشبكية أربعةً على **كلّ** ملفٍّ (‏114 × 4 لكل مرشَّح)
#   ولا يكفي `sultani` أصلاً؛ والثانيةُ تُقرأ **لمن وسمُه أطولُ من النافذة
#   وحدَه**، وثمنُها ثمانيةُ كيلوبايت.
#
# ⛔ **وطولُ الوسم يُطرح من الحجم في كلتا الحالتين**: لو حُسب من النافذة
#   الثانية لَقُرئ صفراً (‏إذ لا `ID3` عند حدّ الوسم) فتزيد المدّةُ بطول الوسم —
#   و66ك.ب من 396ك.ب **سُدسُ الملفّ**، فيكذب الحارسُ الخامس في الاتجاه الآمن
#   ظاهراً والخطرِ حقيقةً.

# جداولُ MPEG-1/2/2.5 — منقولةٌ من `mp3dur.py` عمداً بلا تعديل (‏مصدرٌ واحد
# للحقيقة يُختبر في الملفّين)، والفرقُ أنّ هذا يقرأ **رأسَ** الملفّ لا كلَّه.
BR1 = [0, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448]
BR2 = [0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384]
BR3 = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320]
BRV2 = {1: [0, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256],
        2: [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160]}
SR = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000],
      0: [11025, 12000, 8000]}


# ───────────────────────── قراءةُ رأس MP3 ─────────────────────────
def id3_size(head: bytes) -> int:
    """طولُ وسم ID3v2 إن وُجد — يُطرح من الحجم قبل القسمة."""
    if len(head) >= 10 and head[:3] == b"ID3":
        return 10 + ((head[6] & 0x7F) << 21 | (head[7] & 0x7F) << 14
                     | (head[8] & 0x7F) << 7 | (head[9] & 0x7F))
    return 0


def first_frame(head: bytes, off: int) -> dict | None:
    """أوّلُ إطارٍ صالحٍ بعد `off` — ومعه موضعُه وطولُه، أو `None`."""
    i, limit = off, min(len(head) - 4, off + 8192)
    while i < limit:
        if head[i] == 0xFF and (head[i + 1] & 0xE0) == 0xE0:
            ver = (head[i + 1] >> 3) & 3
            layer = (head[i + 1] >> 1) & 3
            bri = (head[i + 2] >> 4) & 0xF
            sri = (head[i + 2] >> 2) & 3
            pad = (head[i + 2] >> 1) & 1
            if ver == 1 or layer == 0 or bri in (0, 15) or sri == 3:
                i += 1
                continue
            lay = 4 - layer
            if ver == 3:
                kbps = (BR1 if lay == 1 else BR2 if lay == 2 else BR3)[bri]
            else:
                kbps = BRV2[1 if lay == 1 else 2][bri]
            sr = SR[ver][sri]
            spf = 384 if lay == 1 else (1152 if (lay == 2 or ver == 3) else 576)
            flen = ((12 * kbps * 1000 // sr + pad) * 4 if lay == 1
                    else (spf // 8 * kbps * 1000) // sr + pad)
            if flen <= 0 or kbps <= 0:
                i += 1
                continue
            return {"pos": i, "len": flen, "kbps": kbps, "sampleRate": sr,
                    "samplesPerFrame": spf, "mpegVersion": ver, "layer": lay}
        i += 1
    return None


def xing_frames(head: bytes, fr: dict) -> int | None:
    """عدّادُ الإطارات من `Xing`/`Info` — **المدّةُ الدقيقة لملفّات VBR**.

    ⛔ ولا يُقبل العدّادُ إلا إن كانت رايةُ `frames` مرفوعة (‏البت 0)؛
    فترويسةٌ بلا عدّادٍ **ليست مصدرَ مدّة**، ولا يُخترع لها رقم.
    """
    base = fr["pos"] + 4
    for gap in (32, 17, 9):                # مواضعُ Xing حسب القناة والنسخة
        p = base + gap
        if p + 12 <= len(head) and head[p:p + 4] in (b"Xing", b"Info"):
            flags = int.from_bytes(head[p + 4:p + 8], "big")
            if flags & 1 and p + 12 <= len(head):
                n = int.from_bytes(head[p + 8:p + 12], "big")
                return n if 0 < n < 50_000_000 else None
            return None
    return None


def duration_of(head: bytes, size: int, buf_off: int = 0,
                tag_bytes: int | None = None) -> dict:
    """مدّةُ الملفّ من رأسه وحجمه — ومعها **من أين جاءت**.

    `buf_off` موضعُ أوّلِ بايتٍ من `head` داخل الملفّ (‏صفرٌ للنافذة الأولى)،
    و`tag_bytes` طولُ وسم ID3 مقروءاً من النافذة الأولى. وهما لازمان معاً حين
    يُقرأ الرأسُ من النافذة الثانية: الوسمُ ليس فيها فيُقرأ صفراً، **فيُمرَّر
    صراحةً كي يُطرح من الحجم** (‏وإلا زادت المدّةُ بطول الوسم كلِّه).
    """
    tag = id3_size(head) if tag_bytes is None else tag_bytes
    fr = first_frame(head, max(tag - buf_off, 0))
    if fr is None:
        return {"durationMs": None, "durationFrom": "لا إطارَ صالحاً في الرأس"}
    n = xing_frames(head, fr)
    if n:
        ms = round(n * fr["samplesPerFrame"] * 1000.0 / fr["sampleRate"])
        src = "xing"
    else:
        audio = max(size - tag, 0)
        ms = round(audio * 8 * 1000.0 / (fr["kbps"] * 1000))
        src = "cbr"
    return {"durationMs": ms, "durationFrom": src, "bitrateKbps": fr["kbps"],
            "sampleRate": fr["sampleRate"]}


# ───────────────────────── الشبكة ─────────────────────────
def _open(url: str, headers: dict, method: str = "GET", timeout: int = 60):
    req = urllib.request.Request(url, headers={**UA, **headers}, method=method)
    return urllib.request.urlopen(req, timeout=timeout)


def probe_file(url: str, attempts: int = 4) -> dict:
    """`HEAD` + رأسٌ بـ`Range` لملفٍّ واحد — بإعادةِ محاولةٍ متدرّجة.

    ⛔ **والخطأُ يُسمّى ولا يُبتلع**: صفٌّ بلا `status` يُقرأ عجزَ شبكةٍ لا
    غيابَ ملفّ، والفرقُ بينهما هو الفرقُ بين «يُعاد المسبار» و«يُردّ القارئ».
    """
    row: dict = {"status": None}
    for k in range(attempts):
        try:
            with _open(url, {}, "HEAD", timeout=45) as r:
                row["status"] = r.status
                cl = r.headers.get("Content-Length")
                row["bytes"] = int(cl) if cl and cl.isdigit() else None
            break
        except urllib.error.HTTPError as ex:
            row["status"] = ex.code          # 404 جوابٌ لا عطب
            break
        except Exception as ex:              # noqa: BLE001
            row["error"] = f"{type(ex).__name__}: {ex}"
            time.sleep(1.5 * (k + 1))
    if row.get("status") != 200:
        return row
    for k in range(attempts):
        try:
            with _open(url, {"Range": f"bytes=0-{HEAD_BYTES - 1}"}) as r:
                head = r.read(HEAD_BYTES)
            if not row.get("bytes"):
                row["bytes"] = None
            row.update(duration_of(head, row.get("bytes") or 0))
            # ⛔ وسمٌ أطولُ من النافذة ⇒ الصوتُ خارجَها بأسره. تُقرأ نافذةٌ
            #    ثانيةٌ **عند حدّ الوسم وحدَه** — التفصيلُ عند `TAG_WINDOW`.
            tag = id3_size(head)
            if row.get("durationMs") is None and tag + 4 > len(head):
                with _open(url, {"Range": f"bytes={tag}-{tag + TAG_WINDOW - 1}"}) as r2:
                    tail = r2.read(TAG_WINDOW)
                row.update(duration_of(tail, row.get("bytes") or 0,
                                       buf_off=tag, tag_bytes=tag))
                if row.get("durationMs") is not None:
                    # الأثرُ مكتوبٌ في المخرَج: من قرأ الصفَّ يعرف من أين جاء.
                    row["durationFrom"] += "+tag"
                    row["id3Bytes"] = tag
            row.pop("error", None)
            break
        except Exception as ex:              # noqa: BLE001
            row["error"] = f"header/{type(ex).__name__}: {ex}"
            time.sleep(1.5 * (k + 1))
    return row


def probe_all(base: str, workers: int = 8) -> dict:
    """السورُ 114 — بالتوازي، والترتيبُ محفوظٌ في المخرَج."""
    urls = {s: base.rstrip("/") + f"/{s:03d}.mp3" for s in range(1, 115)}
    out: dict = {}
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(probe_file, u): s for s, u in urls.items()}
        for f in cf.as_completed(futs):
            out[str(futs[f])] = f.result()
    return {str(s): out[str(s)] for s in range(1, 115)}


# ───────────────────────── الشاهدان ─────────────────────────
def transcribe(url: str, model: str, threads: int, work: str) -> str:
    """ينزّل سورةَ الشاهد كاملةً ويفرّغها — والنصُّ يُعاد كما سُمع."""
    os.makedirs(work, exist_ok=True)
    mp3 = os.path.join(work, "witness.mp3")
    wav = os.path.join(work, "witness.wav")
    last = None
    for k in range(4):
        try:
            with _open(url, {}, timeout=300) as r, open(mp3, "wb") as f:
                f.write(r.read())
            if os.path.getsize(mp3) > 16384:
                last = None
                break
            last = "حمولةٌ أقصرُ من 16ك.ب"
        except Exception as ex:              # noqa: BLE001
            last = ex
        time.sleep(2 * (k + 1))
    if last is not None:
        raise RuntimeError(f"تعذّر تنزيل الشاهد {url}: {last}")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp3,
                    "-ac", "1", "-ar", "16000", wav], check=True)
    from pywhispercpp.model import Model
    m = Model(model, n_threads=threads, language="ar",
              print_progress=False, print_realtime=False)
    return " ".join(s.text for s in m.transcribe(wav)).strip()


# ───────────────────────── الاختبارُ الذاتيّ ─────────────────────────
def _frame_bytes(kbps: int, sr_i: int = 0, ver: int = 3) -> bytes:
    """يبني ترويسةَ إطارٍ MPEG-1 Layer III بمعدّلٍ معلوم — لاختبار القارئ."""
    bri = BR3.index(kbps)
    return bytes([0xFF, 0xE0 | (ver << 3) | (1 << 1),
                  (bri << 4) | (sr_i << 2), 0x00])


def _self_test() -> None:
    # (١) الترويسةُ تُقرأ بمعدّلها وترددها — لا تخمين
    fr = first_frame(_frame_bytes(128) + b"\x00" * 800, 0)
    assert fr and fr["kbps"] == 128 and fr["sampleRate"] == 44100, fr
    fr64 = first_frame(_frame_bytes(64) + b"\x00" * 800, 0)
    assert fr64 and fr64["kbps"] == 64, fr64
    print("  ✅ (١) معدّلُ البِتّ والترددُ يُقرآن من أوّل إطار (128k · 64k)")

    # (٢) ID3 يُتخطّى ولا يُحسب صوتاً
    tag = b"ID3\x04\x00\x00" + bytes([0, 0, 0x01, 0x00])   # 128 بايتاً
    body = b"\x00" * 128 + _frame_bytes(128) + b"\x00" * 800
    assert id3_size(tag) == 138, id3_size(tag)
    fr = first_frame(tag + body, id3_size(tag))
    assert fr and fr["kbps"] == 128, fr
    print("  ✅ (٢) وسمُ ID3 يُقاس ويُتخطّى (‏138 بايتاً)")

    # (٣) CBR: المدّةُ = الحجم ÷ المعدّل — ودقيقةٌ عند 128k = 960 ك.ب
    d = duration_of(_frame_bytes(128) + b"\x00" * 800, 128 * 1000 // 8 * 60)
    assert d["durationFrom"] == "cbr" and abs(d["durationMs"] - 60000) < 50, d
    print(f"  ✅ (٣) CBR: ‏{d['durationMs']}م.ث لـ960ك.ب عند 128k")

    # (٤) ⛔⛔ **VBR يُقرأ من `Xing` لا بالقسمة** — وهي علّةٌ حقيقية: نصفُ
    #     صفوف جدول المسح «Info(VBR)»، والقسمةُ عليها تكذب. 5000 إطارٍ
    #     عند 44.1ك = 130.6ث، والحجمُ هنا يوافق 128k (‏= 60ث) فلو غلبت
    #     القسمةُ لظهر الرقمُ الخطأ.
    head = _frame_bytes(128) + b"\x00" * 32 + b"Xing" + (1).to_bytes(4, "big") \
        + (5000).to_bytes(4, "big") + b"\x00" * 400
    d = duration_of(head, 128 * 1000 // 8 * 60)
    assert d["durationFrom"] == "xing", d
    assert abs(d["durationMs"] - round(5000 * 1152 * 1000 / 44100)) < 2, d
    print(f"  ✅ (٤) VBR: ‏`Xing` تغلب القسمة — {d['durationMs']}م.ث لا 60000")

    # (٥) رايةُ العدّاد مطفأةٌ ⇒ لا يُخترع رقم، بل يُقسم ويُسمّى
    head = _frame_bytes(128) + b"\x00" * 32 + b"Info" + (0).to_bytes(4, "big") \
        + (5000).to_bytes(4, "big") + b"\x00" * 400
    assert duration_of(head, 128 * 1000 // 8 * 60)["durationFrom"] == "cbr"
    print("  ✅ (٥) `Info` بلا رايةِ عدّادٍ لا تُقرأ مدّةً — يُقسم ويُسمّى المصدر")

    # (٦) رأسٌ بلا إطارٍ ⇒ `durationMs=None` ⇒ **الحارسُ الثاني يمسكه**
    d = duration_of(b"\x00" * 4096, 1_000_000)
    assert d["durationMs"] is None, d
    from add_surah_reciter import check_evidence
    ev = {"files": {str(s): {"status": 200, "durationMs": 60000}
                    for s in range(1, 115)},
          "witnesses": [], "license": {"declared": "x"}}
    ev["files"]["9"].pop("durationMs")
    assert any(x.startswith("2:") for x in check_evidence(ev, "warsh")), \
        "⛔ رأسٌ غيرُ مقروءٍ لا يمسكه الحارسُ الثاني"
    print("  ✅ (٦) رأسٌ غيرُ مقروءٍ يصل الحارسَ الثاني `None` لا رقماً مخترَعاً")

    # (٧) ⭐⭐ **المقابلةُ بملفّاتٍ حقيقية** — والحالاتُ الستُّ فوقها اصطناعية،
    #     والاصطناعيُّ يوافق نموذجاً خاطئاً كما يوافق الصحيح. فيُقابَل الرأسُ
    #     وحدَه بعدّ الإطارات كلِّها (`mp3dur.dur`) على أصولٍ في المستودع.
    #     قِيس 2026-09-08: ثمانيةُ ملفّات، أقصى فارقٍ **0.01%**.
    import glob
    bench = sorted(glob.glob(os.path.join(ROOT, "assets-archive",
                                          "bench-audio", "*.mp3")))[:8]
    if not bench:
        print("  ⚠️ (٧) لا أصولَ صوتيةً هنا (‏مستودع CI) — تُقاس في مستودع الأدوات")
    else:
        from mp3dur import dur
        worst = 0.0
        for f in bench:
            head = open(f, "rb").read(HEAD_BYTES)
            est = duration_of(head, os.path.getsize(f))["durationMs"]
            ex = dur(f)
            ex_ms = (ex[0] if isinstance(ex, tuple) else ex) * 1000
            worst = max(worst, abs(est - ex_ms) / ex_ms * 100)
        assert worst < 2.0, f"⛔ الرأسُ وحده يخالف عدَّ الإطارات بـ{worst:.2f}%"
        print(f"  ✅ (٧) الرأسُ وحده = عدُّ الإطارات في {len(bench)} ملفّاً "
              f"حقيقيّاً — أقصى فارق {worst:.2f}%")

    # (٨) ⭐⭐ **وسمٌ أطولُ من النافذة** — الحالةُ التي جمّدت الذراعَ كلَّها
    #     (‏archive.org: ‏39,150 و66,731 بايتاً وسماً). ثلاثةُ أشياءَ تُثبَت هنا،
    #     وسقوطُ أيٍّ منها يعيد العطبَ بعينه.
    tag_len = 39_160                                    # وسمٌ + ترويستُه
    syncsafe = bytes([(tag_len - 10) >> 21 & 0x7F, (tag_len - 10) >> 14 & 0x7F,
                      (tag_len - 10) >> 7 & 0x7F, (tag_len - 10) & 0x7F])
    # ⛔ وفي حشو الوسم **مزامنةٌ كاذبة** `ff fe` — وهي عينُ ما رأيناه في
    #    ملفّات archive.org (‏علامةُ ترتيبِ بايتٍ UTF-16 في حقلٍ نصّيّ).
    tag8 = b"ID3\x03\x00\x00" + syncsafe + b"TSSE\x00\x00\xff\xfe\x33\x06" \
        + b"\x00" * (tag_len - 22)
    assert id3_size(tag8) == tag_len, id3_size(tag8)
    audio8 = (_frame_bytes(128) + b"\x00" * 413) * 1149        # ‏≈480ك.ب
    size8 = tag_len + len(audio8)

    # (أ) النافذةُ الأولى وحدَها **عمياءُ لا كاذبة**: لا مدّةَ، ولا مزامنةٌ كاذبة
    win1 = (tag8 + audio8)[:HEAD_BYTES]
    d8 = duration_of(win1, size8)
    assert d8["durationMs"] is None, f"⛔ النافذةُ الأولى ادّعت مدّةً: {d8}"

    # (ب) النافذةُ الثانيةُ عند حدّ الوسم تقرأ الإطار
    win2 = (tag8 + audio8)[tag_len:tag_len + TAG_WINDOW]
    d8b = duration_of(win2, size8, buf_off=tag_len, tag_bytes=tag_len)
    assert d8b["durationMs"] is not None, f"⛔ النافذةُ الثانيةُ عمياءُ أيضاً: {d8b}"

    # (ج) ⛔ **وطولُ الوسم مطروحٌ من الحجم** — وإلا زادت المدّةُ بطوله.
    want = round(len(audio8) * 8 * 1000.0 / (128 * 1000))
    assert abs(d8b["durationMs"] - want) <= 1, (d8b["durationMs"], want)
    naive = duration_of(win2, size8)          # بلا تمريرِ الوسم = الخطأُ عينُه
    assert naive["durationMs"] - d8b["durationMs"] > 2000, \
        "⛔ إهمالُ الوسم لم يعد يُغيّر المدّة — فالاختبارُ لا يحرس شيئاً"
    print(f"  ✅ (٨) وسمٌ {tag_len} بايتاً > النافذة: الأولى عمياء · الثانيةُ "
          f"{d8b['durationMs']}م.ث · وإهمالُ الوسم كان سيزيدها "
          f"{naive['durationMs'] - d8b['durationMs']}م.ث")

    print(f"✅ --self-test أخضر · {TOOL}")


# ───────────────────────── الرفع ─────────────────────────
def upload(doc: dict, rid: str) -> str:
    import boto3
    c = json.load(open(os.path.join(ROOT, "secure", "r2_credentials.json"),
                       encoding="utf-8"))
    s3 = boto3.client("s3", endpoint_url=c["endpoint"],
                      aws_access_key_id=c["accessKeyId"],
                      aws_secret_access_key=c["secretAccessKey"],
                      region_name="auto")
    key = f"state/newreciters/{rid}.probe.json"
    # ⛔ بادئةٌ واحدةٌ لا غير — ولا حذفَ ولا كتابةَ فوق فهرسٍ مخدوم.
    assert key.startswith("state/newreciters/"), key
    s3.put_object(Bucket=c["bucket"], Key=key,
                  Body=json.dumps(doc, ensure_ascii=False, indent=1).encode(),
                  ContentType="application/json")
    return key


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--id")
    ap.add_argument("--riwaya")
    ap.add_argument("--base", help="مجلّدُ الملفّات (‏تُضاف NNN.mp3)")
    ap.add_argument("--license", default="")
    ap.add_argument("--witness", default="89,104",
                    help="سورتا الشاهد (‏`reciter_evidence.py --witness-surahs`)")
    ap.add_argument("--model", help="نموذج ggml للتفريغ")
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", default="work/probe.json")
    ap.add_argument("--upload", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        _self_test()
        return
    for need in ("id", "riwaya", "base", "model"):
        if not getattr(a, need):
            sys.exit(f"⛔ ينقص --{need}")
    if not a.license.strip():
        # ⛔ الحارسُ السادس يردّه لاحقاً، **ويُقال هنا مبكّراً** كي لا يُنفق
        #    عدّاءٌ كاملٌ على مسبارٍ مردودٍ سلفاً.
        sys.exit("⛔ لا صفَّ رخصةٍ — المصدرُ وما أعلنه يُكتبان بنصّهما")

    t0 = time.time()
    files = probe_all(a.base, a.workers)
    ok = sum(1 for v in files.values() if v.get("status") == 200)
    noh = [s for s, v in files.items()
           if v.get("status") == 200 and not v.get("durationMs")]
    errs = {s: v["error"] for s, v in files.items() if v.get("error")}
    print(f"‏HEAD 200: {ok}/114 · بلا رأسٍ مقروء: {len(noh)} · "
          f"أخطاءُ شبكة: {len(errs)}")
    if errs:
        print("⚠️ أخطاءٌ تُقرأ عجزَ شبكةٍ لا غيابَ ملفّ:",
              json.dumps(dict(list(errs.items())[:5]), ensure_ascii=False))

    transcripts: dict = {}
    wit = [int(x) for x in a.witness.replace(",", " ").split()]
    for s in wit:
        row = files.get(str(s)) or {}
        if row.get("status") != 200:
            print(f"⚠️ س{s} حالتُها {row.get('status')} — لا تُفرَّغ")
            continue
        url = a.base.rstrip("/") + f"/{s:03d}.mp3"
        try:
            transcripts[str(s)] = transcribe(url, a.model, a.threads,
                                             os.path.join(HERE, "work"))
            print(f"✅ تفريغُ س{s}: {transcripts[str(s)][:60]}…")
        except Exception as ex:              # noqa: BLE001
            print(f"⚠️ تعذّر تفريغُ س{s}: {ex}")

    doc = {"probedBy": TOOL, "id": a.id, "riwaya": a.riwaya, "base": a.base,
           "files": files, "transcripts": transcripts,
           "license": {"declared": a.license.strip()},
           "elapsedSec": int(time.time() - t0),
           "runId": os.environ.get("GITHUB_RUN_ID")}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(f"↑ {a.out} · {doc['elapsedSec']}ث")
    if a.upload:
        print("☁️", upload(doc, a.id))


if __name__ == "__main__":
    main()
