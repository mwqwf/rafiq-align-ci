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
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
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
            # بصمةُ الرأس — بلا نداءٍ زائد: البايتاتُ مقروءةٌ أصلاً للمدّة.
            # وهي نصفُ كاشفِ «الملفّ نفسُه باسمين» (‏الحارس الثامن في `main`).
            row["headSha"] = hashlib.sha256(head).hexdigest()[:16]
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


# ─────────────── جدولُ الأسماء حين لا يكون الاسمُ رقماً ───────────────
# ⛔ **درسٌ بثمنه (2026-09-08، خمسُ موجاتٍ مهدورة):** خمسةُ مسابرَ رجعت 114
#    ملفاً بـHEAD 404 والعناصرُ موجودةٌ كلُّها — والمانعُ أنّ الأسماء ليست
#    `NNN.mp3` بل `ar_001_Mustapha_Gharbi_Warsh.mp3` و`sura_100_64kb.mp3`.
#    وكُتب حينها أنّ العلاجَ «حقلُ نمطٍ في الكتالوج يبتّه المشرف».
# ⭐ **وقياسُ 2026-09-09 نقض ذلك:** الكتالوجُ والتطبيقُ **يحملان الحقلَ منذ
#    تلاوةِ لغظف الشنقيطي**: `Reciter.files` في `QuranRepository.kt:243`
#    و`surahUrl` فيه `files.getOrNull(surah-1)?.let { base + it }` (:251)،
#    و`AudioMirrorBridge.kt:56` يستدلّ برتبة الاسم في القائمة عند المرآة.
#    ⇒ لا قرارَ بنيةٍ ولا حقلَ جديد — **نقصٌ في هذه الأداة وحدَها**: لم تكن
#    تقرأ الأسماءَ الحقيقية ولا تكتبها في البرهان.
def _digit_runs(name: str) -> list[str]:
    """مجموعاتُ الأرقام المتتالية في الاسم، بترتيب ظهورها."""
    runs, cur = [], ""
    for ch in name:
        if ch.isdigit():
            cur += ch
        elif cur:
            runs.append(cur)
            cur = ""
    if cur:
        runs.append(cur)
    return runs


def map_names(names: list[str]) -> list[str] | None:
    """يطابق أسماءَ الملفّات بأرقام السور — **بتقابلٍ تامٍّ أو لا شيء**.

    ⛔ **لا تُخمَّن الرتبة:** تُجرَّب كلُّ رتبةِ مجموعةِ أرقامٍ في الاسم (‏الأولى
    ثم الثانية…)، ولا تُقبل إلا التي تعطي **1..114 كلَّها بلا تكرار**. فاسمٌ
    مثل `sura_100_64kb.mp3` فيه مجموعتان (`100` و`64`)، والأولى وحدَها تعطي
    تقابلاً — والثانيةُ تعطي تكراراً فتُردّ من تلقائها. **وترتيبُ الأبجدية
    ليس مطابقةً** ولا يُقبل بديلاً: `010` تسبق `002` في مضيفين معروفين.
    """
    mp3 = [n for n in names if n.lower().endswith(".mp3")]
    if len(mp3) < 114:
        return None
    for rank in range(4):
        table: dict[int, str] = {}
        for n in mp3:
            runs = _digit_runs(os.path.basename(n))
            if len(runs) <= rank:
                continue
            try:
                s = int(runs[rank])
            except ValueError:                            # noqa: PERF203
                continue
            if 1 <= s <= 114 and s not in table:
                table[s] = n
            elif 1 <= s <= 114:
                table[s] = ""                             # تكرارٌ ⇒ إبطال
        if len(table) == 114 and all(table.values()):
            return [table[s] for s in range(1, 115)]
    return None


def archive_names(base: str) -> list[str] | None:
    """أسماءُ عنصرِ archive.org الحقيقية — **نداءٌ واحدٌ يسبق الموجة**."""
    marker = "archive.org/download/"
    if marker not in base:
        return None
    ident = base.split(marker, 1)[1].strip("/").split("/")[0]
    if not ident:
        return None
    url = f"https://archive.org/metadata/{ident}/files"
    for k in range(3):
        try:
            with _open(url, {}, timeout=90) as r:
                doc = json.loads(r.read().decode("utf-8", "replace"))
            break
        except Exception:                                 # noqa: BLE001
            if k == 2:
                return None
            time.sleep(1.5 * (k + 1))
    rows = doc.get("result") if isinstance(doc, dict) else doc
    if not isinstance(rows, list):
        return None
    return map_names([r.get("name", "") for r in rows if isinstance(r, dict)])


# ⛔ **الاسمُ يُرمَّز قبل أن يصير عنواناً** — وثمنُ غيابه مقيسٌ 2026-09-09:
#    مصحفا `shaykhna_qalun` و`naji_qalun` (‏موريتانيا · رأسُ أولوية المالك)
#    ملفّاتُهما `001 الفاتحة.mp3` — وفيها **فراغٌ وحروفٌ عربية**. فرفع
#    `urllib.request` استثناءَ `InvalidURL: URL can't contain control characters`
#    **على السور الـ114 كلِّها**، فخرج المسبارُ بـ`status: None` × 114 وصفرِ
#    تفريغ — **ويقرؤه الحارسُ الأوّل «ملفّاتٌ بـHEAD 200: 0/114»، أي مصحفٌ
#    غائب.** والمصحفُ كاملٌ: العنوانُ المرمَّز نفسُه يردّ `200`.
#    ⇒ **عطبُ أداةٍ تنكّر في زيّ حكمٍ على المحتوى** — وهو الصنفُ الذي حذّر منه
#    هذا الملفُّ نفسُه في درسِ `obk`. والتقييدُ في موضعٍ واحدٍ لا موضعين.
#    (‏و`safe` هنا هو نفسُه في `add_surah_reciter` عند كتابة `files` — فما
#    يُسبر به هو ما يُشغَّل به، ولا مسطرتان.)
def surah_url(base: str, surah: int, names: list[str] | None = None) -> str:
    root = base.rstrip("/")
    name = names[surah - 1] if names else f"{surah:03d}.mp3"
    return root + "/" + urllib.parse.quote(name, safe="/-._~()!*'")


def probe_all(base: str, workers: int = 8, names: list[str] | None = None) -> dict:
    """السورُ 114 — بالتوازي، والترتيبُ محفوظٌ في المخرَج."""
    urls = {s: surah_url(base, s, names) for s in range(1, 115)}
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

    # (٩) جدولُ الأسماء — يُقبل بالتقابل التامّ ويُردّ بغيره
    gharbi = [f"ar_{s:03d}_Mustapha_Gharbi_Warsh.mp3" for s in range(1, 115)]
    assert map_names(list(reversed(gharbi))) == gharbi, "⛔ نمطُ الغربي لم يُطابَق"
    # ⛔ والمجموعةُ الثانية (`64kb`) تُبطل نفسَها بالتكرار فتُختار الأولى
    jabery = [f"sura_{s}_64kb.mp3" for s in range(1, 115)]
    assert map_names(jabery) == jabery, "⛔ نمطُ الحياني لم يُطابَق"
    # ناقصٌ ⇒ لا شيء (‏113 اسماً لا تُقبل «أكثرُها موجود»)
    assert map_names(gharbi[:-1]) is None, "⛔ قُبلت 113"
    # مكرَّرٌ ⇒ لا شيء (‏س7 مرّتين وس8 غائبة)
    dup = list(gharbi)
    dup[7] = dup[6]
    assert map_names(dup) is None, "⛔ قُبل جدولٌ فيه تكرار"
    # ورقمٌ خارج المدى في الرتبة الأولى لا يخدع (‏`2020_007.mp3`)
    dated = [f"2020_{s:03d}.mp3" for s in range(1, 115)]
    assert map_names(dated) == dated, "⛔ لم تُجرَّب الرتبةُ الثانية"
    print("  ✅ (٩) جدولُ الأسماء: تقابلٌ تامٌّ يُقبل · ناقصٌ ومكرَّرٌ يُردّان · "
          "والرتبةُ الثانيةُ تُجرَّب عند فشل الأولى")

    # (١٠) العنوانُ يُرمَّز — والاختبارُ يحرس ما كلّف موجةً كاملة (2026-09-09):
    #      اسمٌ فيه فراغٌ وعربيّةٌ كان يرفع `InvalidURL` على 114 سورة، فيخرج
    #      المسبارُ «0/114» — حكماً على مصحفٍ كامل بعطبِ أداة.
    u = surah_url("https://x/y/", 1, ["001 الفاتحة.mp3"])
    assert " " not in u and "%20" in u, f"⛔ الفراغُ لم يُرمَّز: {u}"
    assert u.encode("ascii", "strict"), "⛔ في العنوان حرفٌ غيرُ ascii"
    assert surah_url("https://x/y", 7) == "https://x/y/007.mp3", "⛔ الرقميُّ تغيّر"
    assert surah_url("https://x/y", 1, [gharbi[0]]) == "https://x/y/" + gharbi[0], \
        "⛔ الاسمُ الـascii رُمّز بلا حاجة"
    print("  ✅ (١٠) العنوانُ يُرمَّز: الفراغُ والعربيّةُ تصيران `%`، "
          "والرقميُّ والـascii كما هما")

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
    ap.add_argument("--names", default="auto",
                    help="`auto` (‏الافتراض: أرقامٌ ثم ميتاداتا archive عند "
                         "تعذّرها) · `none` (‏أرقامٌ حصراً) · أو مسارُ ملفّ "
                         "JSON فيه 114 اسماً بترتيب السور")
    ap.add_argument("--license", default="")
    ap.add_argument("--witness", default="auto",
                    help="`auto` (‏الافتراض: يُقاس من الرواية بـ"
                         "`reciter_evidence.best_witnesses`) أو سورتان بفاصلة")
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
    # ⛔ **الرقمُ أوّلاً والاسمُ عند تعذّره** — لا العكس: أكثرُ المضيفين يرقّمون،
    #    فنداءُ الميتاداتا لا يُنفق إلا على من ردَّ رقمُه. والقياسُ **سورةٌ واحدة**
    #    (‏س1) لا 114: موجةٌ كاملةٌ من 404 ثمنُها 114 طلباً بلا فائدة.
    names = None
    if a.names == "auto":
        first = probe_file(a.base.rstrip("/") + "/001.mp3", attempts=2)
        if first.get("status") != 200:
            names = archive_names(a.base)
            if names:
                print(f"🔤 أسماءٌ لا أرقام — طوبقت 114 من الميتاداتا: "
                      f"«{names[0]}» … «{names[113]}»")
            else:
                print("⚠️ س1 لم ترجع 200 ولا جدولَ أسماءٍ مطابقاً — "
                      "المسبارُ يمضي بالأرقام، والحكمُ للحُرّاس")
    elif a.names not in ("", "none"):
        names = json.load(open(a.names, encoding="utf-8"))
        if not (isinstance(names, list) and len(names) == 114):
            sys.exit("⛔ ملفُّ الأسماء ليس قائمةً من 114 اسماً")
    files = probe_all(a.base, a.workers, names)
    ok = sum(1 for v in files.values() if v.get("status") == 200)
    noh = [s for s, v in files.items()
           if v.get("status") == 200 and not v.get("durationMs")]
    errs = {s: v["error"] for s, v in files.items() if v.get("error")}
    print(f"‏HEAD 200: {ok}/114 · بلا رأسٍ مقروء: {len(noh)} · "
          f"أخطاءُ شبكة: {len(errs)}")
    if errs:
        print("⚠️ أخطاءٌ تُقرأ عجزَ شبكةٍ لا غيابَ ملفّ:",
              json.dumps(dict(list(errs.items())[:5]), ensure_ascii=False))

    # ── الحارسُ الثامن: «الملفّ نفسُه باسمين» ──────────────────────────
    # ⛔ **سببُه مقيسٌ بثمنه (2026-09-09):** `rabbani_warsh` و`iraoui_warsh`
    #    مضيا في المسبار والمحاذاة كاملةً — ساعاتِ حوسبةٍ لكلٍّ — ثمّ رُدّا
    #    عند البوابة بـ«بصمات مكرّرة: 1». والعلّةُ **عند الناشر لا عندنا**:
    #      `rabbani` 070.mp3 = 071.mp3 (‏2,264,407 بايت، والرأسُ نفسُه)
    #      `iraoui`  040.mp3 = 041.mp3 (‏14,285,391 بايت، والرأسُ نفسُه)
    #    ⇒ إعادةُ المحاذاة تنزّل البايتاتِ نفسَها فتُنتج العطبَ نفسَه،
    #    والإسقاطُ يمنعه D-186 (‏السورُ الأربعُ كلُّها فوق 20 آية).
    # ⭐ **والكشفُ هنا مجّانيّ:** `bytes` و`headSha` مقروءان أصلاً في المسبار،
    #    فيُقاس ما كان يُكتشف بعد ساعاتٍ **قبل أن يُنفق عدّاءٌ واحد**.
    # ⛔ **وشرطان لا شرط:** الطولُ وحدَه يقع فيه تصادفٌ نادر (‏سورتان بمدّةٍ
    #    واحدةٍ إلى إطار)، والرأسُ وحدَه يتطابق في وسمِ ID3 المكرّر. فمعاً
    #    يقطعان.
    dup: dict = {}
    for s, v in files.items():
        if v.get("status") != 200 or not v.get("bytes") or not v.get("headSha"):
            continue
        dup.setdefault((v["bytes"], v["headSha"]), []).append(int(s))
    twins = sorted((ss for ss in dup.values() if len(ss) > 1), key=lambda x: x[0])
    if twins:
        print("⛔ **عطبُ ناشرٍ — الملفُّ نفسُه لأكثرَ من سورة** "
              f"({len(twins)} مجموعة):")
        for ss in twins:
            b, h = next(k for k, v2 in dup.items() if v2 is ss)
            print(f"   سور {ss} ← {b:,} بايت · رأس {h}")
        print("   ⇒ لا تُصلحه محاذاةٌ (البايتاتُ نفسُها) ولا يبيحه D-186 "
              "إسقاطاً متى زادت السورةُ على 20 آية. **السبيلُ مصدرٌ بديلٌ "
              "لهذه السور، أو ردُّ القارئ.**")

    transcripts: dict = {}
    # ⛔ **ولا يُورَث رقمُ شاهدٍ من ترويسة**: الافتراضُ القديم `89,104` كان
    #    فيه **س104 ميّتةً** (‏نصُّها واحدٌ في الروايتين ⇒ `conflict` دائم)،
    #    والبديلُ الظاهرُ (‏س106/96/107 — أقوى ما يفرّق) **فخٌّ أسوأ**: قِصَرُها
    #    يُهبِط التفريغَ تحت حدّ الحارس الثالث. فالقياسُ من الرواية نفسِها.
    # ⛔ **وثلاثةٌ لا اثنان، والسببُ حسابيٌّ لا احتياطيّ:** الشاهدُ الطويل
    #    يفرّق 1.4–1.7% من كلماته، و`CONFLICT_MARGIN` = 5% ⇒ `conflict`
    #    **مضمونٌ** لا محتمَل، والحارسُ الرابع يمرّره عند ثلاثةٍ فأكثر
    #    (`add_surah_reciter.py:115`). فاثنان = رفضٌ مؤكَّد وعدّاءٌ ضائع.
    if a.witness.strip() == "auto":
        from reciter_evidence import best_witnesses
        wit = best_witnesses(a.riwaya, 3)
        print(f"🎯 شاهدا {a.riwaya} مقيسَين: " + " · ".join(f"س{s}" for s in wit))
    else:
        wit = [int(x) for x in a.witness.replace(",", " ").split()]
    for s in wit:
        row = files.get(str(s)) or {}
        if row.get("status") != 200:
            print(f"⚠️ س{s} حالتُها {row.get('status')} — لا تُفرَّغ")
            continue
        url = surah_url(a.base, s, names)
        try:
            transcripts[str(s)] = transcribe(url, a.model, a.threads,
                                             os.path.join(HERE, "work"))
            print(f"✅ تفريغُ س{s}: {transcripts[str(s)][:60]}…")
        except Exception as ex:              # noqa: BLE001
            print(f"⚠️ تعذّر تفريغُ س{s}: {ex}")

    doc = {"probedBy": TOOL, "id": a.id, "riwaya": a.riwaya, "base": a.base,
           "names": names,
           "files": files, "transcripts": transcripts,
           # يُكتب دائماً — والقائمةُ الفارغةُ خبرٌ أيضاً: «فُحص ولم يوجد».
           "duplicateFiles": [{"surahs": ss,
                               "bytes": next(k for k, v2 in dup.items()
                                             if v2 is ss)[0],
                               "headSha": next(k for k, v2 in dup.items()
                                               if v2 is ss)[1]}
                              for ss in twins],
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
