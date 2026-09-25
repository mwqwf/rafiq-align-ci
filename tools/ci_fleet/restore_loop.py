#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""حلقةُ **استرجاع الآيات المفقودة** — سحابيّةٌ بلا جهاز المالك.

    python tools/ci_fleet/restore_loop.py scan   [--limit 3]   # يقيس ويُطلق المحاذاة
    python tools/ci_fleet/restore_loop.py gate   [--limit 6]   # يُبوّب المرشَّحين المحسَّنين
    python tools/ci_fleet/restore_loop.py promote               # يرقّي ما مرّ بحكمه

**لماذا هذا الملفّ؟** النبّاضُ (`keepalive.yml`) يحكم ويرقّي **لغير المنشورين
قصداً** — «التحسينُ الهامشيُّ لا يُقدَّم على قارئٍ لا فهرسَ له البتّة». وذلك
صوابٌ حين يكون التحسينُ هامشيّاً؛ **وليس هامشيّاً** أن يجد القارئُ سورةَ الأنعام
**سبعين آيةً من 165**. فهذه الحلقةُ للمنشورين وحدَهم، وشرطُها **زيادةُ آياتٍ
حقيقيّة** لا تجميل.

## الطريقةُ — كلُّها قياسٌ لا تخمين (نُفّذت بيدٍ ليلةَ 2026-09-13 فأثمرت 383 آية)

1. **جردٌ من الدلو لا من وثيقة**: سورٌ غائبةٌ كلّياً، أو حاضرةٌ تغطيتُها < 75%.
2. **سلامةُ المصدر بلا تنزيلِ صوت**: حجمُ الملفّ (HEAD) مقابلَ مدّةٍ متوقَّعةٍ من
   **أربعة مراجعَ مستقلّة**، ومعدّلِ بتٍّ مقيسٍ من القارئ نفسِه.
   ⛔ **والمرجعُ الواحدُ يُضلّ**: أعطى `deban/22` نسبةَ 0.87 («مبتور») والثلاثةُ
   الباقون 1.18 و1.01 و1.08 — فالحكمُ **بالوسيط** لا بمرجع.
3. **التخطّي مقيسٌ من القارئ نفسِه**: وسيطُ `startMs` للآية الأولى في **جارات**
   السورة = طولُ بسملته هناك. ⛔ ولا يُؤخذ من سُلَّمٍ ثابت: سُلَّمُ `basmala.yml`
   سقفُه 3000م.ث وبسملةُ `husary_douri` **10160م.ث**، فيقول «لا بسملة» كذباً.
   ⛔ ولا يُترك صفراً: `realign_surah` بـ`skip_ms=0` **يبتلع البسملة دائماً**
   لأنّ الملفّ يبدأ بها — وهو ما وقع في تسعةٍ من تسعة.
4. **الحَكَمُ هو الحارسُ لا هذا الملفّ**: ما لا تصحّ محاذاتُه يردّه الحارسُ ولا
   يُنشر. فالمحاولةُ آمنةٌ بطبعها، وأسوأُ ما فيها تشغيلةٌ مجّانيّةٌ تُهدر.

## ⛔ حدودٌ لا تُتجاوز
- **لا يُرقّى إلا ما زادت مداخلُه** عن المنشور — فالتحسينُ يُقاس بالآيات لا بالنيّة.
- **ولا يُرفع تجميدٌ إلا للحظةِ ترقيةٍ متحقَّقة**: يُسأل `promote.py` أوّلاً بلا
  `--yes`، فإن قال «جاهز» رُفع التجميدُ بسببٍ مكتوبٍ ثمّ رُقّي. وإلا **لا يُمَسّ**.
- **ولا تُخفَّض عتبةٌ ولا يُعطَّل حارس**: القرارُ كلُّه لـ`promote.py` بحُرّاسه.
- **ولا يُمَسّ قارئٌ في الطيران** (له تشغيلةٌ جاريةٌ أو منتظرة).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                          # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "index_qa"))

from run import fetch_index, list_indexes, s3, audit as _run_audit  # noqa: E402
from drop_surah import SURAH_AYAHS_OF                          # noqa: E402

# مراجعُ كاملةُ الصوت — أربعةٌ لا واحد (§2 أعلاه).
# ⛔⛔ **وعطبٌ قِيس 2026-09-20 وأُصلح هنا: ثلاثةٌ من الأربعة كانت ناقصةَ
#    المداخل هي نفسُها** — `tblawi` ‏6227/6236 و`harthi` 6230 و`abdullahk` 6208
#    (‏و`a_turki` وحدَه كامل)، مقروءاً من `ops/out/state.json`. ومدّةُ سورةٍ في
#    مرجعٍ ناقصٍ **أقصرُ من الحقّ**، فالمتوقَّعُ يصغر والنسبةُ ترتفع ⇒ الحارسُ
#    **أسهلُ خداعاً في الاتّجاه الخطر**: يمرّر مبتوراً على أنّه سليم.
# 🧪 والأثرُ مقيسٌ لا مظنون (`tools/ci_fleet/test_source_ratio_refs.py`): مصدرٌ
#    نسبتُه الحقيقيّةُ 0.70 يُقرأ **0.875** بحال المراجع القديمة ⇒ يعبر عتبةَ
#    0.85 كذباً؛ وبمراجعَ كاملةٍ يُقرأ 0.700 بالضبط.
# ✅ **والعلاجُ إصلاحُ المراجع لا خفضُ العتبة**: أُضيف `bari` و`shaheen` وهما
#    متحقَّقا الكمال (لا أثرَ لهما في جدول النقص)، فصار الوسيطُ على ستّةٍ ثلثُها
#    كاملٌ متحقَّق. ⛔ ولم تُمَسّ `SOUND` ولا أيُّ عتبةٍ أخرى.
# ⏭️ وما يبقى لمن بعدي: جردُ الفهارس الكاملة (6236/6236) واستبدالُ الناقصةِ
#    كلِّها — والقائمةُ تُشتقّ من الدلو لا من هذا التعليق.
REFS = ["timings/hafs/a_turki.jz", "timings/hafs/bari.jz",
        "timings/hafs/shaheen.jz", "timings/hafs/tblawi.jz",
        "timings/hafs/harthi.jz", "timings/hafs/abdullahk.jz"]
UA = {"User-Agent": "Mozilla/5.0"}
SOUND = 0.85          # وسيطُ نسبةِ الحجم الذي دونه يُعدّ المصدرُ مبتوراً
# ⛔⛔ **فجوةٌ بنيويّةٌ قِيست 2026-09-20 وسُدّت هنا:** كانت `LOWCOV = 0.75`
#    بينما `index_qa/low_coverage_scan.py` يشتكي عند **0.98** ⇒ النطاقُ
#    **[0.75, 0.98)** لا تلمسه حلقةٌ واحدة: الماسحُ يراه ولا يُصلحه، والحلقةُ
#    تُصلح ولا تراه. ومقيسٌ من الدلو أنّ فيه **معظمَ الـ667 سورةً الحاضرةَ
#    الناقصة** (‏21 فهرساً فقط دون 70٪، والباقي في النطاق الأعمى) ⇒ **646 سورةً
#    كانت محرومةً من أيّ علاجٍ إلى الأبد**، وهي «آخرُ سطرٍ» في عمل الفهرسة.
# ✅ **وتوسيعُها لا يفجّر الإنفاق**: السقفُ `--limit` لكلّ شوطٍ (‏3 في
#    `restore.yml`) هو الذي يحكم الصرف، والترتيبُ `-gap` يُقدّم الأكبرَ نقصاً
#    ⇒ الأثرُ أنّ الصغيرَ **يدخل الطابورَ** بدل أن يكون غيرَ مرئيّ، لا أن
#    تُطلق مئاتُ التشغيلات. ومَن أراد تسريعاً فالدِّيالُ `--limit` لا هذه.
# ⛔ وليست عتبةَ حارس: `SOUND` (‏0.85) و«العطب الجسيم» (‏5٪) لم تُمَسّا، وهذه
#    **مِصفاةُ اختيارِ عملٍ** — توسيعُها يزيد ما يُفحص ولا يُجيز شيئاً.
LOWCOV = float(os.environ.get("RESTORE_LOWCOV", "0.98"))   # تغطيةُ سورةٍ حاضرةٍ تُعدّ دونها ناقصة
MIN_AYAHS = 3         # لا يُنفق عدّاءٌ على أقلَّ من هذا
# ⛔⛔ **وحدُّ الثلاثِ وحدَه كان يهجر أخطرَ نقصٍ عند المستخدم** (قِيس 2026-09-20):
#    **ثمانيةٌ وعشرون قارئاً تنقصهم آيةٌ أو آيتان من الفاتحة** — أكثرِ سورةٍ
#    تُقرأ — ومنهم مَن تنقصه **الآيةُ الأولى** (‏`arkani` · `kurdi` · `lhdan` ·
#    `i_sanankoua`) أو **السابعة** (‏`harthi` · `khan`). وكلُّها `gap < 3`
#    ⇒ **لا تدخل الطابورَ أبداً، فلا تُصلَح أبداً**. (الشاهد: `ops/out/1712_miss_1.txt`.)
# ⭐ **والعلّةُ أنّ الحدَّ مطلقٌ والضررُ نسبيّ**: آيةٌ من 286 في البقرة نقصٌ
#    يسير، وآيةٌ من سبعٍ في الفاتحة **سُبعُ السورة**. ⇒ يُضاف قاعُ تغطيةٍ نسبيٌّ
#    ينجو به القصيرُ المتضرّرُ وحدَه، ويبقى الحدُّ المطلقُ على حاله لما سواه.
# ⚖️ وكلفةً: الترتيبُ `-gap` يُقدّم الأكبرَ نقصاً، فهذه تقف **آخرَ الطابور**
#    ⇒ لا تُزاحم عملاً أنفعَ منها، ولا تُنفَق عليها إلا بعد فراغه.
SMALL_GAP_FLOOR = float(os.environ.get("RESTORE_SMALL_GAP_FLOOR", "0.95"))

# مصدرٌ بديلٌ **لسورةٍ بعينها** بعد قياس المصدر الأصلي، لا استبدالٌ عشوائيّ
# للمصحف كله. `3siri/9` في المصدر المسجّل حجمه 10,582,833 بايت ونسبةُ حجمه
# إلى المتوقّع بوسيط المراجع الأربعة 0.19 (restore 35185281620)، بينما المصدر
# البديل لنفس القارئ والرواية يعلن 114 سورة وحجمُ س9 فيه 57,088,047 بايت.
# يبقى `source_ratio` أدناه هو الحارس الفعلي: إن لم يبلغ 0.85 لا تُطلق المحاذاة.
SOURCE_OVERRIDES = {
    (row["riwaya"], row["reciter"], int(row["surah"])): row["base"]
    for row in json.loads(
        (ROOT / "tools" / "ci_fleet" / "source_overrides.json").read_text(
            encoding="utf-8"))
}

# محاولاتُ realign التي انتهت بلا مرشّحٍ على **المصدر والمحرّك نفسيهما**.
# هذا سجلّ مانعٍ للهدر، لا حكمُ جودة: تغييرُ المصدر المسجّل أو المحرّك يجعل
# البصمة مختلفةً ويعيدها إلى الأهلية، أما إعادةُ الأمر نفسه فتعيد العطب نفسه.
_blocked_path = ROOT / "tools" / "ci_fleet" / "blocked_realigns.json"
BLOCKED_REALIGNS = {
    (row["riwaya"], row["reciter"], int(row["surah"]), row["source"],
     row["engine"])
    for row in json.loads(_blocked_path.read_text(encoding="utf-8"))
}
REALIGN_ENGINE = "realign-surah-v1"


def blocked_realign(riwaya: str, reciter: str, surah: int, source: str) -> bool:
    return (riwaya, reciter, surah, source, REALIGN_ENGINE) in BLOCKED_REALIGNS


def head_len(url: str) -> int:
    def measured(response) -> int:
        content_range = response.headers.get("Content-Range", "")
        if "/" in content_range:
            total = content_range.rsplit("/", 1)[-1]
            if total.isdigit():
                return int(total)
        return int(response.headers.get("Content-Length", 0))

    try:
        rq = urllib.request.Request(url, method="HEAD", headers=UA)
        with urllib.request.urlopen(rq, timeout=45) as r:
            size = measured(r)
        if size:
            return size
    except Exception:                                          # noqa: BLE001
        pass
    # بعض مرايا الصوت لا تجيب HEAD مع أنها تخدم الملف كاملاً. GET لبايتٍ واحد
    # يثبت الوجود والحجم من Content-Range، ولا ينزّل الملف إلى العدّاء.
    rq = urllib.request.Request(url, headers={**UA, "Range": "bytes=0-0"})
    with urllib.request.urlopen(rq, timeout=60) as r:
        size = measured(r)
    if not size:
        raise ValueError(f"لا طولَ قابلاً للقياس: {url}")
    return size


def surah_ends(idx) -> dict:
    out = {}
    for e in idx["entries"]:
        s = int(e["ayahId"].split(":")[0])
        out[s] = max(out.get(s, 0), e.get("endMs") or 0)
    return out


def first_starts(idx) -> dict:
    out = {}
    for e in idx["entries"]:
        s, a = e["ayahId"].split(":")
        if a == "1":
            out[int(s)] = e.get("startMs") or 0
    return out


def catalog_bases() -> dict:
    cl, b = s3()
    cat = json.loads(cl.get_object(Bucket=b, Key="catalog/reciters.json")["Body"].read())
    out = {}
    for r in cat["riwayat"]:
        riw = r.get("id") or r.get("key")
        for rc in r.get("reciters", []):
            if rc.get("mode") != "ayah":
                out[(riw, rc.get("id"))] = rc.get("base")
    return out


def file_tables(cat: dict) -> dict:
    """`{(الرواية، القارئ): {سورة: اسم} أو None}` لكلّ قارئٍ له جدولُ `files`.

    القيمةُ `None` تعني جدولاً ليس 114 بالضبط ⇒ لا يُقاس ولا يُطلق (‏شرطُ
    `batch_run.catalog_files` نفسُه). ومَن لا جدولَ له لا يظهر هنا فيبقى على
    القالب الرقميّ حرفاً. ⚖️ دالّةٌ محضةٌ على كتالوجٍ مقروء: بلا شبكةٍ ولا دلو.
    """
    out = {}
    for r in cat.get("riwayat", []):
        riw = r.get("id") or r.get("key")
        for rc in r.get("reciters", []):
            files = rc.get("files")
            if files:
                out[(riw, rc.get("id"))] = (
                    {i + 1: n for i, n in enumerate(files)} if len(files) == 114 else None)
    return out


def catalog_file_tables() -> dict:
    cl, b = s3()
    return file_tables(json.loads(
        cl.get_object(Bucket=b, Key="catalog/reciters.json")["Body"].read()))


def realign_template(base: str, names: dict | None) -> str:
    """ما يُمرَّر `url_template` إلى `realign_surah.yml`: المجلّدُ وحدَه لقارئ
    الجدول (‏يحلّه `resolve_url.py` بـ`reciter_id`)، والقالبُ الرقميُّ لغيره."""
    return base.rstrip("/") if names is not None else f"{base}{{s:03d}}.mp3"


def source_base(bases: dict, riwaya: str, reciter: str, surah: int) -> str | None:
    """المصدر المقاس للسورة، ثم مصدر الكتالوج لبقية السور."""
    return SOURCE_OVERRIDES.get((riwaya, reciter, surah),
                                bases.get((riwaya, reciter)))


def needs_restore(have: int, exp: int) -> bool:
    """أتستحقّ هذه السورةُ محاولةَ استرجاع؟ — شرطٌ واحدٌ في دالّةٍ **تُختبر**.

    ⛔ كان سطراً داخلَ حلقةٍ لا يُقاس إلا بتشغيل الدلو كلِّه، فأُخرج كما هو
    حرفاً (‏لا تغييرَ في منطقه) ليُقابَل بحالاتٍ معلومةِ الجواب.
    ⚖️ وهو **مِصفاةُ عملٍ لا حارسُ نشر**: يقول «انظر في هذه»، ولا يقول «رقِّ».
    """
    if exp <= 0:
        return False
    gap = exp - have
    if gap <= 0:
        return False
    cov = have / exp
    # الحدُّ المطلقُ أو القاعُ النسبيُّ — أيُّهما تحقّق كفى.
    big_enough = gap >= MIN_AYAHS or cov < SMALL_GAP_FLOOR
    return big_enough and (have == 0 or cov < LOWCOV)


def source_ratio(idx, base: str, surah: int, refs, names: dict | None = None,
                 size=None) -> float | None:
    """نسبةُ حجمِ الملفّ إلى المتوقَّع — **وسيطُ أربعةِ مراجع**.

    `names`: جدولُ `files` من الكتالوج `{سورة: اسم}` لمضيف المجلّد، أو `None`
    فيبقى القالبُ الرقميُّ `{base}{s:03d}.mp3` حرفاً كما كان.
    ⛔ **عطبٌ مقيسٌ 2026-09-25:** كان القالبُ الرقميُّ يُبنى لـ`warsh/gharbi_warsh`
    وأسماؤه `ar_036_Mustapha_Gharbi_Warsh.mp3` ⇒ 404 ⇒ «نسبة=None» في كلّ شوط،
    فتُرك 18 آيةً في ثماني سور بحكمٍ كاذبٍ بموت المصدر. والرابطُ الآن يُحلّ من
    الجدول بمنطق `resolve_url.py` نفسِه، ولا يُخمَّن: سورةٌ لا اسمَ لها ⇒ لا قياس.
    `size`: دالّةُ الحجم (‏الافتراضُ `head_len`) — تُحقن في الاختبار بلا شبكة.
    """
    size = size or head_len

    def url(s: int) -> str:
        if names is None:
            return f"{base}{s:03d}.mp3"
        from urllib.parse import quote                         # noqa: PLC0415
        return base.rstrip("/") + "/" + quote(names[s])        # KeyError ⇒ لا تخمين

    d = surah_ends(idx)
    probe = [s for s in sorted(d, key=lambda x: -d[x]) if s != surah][:3]
    if not probe:
        return None
    try:
        bps = sum(size(url(s)) / (d[s] / 1000.0) for s in probe) / len(probe)
        actual = size(url(surah))
    except Exception as e:                                     # noqa: BLE001
        print(f"      ⚠️ تعذّر السبر: {e}")
        return None
    rs = []
    for rd in refs:
        if not rd.get(surah):
            continue
        common = [s for s in d if s in rd and d[s] > 0 and rd[s] > 0 and s != surah]
        if not common:
            continue
        sp = sum(d[s] for s in common) / sum(rd[s] for s in common)
        exp = rd[surah] * sp / 1000.0 * bps
        if exp:
            rs.append(actual / exp)
    return statistics.median(rs) if rs else None


def measured_skip(idx, surah: int) -> int | None:
    """التخطّي = وسيطُ بدءِ الآية الأولى في **جارات** السورة عند القارئ نفسِه."""
    f = first_starts(idx)
    nb = [f[x] for x in (surah - 2, surah - 1, surah + 1, surah + 2) if f.get(x)]
    return int(statistics.median(nb)) if nb else None


def gh(*args) -> str:
    return subprocess.run(["gh", *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout


def inflight_reciters() -> set:
    """عناوينُ التشغيلات الجارية — و**قرّاءُ موجةِ `align.yml` الجارية بأسمائهم**.

    ⛔ **عطبٌ مقيسٌ 2026-09-13**: `align.yml` (موجةُ محاذاةٍ كاملةٍ متعدّدةِ
    القرّاء) يحمل عنوان تشغيلةٍ مثل «align reciters_partial6.tsv · shards=6»
    — **لا يحمل اسمَ قارئٍ واحد**. فحصُ `rid in t` القديم لا يرى فيه شيئاً،
    فكرّر هذا الملفُّ إطلاقَ `realign_surah` على `a_klb` و`a_binaoun` **وهما
    داخل تلك الموجة نفسِها فعلاً** — ثلاثُ تشغيلاتٍ ضاعت على حارسٍ يردّها حتماً
    («لا أثرَ صقل» في `stage_transform`: فهرسٌ من الجيل الأوّل لا يُصلحه ترقيعُ
    سورة، والمحاذاةُ الكاملةُ الجاريةُ هي العلاج الصحيح أصلاً). ⇒ يُقرأ مسارُ
    كلّ تشغيلةٍ أيضاً، وما كان `align.yml` تُستخرج منه قائمةُ الـtsv من العنوان
    وتُضاف أسماءُ قرّائها كلُّهم إلى المشغولين — لا عنوانُ التشغيلة وحده.
    """
    out = set()
    repo = os.environ.get("GITHUB_REPOSITORY", "mwqwf/rafiq-align-ci")
    for st in ("in_progress", "queued", "pending"):
        txt = gh("api", f"repos/{repo}/actions/runs?status={st}&per_page=100",
                 "-q", r'.workflow_runs[] | .path + "\t" + .display_title')
        for ln in txt.splitlines():
            ln = ln.strip()
            if not ln:
                continue
            path, _, title = ln.partition("\t")
            out.add(title)
            if not path.endswith("/align.yml"):
                continue
            m = re.match(r"align (\S+\.tsv)", title)
            if not m:
                continue
            tsv = ROOT / "tools" / "ci_fleet" / m.group(1)
            if not tsv.exists():
                continue
            for row in tsv.read_text(encoding="utf-8").splitlines():
                row = row.strip()
                if not row or row.startswith("#"):
                    continue
                out.add(row.split("\t")[0].strip())
    return out


def latest_staged_indexes() -> dict[tuple[str, str], str]:
    """أحدثُ مرشّحِ مسرحٍ لكلّ قارئ.

    ⛔ حلقةٌ مقيسةٌ في الشوطين 35164079148 و35185281620: أصلح الشوطُ الأول
    `nufais/47` في المسرح (+38)، ثم عاد `scan` إلى الفهرس المنشور نفسه فأطلق
    **السورة 47 ذاتها** ثانيةً، لأنّه لم يرَ المرشّح المرحلي قط. والأسوأ أنّ
    إطلاق السورة 46 لاحقاً من المنشور كان سيُسقط إصلاح 47، فتتبادل السورتان
    إلى ما لا نهاية. لذلك تكون الزيادةُ المرحليةُ أباً للدورة التالية، ولا
    يصير ذلك نشراً أو قبولاً: بوابةُ `gate` وحارسُ `promote.py` باقيان كما هما.
    """
    cl, b = s3()
    newest = {}
    newest_mtime = {}
    for pg in cl.get_paginator("list_objects_v2").paginate(
            Bucket=b, Prefix="timings-staging/"):
        for o in pg.get("Contents", []):
            k = o["Key"]
            if not k.endswith(".jz") or "/tmp/" in k or "/timings/" in k:
                continue
            p = k.split("/")
            if len(p) < 3:
                continue
            who = (p[1], p[2].split(".")[0])
            mt = o.get("LastModified", 0)
            if who not in newest or mt > newest_mtime[who]:
                newest[who] = k
                newest_mtime[who] = mt
    return newest


def effective_indexes():
    """الفهارس المنشورة، مع تسلسل أحدث زيادةٍ مرحليةٍ فوق أصلها المنشور."""
    staged = latest_staged_indexes()
    out = []
    for row in list_indexes():
        live_key = row["key"]
        try:
            live_idx, _ = fetch_index(live_key)
        except Exception:                                      # noqa: BLE001
            continue
        p = live_key.split("/")
        who = (p[1], p[2][:-3])
        key, idx = live_key, live_idx
        staged_key = staged.get(who)
        if staged_key:
            try:
                staged_idx, _ = fetch_index(staged_key)
            except Exception:                                  # noqa: BLE001
                staged_idx = None
            # لا يُسلسل تجميلاً أو مرشحاً ناقصاً: الزيادة المقيسة وحدها.
            if staged_idx and len(staged_idx.get("entries", [])) > len(live_idx.get("entries", [])):
                key, idx = staged_key, staged_idx
        out.append({"key": key, "liveKey": live_key, "index": idx})
    return out


def candidates():
    """السورُ التي يُرجى استرجاعُها، الأكثرُ آياتٍ أوّلاً.

    يبدأ القياسُ من أحدث زيادةٍ مرحليةٍ، لا من المنشور القديم، كي تتراكم
    إصلاحاتُ السور ولا تُعاد أو يُسقط بعضُها بعضاً قبل البوابة النهائية.
    """
    rows = []
    for r in effective_indexes():
        k, idx = r["key"], r["index"]
        riw, rid = k.split("/")[1], k.split("/")[2][:-3]
        rid = rid.split(".")[0]
        try:
            counts = SURAH_AYAHS_OF(idx)
        except SystemExit as e:
            # لا نحوّل عدّ روايةٍ إلى كوفيّ تخميناً، ولا نُسقط جردَ القرّاء
            # الآخرين بسبب فهرسٍ واحد. يُغلق هذا الفهرس وحده ويظل صوته كما هو.
            print(f"   ⛔ {k}: يُترك من جرد الاسترجاع — {e}", file=sys.stderr)
            continue
        per = {}
        for e in idx["entries"]:
            s = int(e["ayahId"].split(":")[0])
            per[s] = per.get(s, 0) + 1
        for s in range(1, 115):
            have, exp = per.get(s, 0), counts[s - 1]
            gap = exp - have
            if needs_restore(have, exp):
                rows.append({"riwaya": riw, "reciter": rid, "surah": s,
                             "have": have, "expected": exp, "gap": gap,
                             "key": k, "liveKey": r["liveKey"]})
    rows.sort(key=lambda x: -x["gap"])
    return rows


# ───────────────────────── scan: يقيس ثمّ يُطلق المحاذاة ─────────────────────────
def cmd_scan(a):
    bases = catalog_bases()
    tables = catalog_file_tables()
    refs = []
    for k in REFS:
        try:
            refs.append(surah_ends(fetch_index(k)[0]))
        except Exception as e:                                 # noqa: BLE001
            print(f"⚠️ مرجعٌ متعذّر {k}: {e}")
    if len(refs) < 2:
        raise SystemExit("⛔ أقلُّ من مرجعين — والحكمُ بمرجعٍ واحدٍ يُضلّ. لا عمل.")
    busy = inflight_reciters()
    rows = candidates()
    print(f"مرشَّحون: {len(rows)} · مجموعُ الآيات المرجوّة: {sum(r['gap'] for r in rows)}")
    done = 0
    for r in rows:
        if done >= a.limit:
            break
        rid, riw, s = r["reciter"], r["riwaya"], r["surah"]
        if any(rid in t for t in busy):
            print(f"   ⏭️ {rid} س{s}: في الطيران — يُترك")
            continue
        base = source_base(bases, riw, rid, s)
        if not base:
            print(f"   ⛔ {rid}: لا مصدرَ في الكتالوج")
            continue
        if blocked_realign(riw, rid, s, base):
            print(f"   ⏭️ {rid} س{s}: المحاولةُ نفسها انتهت بلا مرشّح — "
                  "لا تُعاد بلا مصدرٍ أو محرّكٍ جديد موثّق")
            continue
        if (riw, rid, s) in SOURCE_OVERRIDES:
            print(f"   🔁 {rid} س{s}: مصدرٌ بديلٌ مقاس؛ المصدرُ المسجّل مبتور")
        idx, _ = fetch_index(r["key"])
        # ⛔⛔ **فهرسُ الجيل الأوّل لا يُصلحه ترقيعُ سورة** — قاعدةُ `CLAUDE.md` نصّاً،
        #    و`stage_transform` يردّه **حتماً** بـ«الفهرس بلا أثر صقلٍ في ترويسته —
        #    مجهول الجيل فلا يُرقّى». ⇒ فكلُّ تشغيلةٍ تُطلق عليه **ضائعةٌ يقيناً**.
        # 🔥 **وثمنُه دُفع ليلةَ 2026-09-14** (مقيس): `a_klb` س2 أُطلقت ثلاثَ مرّات
        #    (‏20:26 · 21:30 · 22:58) وسقطت الثلاثُ عند الحارس نفسِه بعد **29 دقيقةً**
        #    من محاذاةٍ **نجحت** (‏«+147 مدخلاً») ثمّ رُميت.
        # ⛔ **وعلاجُ 2026-09-13 عالج العَرَض لا السبب**: وُسّع كشفُ «في الطيران» ليشمل
        #    موجةَ `align.yml` — فسكت العطبُ ما دامت الموجةُ جارية، **وعاد حين انتهت**.
        #    والسببُ أنّ شيئاً لم يكن يسأل عن جيل الأب قبل الإطلاق. وهذا يسأل.
        # ✅ ولا حارسَ يُعطَّل ولا عتبةَ تُخفَّض: هذا **يمنع** إطلاقاً عابثاً ولا يقبل شيئاً.
        if not (idx.get("refineVersion") or idx.get("refinedCount")):
            print(f"      ⛔ {rid}: فهرسٌ من الجيل الأوّل (لا أثرَ صقلٍ في الترويسة) — "
                  f"يردّه الحارسُ حتماً. **العلاجُ محاذاةٌ كاملةٌ لا ترقيعُ سورة.**")
            continue
        # جدولُ files يُحلّ به رابطُ السورة — إلا لمصدرٍ بديلٍ مقاس (قالبٌ رقميّ).
        names = None
        if (riw, rid, s) not in SOURCE_OVERRIDES and (riw, rid) in tables:
            names = tables[(riw, rid)]
            if names is None:
                print(f"   ⛔ {rid}: جدولُ files في الكتالوج ليس 114 — لا قياسَ ولا تخمين")
                continue
        ratio = source_ratio(idx, base, s, refs, names)
        skip = measured_skip(idx, s)
        if ratio is None or skip is None:
            print(f"   ⚠️ {rid} س{s}: قياسٌ ناقص (نسبة={ratio} تخطٍّ={skip}) — يُترك")
            continue
        tag = "سليم" if ratio >= SOUND else "مبتور"
        print(f"   {rid:16s} س{s:<4d} {r['have']}/{r['expected']} · نسبةُ المصدر {ratio:.2f} ({tag}) · تخطٍّ {skip}م.ث")
        if ratio < SOUND:
            print("      ⇒ مبتورٌ عند الناشر — لا تُنفَق عليه محاذاة.")
            continue
        reason = (f"استرجاعُ سورة {s}: الفهرسُ {r['have']} من {r['expected']} مدخلاً، "
                  f"ونسبةُ حجمِ المصدر إلى المتوقَّع {ratio:.2f} بوسيطِ {len(refs)} مراجعَ "
                  f"⇒ المصدرُ حاضرٌ والنقصُ في محاذاتنا. والتخطّي {skip}م.ث وسيطُ بدءِ "
                  f"الآية الأولى في جارات السورة عند هذا القارئ نفسِه.")
        call = ["workflow", "run", "realign_surah.yml",
                "--repo", os.environ.get("GITHUB_REPOSITORY", "mwqwf/rafiq-align-ci")]
        # تشغيلُ فرعٍ تجريبي يجب أن يستهلك حارسه هو، لا نسخة main القديمة.
        # وعلى main تكون القيمة main نفسها فلا يتغيّر مسار الإنتاج.
        if os.environ.get("GITHUB_REF_NAME"):
            call += ["--ref", os.environ["GITHUB_REF_NAME"]]
        call += ["-f", f"parent={r['key']}", "-f", f"surahs={s}",
                 "-f", f"skip_ms={skip}", "-f", f"url_template={realign_template(base, names)}",
                 "-f", f"reciter_id={rid}", "-f", f"riwaya={riw}", "-f", f"reason={reason}"]
        out = gh(*call)
        print(f"      ▶ أُطلقت إعادةُ المحاذاة {out.strip()}")
        done += 1
    print(f"⇒ أُطلق {done}")


# ───────────────────────── gate: يُبوّب المحسَّنين ─────────────────────────
PARTIAL_RE = re.compile(r"\.partial\d+\.")


def is_partial(key: str) -> bool:
    """أفهرسٌ جزئيٌّ هو؟ (‏`<قارئ>.partial113.<بصمة>.jz`)

    ⛔ **العطبُ الذي وُلدت منه هذه الدالّة — مقيسٌ 2026-09-22:** شوطُ CTC الذي
    يتعثّر في سورةٍ أو أكثر يرفع فهرساً باسمٍ فيه `partialNNN`، **ومداخلُه قد
    تفوق المنشورَ** رغم نقص سوره. فكان `_staged_improvements` يختاره لأنّه
    **الأحدث**، فيقع ضرران مقيسان:
      ١) **هدرٌ**: خمسُ تشغيلاتِ بوّابةٍ (مطالعٌ وأربعةُ ملوح) تُنفق على فهرسٍ
         **يردّه `promote` يقيناً** بشرط 114/114 (وقع على sahood.partial113).
      ٢) **وأخطرُ منه حجبٌ**: الجزئيُّ **يُظلّل** المرشّحَ الكاملَ للقارئ نفسِه
         لأنّ الأحدثَ وحدَه يُؤخذ ⇒ فهرسٌ تامٌّ جاهزٌ لا يُبوَّب ولا يُرقّى.
    ⚖️ وهذا **تشديدٌ لا تخفيف**: لا يُجيز شيئاً، ولا يمسّ عتبةً ولا حكماً —
    يمنع إنفاقاً على ما لا يُقبل، ويُبقي البابَ للكامل وحدَه.
    """
    return bool(PARTIAL_RE.search(key.rsplit("/", 1)[-1]))


def _staged_improvements():
    """بصماتُ مسرحٍ لقارئٍ **منشور** مداخلُها أكثرُ من المنشور — **كلُّها** لا أكبرُها.

    تُرجع لكلّ قارئٍ كلَّ مرشّحيه المحسَّنين مرتّبين بالزيادة تنازلياً (‏والأحدثُ
    عند التساوي)، والقرّاءُ مرتّبون بأكبر زيادة. واختيارُ واحدٍ للقارئ في الجولة
    شأنُ `gate_picks` و`promote_groups` لا شأنُ هذه الدالّة.

    ⛔ **العطبُ الذي غيّرها — مقيسٌ 2026-09-25** (‏`ops/out/0835b_gate.txt`
    و`0835c_promote.txt`): كانت تُبقي للقارئ **أكبرَ مرشّحٍ وحده**. فمرشّحٌ قديمٌ
    زيادتُه أكبر لأنّه يضمّ سوراً مبتورةً في المصدر (‏`akri_qalun.8b9fea7c`)
    استوفى ملوحَه، ويردّه `promote.py` بحارس البتر في كلّ جولة، **ويُظلّل** مرشّحاً
    أحدثَ سليماً أصغرَ زيادةً (‏`akri_qalun.655f19d5` +33): فلا تُبوّبه `gate`
    (‏لأنّ المختارَ مستوفي الملوح) ولا تُرقّيه `promote` (‏لأنّها لا تراه). وقع
    لخمسة قرّاء: akri_qalun · nufais · mohna · nasser_almajed · mukhtar_haj.
    ⚖️ لا يمسّ حارساً: كلُّ مرشّحٍ يمرّ بالبوّابة والملوح الأربعة و`promote.py`
    كما كان، وحارسُ الانكماش فيه يمنع الأصغرَ من النزول فوق أكبرَ منشور.

    ⛔ والجزئيُّ (`partialNNN`) يُستبعد هنا: يُنفق البوّابةَ ويُظلّل الكامل."""
    cl, b = s3()
    live, staged, lmt = {}, [], {}
    for pg in cl.get_paginator("list_objects_v2").paginate(Bucket=b, Prefix="timings/"):
        for o in pg.get("Contents", []):
            k = o["Key"]
            if k.endswith(".jz") and k.count("/") == 2:
                live[(k.split("/")[1], k.split("/")[2][:-3])] = k
                lmt[k] = o["LastModified"]
    mt = {}
    for pg in cl.get_paginator("list_objects_v2").paginate(Bucket=b, Prefix="timings-staging/"):
        for o in pg.get("Contents", []):
            if (o["Key"].endswith(".jz") and "/timings/" not in o["Key"]
                    and not is_partial(o["Key"])):
                staged.append(o["Key"]); mt[o["Key"]] = o["LastModified"]
    # ⛔ **كلُّ مرشّحي القارئ لا أحدثُهم وحده** (مقيسٌ 2026-09-22): محاذاةُ سورةٍ
    #    واحدةٍ من الحلقة تُرفع بعد محاذاة CTC الكاملة فتصير «الأحدث» وهي أقلُّ مداخلَ،
    #    فتُظلّل البصمةَ الكاملة (khalf +26 · soufi +25 نجتا بنيويّاً ولم تُبوَّبا).
    #    ⇒ يُختار **أكبرُ المرشّحين زيادةً** (والأحدثُ عند التساوي). ولا يمسّ هذا حارساً:
    #    المختارُ يمرّ بالبوّابة والملوح الأربعة و`promote.py` كاملةً كما كان.
    cands = {}
    for k in staged:
        p = k.split("/")
        if len(p) < 3:
            continue
        who = (p[1], p[2].split(".")[0])
        # ⚡ ما رُفع قبل المنشور لا يُحمَّل: الترقيةُ تُحدِّث المنشور، فالأقدمُ منه
        #    إمّا رُقّي أو سُبق — وتحميلُ المسرح كلِّه أبطأَ الجسرَ ساعةً (مقيسٌ).
        if who in live and mt[k] > lmt[live[who]]:
            cands.setdefault(who, []).append(k)
    out = []
    for who, ks in cands.items():
        try:
            o, _ = fetch_index(live[who])
        except Exception:                                      # noqa: BLE001
            continue
        mine = []
        for k in sorted(ks, key=lambda x: mt[x], reverse=True):
            try:
                n, _ = fetch_index(k)
            except Exception:                                  # noqa: BLE001
                continue
            g = len(n["entries"]) - len(o["entries"])
            if g > 0:
                mine.append({"key": k, "live": live[who], "gain": g,
                             "riwaya": who[0], "reciter": who[1]})
        # الترتيبُ مستقرّ: الأحدثُ أوّلاً عند تساوي الزيادة كما كان.
        mine.sort(key=lambda x: -x["gain"])
        out.extend(mine)
    return _grouped_by_best(out)


def _who(r) -> tuple:
    """هويّةُ القارئ من سطر مرشّح (‏الرواية والقارئ؛ ويُشتقّان من المفتاح إن غابا)."""
    p = r["key"].split("/")
    return (r.get("riwaya") or (p[1] if len(p) > 2 else ""),
            r.get("reciter") or p[-1].split(".")[0])


def _grouped_by_best(rows) -> list:
    """يرتّب المرشّحين: القرّاءُ بأكبر زيادةٍ لكلٍّ منهم، ومرشّحو القارئ متجاورون
    بالزيادة تنازلياً. الترتيبُ مستقرّ فلا يتبدّل ما تساوى."""
    top = {}
    for r in rows:
        w = _who(r)
        top[w] = max(top.get(w, r["gain"]), r["gain"])
    first = {}
    for i, r in enumerate(rows):
        first.setdefault(_who(r), i)
    return sorted(rows, key=lambda r: (-top[_who(r)], first[_who(r)], -r["gain"]))


def promote_groups(imp, salt_count) -> list[list[dict]]:
    """مرشّحو الترقية مجموعين بالقارئ: كلُّ مجموعةٍ ما استوفى ملوحَه الأربعة
    مرتّباً بالزيادة تنازلياً، والمجموعاتُ بأكبر زيادة. يُجرَّب الأوّلُ فإن ردّه
    الحارسُ جُرّب التالي، ولا يُرقّى للقارئ أكثرُ من واحد في الجولة."""
    groups: dict = {}
    for r in _grouped_by_best(imp):
        if salt_count(r["key"]) >= 4:
            groups.setdefault(_who(r), []).append(r)
    return list(groups.values())


_AUDIO_KEYS: list | None = None


def _salt_count(key: str) -> int:
    # ⚡ **سردُ `state/` مرّةً في العمليّة لا مرّةً لكلّ مرشّح** (مقيسٌ 2026-09-25:
    #    تجاوزت جولةُ الترقية سقفَ الثلاثين دقيقة مع تكاثر المرشّحين، وكلُّ مرشّحٍ
    #    كان يسرد الدلوَ كلَّه من جديد). والعدُّ نفسُه لا يتغيّر: الملوحُ تُكتب
    #    في شوطٍ آخر، فما لم يُرَ في هذه الجولة يُرى في التالية.
    global _AUDIO_KEYS
    if _AUDIO_KEYS is None:
        cl, b = s3()
        _AUDIO_KEYS = [o["Key"]
                       for pg in cl.get_paginator("list_objects_v2").paginate(
                           Bucket=b, Prefix="state/")
                       for o in pg.get("Contents", []) if "audio-" in o["Key"]]
    stem = key.replace("/", "_").replace(".jz", "")
    return sum(1 for k in _AUDIO_KEYS if stem in k)


def _struct_fatal(key: str):
    """فحصٌ بنيويٌّ مجّانيٌّ قبل إنفاق أيّ ملحٍ صوتيّ (CLAUDE.md: «لا تُطلق ملحاً
    قبل الفحص البنيويّ»). ⛔ هذه القاعدةُ نفسُها في `promote.sampling_skip_reason`
    وكانت غائبةً عن هذا الراصد بعينِه — فكان يُبوِّب `iraoui_warsh` (بصمةٌ مكرّرة:
    تنزيلٌ مغشوش) و`nufais` (سورةٌ غائبة) لخمسِ تشغيلاتٍ صوتيّةٍ يردّهما الحارسُ
    فيها مجّاناً لو سُئل أوّلاً. تُرجع نصَّ العطب أو `None` إن سلم أو تعذّر القياسُ
    نفسُه (‏فلا يُمنع مرشَّحٌ بعطبٍ في أداة الفحص لا في فهرسه)."""
    import types
    try:
        rep = _run_audit(key, types.SimpleNamespace(struct_only=True))
    except Exception:                                          # noqa: BLE001
        return None
    return " · ".join(rep.get("fatal") or []) or None


CENSUS_PREFIX = "state-census/"


def needs_census(idx: dict, sha: str, census_rep: dict | None) -> bool:
    """أيلزم هذا الفهرسَ إحصاءٌ شاملٌ **لم يُجرَ بعدُ على بصمته**؟

    الشرطُ صارمٌ في الاتجاهين، ومرآةٌ لتخطّي `splice_census.yml` نفسِه:
      · تحويلُه دمجٌ من `promote.SPLICE_OPS` **و**في ترويسته سورٌ بمحرّكٍ آخر؛
      · **ولا** ملفَّ إحصاءٍ على البصمة نفسِها (‏غائبٌ أو على بصمةٍ أخرى).
    ⇒ لا إحصاءَ لما لا دمجَ فيه، ولا إحصاءَ مكرّراً لما أُحصي على بصمته.
    ⚖️ لا يحكم بشيء: `census_gate` في `promote.py` يبقى الحَكَم كما هو."""
    from promote import splice_op_name
    tr = idx.get("transform")
    op = str((tr or {}).get("op") or "") if isinstance(tr, dict) else str(tr or "")
    if not splice_op_name(op):
        return False
    ebs = {k for k, v in (idx.get("engineBySurah") or {}).items()
           if v and v != idx.get("engineVersion")}
    if not ebs:
        return False
    return not (isinstance(census_rep, dict) and census_rep.get("sha256") == sha)


def _census_due(key: str) -> bool:
    """`needs_census` مقروءاً من الدلو. تعذّرُ قراءة الفهرس ⇒ لا إطلاق (‏لا يُنفَق
    على ما لم يُقرأ)؛ وغيابُ ملفّ الإحصاء ⇒ يلزم."""
    try:
        idx, sha = fetch_index(key)
    except Exception:                                          # noqa: BLE001
        return False
    cl, b = s3()
    try:
        rep = json.loads(cl.get_object(
            Bucket=b, Key=CENSUS_PREFIX + key.replace("/", "_") + ".json")["Body"].read())
    except Exception:                                          # noqa: BLE001
        rep = None
    return needs_census(idx, sha, rep)


def census_keys(improvements, batch, busy, salt_count, due) -> list[str]:
    """مفاتيحُ يُطلق لها `splice_census.yml` في هذه الجولة.

    ⛔ **العطبُ الذي وُلدت منه — مقيسٌ 2026-09-24** (‏`ops/out/2135d_promote.txt`):
    كان الإحصاءُ يُطلق **مع الدفعة وحدها**، والدفعةُ مَن نقصت ملوحُه عن أربعة.
    فمرشّحٌ استوفى ملوحَه الأربعة **قبل** أن يُضاف الإحصاءُ إلى البوّابة
    (‏`a_alhazmi.6e289031`) لا يدخل الدفعةَ أبداً ⇒ لا يُحصى أبداً ⇒ يردّه
    `census_gate` في كلّ جولةٍ إلى الأبد. ⇒ يُنظر في **كلّ** محسَّن: ما في
    الدفعة، وما اكتملت ملوحُه؛ لا ما ينتظر دورَه في دفعةٍ لاحقة (‏يُحصى معها)
    ولا ما يُحاذى الآن. ثمّ لا يبقى إلا ما يلزمه إحصاءٌ على بصمته (`due`)."""
    busy_s = "".join(busy)
    out = []
    for r in improvements:
        k = r["key"]
        if k in out or k in busy_s:
            continue
        if k in batch or salt_count(k) >= 4:
            if due(k):
                out.append(k)
    return out


def gate_picks(imp, salts, busy_s, struct_fatal):
    """مَن يُبوَّب في هذه الجولة: **واحدٌ لكلّ قارئ** على الأكثر، هو أكبرُ مرشّحيه
    زيادةً ممّن نقصت ملوحُه عن أربعة ولا يُحاذى الآن ونجا من الفحص البنيويّ.
    ⛔ لا يُفحص بنيويّاً ولا يُبوَّب ما استوفى ملوحَه، ولا يُطلق للقارئ بوّابتان.
    تُرجع (‏المختارين بترتيب الزيادة · المردودين بنيويّاً مع علّتهم)."""
    picks, bad_rows, done = [], [], set()
    for r in _grouped_by_best(imp):
        w = _who(r)
        if w in done or salts.get(r["key"], 0) >= 4 or r["key"] in busy_s:
            continue
        bad = struct_fatal(r["key"])
        if bad:
            bad_rows.append((r, bad))
            continue
        picks.append(r)
        done.add(w)
    picks.sort(key=lambda x: -x["gain"])
    return picks, bad_rows


def cmd_gate(a):
    repo = os.environ.get("GITHUB_REPOSITORY", "mwqwf/rafiq-align-ci")
    busy = inflight_reciters()
    imp = _staged_improvements()
    salts = {r["key"]: _salt_count(r["key"]) for r in imp}
    busy_s = "".join(busy)
    # ⭐ **بوّابةٌ واحدةٌ للقارئ**: أكبرُ مرشّحيه لم تكتمل ملوحُه ونجا بنيويّاً —
    #    ولو ظلّله مرشّحٌ أكبرُ مُحكَم (‏يُردّ بحارس البتر مثلاً). انظر `gate_picks`.
    todo, struct_bad = gate_picks(imp, salts, busy_s, _struct_fatal)
    for r, bad in struct_bad:
        print(f"   ⛔ {r['reciter']}: رُدّ بنيوياً قبل إنفاق ملحٍ — {bad}")
    print(f"محسَّنون بلا حكمٍ كافٍ: {len(todo)}")
    batch = [r["key"] for r in todo[:a.limit]]
    # ⭐ الإحصاءُ الشاملُ يُحسب قبل الخروج: مرشّحٌ اكتملت ملوحُه لا يُبوَّب
    #    لكنّه قد يكون محبوساً بغياب إحصائه وحده (‏انظر `census_keys`).
    cen = census_keys(imp, batch, busy, lambda k: salts.get(k, 0), _census_due)
    if cen:
        gh("workflow", "run", "splice_census.yml", "--repo", repo, "-f",
           f"only={','.join(cen)}")
        print(f"⇒ أُطلق الإحصاءُ الشامل لـ{len(cen)}: {', '.join(cen)}")
    if not batch:
        print("لا شيء يُبوَّب."); return
    keys = ",".join(batch)
    for r in todo[:a.limit]:
        print(f"   {r['reciter']:16s} +{r['gain']} مدخلاً")
    gh("workflow", "run", "openers.yml", "--repo", repo, "-f", f"only={keys}",
       "-f", f"limit={len(batch)}")
    for salt in ("rs1", "rs2", "rs3", "rs4"):
        gh("workflow", "run", "audio_qa.yml", "--repo", repo, "-f", f"only={keys}",
           "-f", f"limit={len(batch)}", "-f", f"seed_salt={salt}")
    # ⭐ المدموجُ بمحرّكين يلزمه إحصاءٌ شاملٌ فوق الملوح (‏حارسُ `census_gate`)؛
    #    وقد أُطلق أعلاه لما يلزمه وحدَه من الدفعة ومن مكتملي الملوح.
    print(f"⇒ بُوِّب {len(batch)} بخمس تشغيلات (‏مطالعُ وأربعةُ ملوح)")


# ───────────────────────── promote: يرقّي ما مرّ ─────────────────────────
DIAG_STALE = "تشخيص الكتالوج يصف فهرساً آخر"
# أحكامٌ نهائيّةٌ على المرشّح نفسِه — وحدَها تُجيز تجربةَ مرشّحٍ أصغرَ للقارئ نفسِه.
FINAL_REJECTIONS = ("مبتورةٌ في المصدر", "عطبٌ جسيم", "خلل بنيوي")


def final_rejection(out: str) -> bool:
    """أردّ الحارسُ المرشّحَ ردّاً نهائيّاً لا يزول بانتظار؟ — ما لم يُسمَّ هنا عابر."""
    return any(m in (out or "") for m in FINAL_REJECTIONS)


def maybe_diagnose(key: str, out: str, fired: set) -> bool:
    """يُطلق `diagnosis.yml` لقارئ المفتاح إن ردّته الترقيةُ (‏تجريبيّةً أو فعليّة)
    بـ«تشخيص الكتالوج يصف فهرساً آخر»، **مرّةً واحدةً للقارئ في الجولة**.

    ⛔ **العطبُ الذي وُلدت منه — مقيسٌ 2026-09-24** (‏`ops/out/2135d_promote.txt`
    السطر 19): الإطلاقُ كان في فرع «⛔ لم يُرقَّ» وحده، أي بعد تجربة الترقية
    الفعليّة. و`lhdan` تردّه التجربةُ الجافّةُ نفسُها بهذا السبب فيسقط في فرع
    «⏸️ لم يمرّ بعدُ» ⇒ لا يُطلق له التشخيصُ أبداً ⇒ محبوسٌ إلى الأبد.
    ⚖️ لا يمسّ حكماً: التشخيصُ الجديد يُقرأ في الجولة التالية بحارس `promote.py` نفسِه."""
    if DIAG_STALE not in (out or ""):
        return False
    riw, rid = key.split("/")[1], key.split("/")[2].split(".")[0]
    who = f"{riw}/{rid}"
    if who in fired:
        return False
    fired.add(who)
    repo = os.environ.get("GITHUB_REPOSITORY", "mwqwf/rafiq-align-ci")
    gh("workflow", "run", "diagnosis.yml", "--repo", repo, "-f", f"only={who}")
    print(f"      ↻ أُطلق diagnosis.yml لـ{who} — يُرقّى في الجولة التالية")
    return True


PROMOTE_BUDGET_S = int(os.environ.get("PROMOTE_BUDGET_S", "1200"))


def cmd_promote(a):
    prom = str(ROOT / "tools" / "index_qa" / "promote.py")
    fired: set = set()
    # ⛔ **مهلةُ الجولة** (مقيسٌ 2026-09-25): جولةٌ أطولُ من سقف الوظيفة (30 د)
    #    تُقتل قبل أن تُطبع نتيجةٌ واحدة، فيضيع ما رُقّي وما رُدّ ويُحجز الطابور.
    #    ⇒ لا يُبدأ مرشّحٌ جديدٌ بعد نفاد المهلة، ويُسمّى المؤجَّلون صراحةً
    #    ليُفحصوا في الجولة التالية. ⚖️ لا يُمسّ حارس: المرشّحُ الذي بدأ يُكمل
    #    فحصَه وترقيتَه وسدَّه كما كان، والمؤجَّلُ لا يُرقّى ولا يُرفض.
    t0 = time.monotonic()
    # ⭐ **مرشّحو القارئ كلُّهم بالترتيب** (‏مقيسٌ 2026-09-25، انظر `_staged_improvements`):
    #    يُجرَّب الأكبرُ زيادةً، فإن ردّه الحارسُ جُرّب التالي المستوفي ملوحَه، وتقف
    #    المجموعةُ عند أوّل ترقيةٍ ناجحة ⇒ لا يُرقّى للقارئ أكثرُ من مرشّحٍ في الجولة.
    #    ⚖️ كلُّ محاولةٍ تمرّ بـ`promote.py` كاملاً، وحارسُ الانكماش فيه يمنع
    #    الأصغرَ من النزول فوق أكبرَ منشور.
    groups = promote_groups(_staged_improvements(), _salt_count)
    for gi, grp in enumerate(groups):
        for ci, r in enumerate(grp):
            if time.monotonic() - t0 > PROMOTE_BUDGET_S:
                rest = [x[0]["reciter"] for x in groups[gi:]]
                print(f"   ⏳ نفدت مهلةُ الجولة ({PROMOTE_BUDGET_S}ث) — أُجّل {len(rest)} "
                      f"إلى الجولة التالية: {', '.join(rest)}")
                return
            ok, out = _try_promote(r, prom, fired)
            if ok:
                break
            # ⏳ «تشخيص الكتالوج يصف فهرساً آخر» علّةٌ عابرةٌ يُصلحها تشخيصٌ أُطلق
            #    للتوّ: لا يُنزل إلى الأصغر فيُسبَق به الأكبرُ السليمُ المنتظِر.
            if DIAG_STALE in (out or ""):
                break
            # ⛔ ولا يُنزل إلا على **ردٍّ نهائيّ** يُسمّى نصّاً: فغيابُ مطالعَ أو إحصاءٍ
            #    لم يُكتب بعدُ علّةٌ عابرة، والنزولُ فيها يرقّي الأصغرَ فيصير الأكبرُ
            #    السليمُ أقدمَ من المنشور ويسقط من النظر إلى الأبد (‏آياتٌ تضيع بلا حكم).
            if not final_rejection(out):
                break
            if ci + 1 < len(grp):
                print(f"      ↓ يُجرَّب مرشّحُه التالي: {grp[ci + 1]['key'].split('/')[-1]}"
                      f" (+{grp[ci + 1]['gain']})")


def _try_promote(r, prom, fired) -> tuple[bool, str]:
    """محاولةُ ترقيةِ مرشّحٍ واحد بحرّاس `promote.py` كاملة. تُرجع (‏رُقّي؟ · المخرج)."""
    dry = subprocess.run([sys.executable, prom, "--only", r["key"]],
                         capture_output=True, text=True, encoding="utf-8",
                         errors="replace", cwd=str(ROOT))
    tail = "\n".join(l for l in dry.stdout.splitlines() if "🔇" not in l)[-400:]
    # ⛔ **عطبٌ مقيسٌ 2026-09-13**: هذا الفحصُ الأوّل لا يُمرِّر `--unfreeze`
    #    أبداً، فهدفٌ مجمَّدٌ يردّه `gate()` بـ«الهدف مجمَّد» **قبل** أن
    #    يصل إلى طباعة «✅ جاهز» مهما صحّ حكمُه الصوتيُّ والبنيويُّ تماماً —
    #    فلا يُرفع التجميدُ عن أيّ مرشَّحٍ أبداً ولو استوفى كلَّ شرط. وقع
    #    فعلاً على `yahya`/`twfeeq`/`h_aldaghriri`/`kyat`/`darweez` بعد أن
    #    مرّت أحكامُها كلُّها: الحكمُ الصوتيُّ · البنيويُّ · فحصُ المطالع.
    #    والتجميدُ **آخرُ ما يفحصه `gate()`**، فبلوغُه دليلٌ أنّ كلَّ ما
    #    قبله صحّ — ⇒ يُحاوَل الرفعُ في هذه الحال أيضاً، **وحارسُ `--yes`
    #    نفسُه** (‏لا هذا الملفّ) هو مَن يحكم نهائيّاً بعد الرفع الفعليّ.
    ready = "✅ جاهز" in dry.stdout
    frozen_only = "الهدف مجمَّد" in dry.stdout
    if not ready and not frozen_only:
        print(f"   ⏸️ {r['reciter']}: لم يمرّ بعدُ — {tail.splitlines()[-1] if tail else ''}")
        maybe_diagnose(r["key"], dry.stdout, fired)
        return False, dry.stdout
    # ⛔ التجميدُ يُرفع **للحظةِ ترقيةٍ متحقَّقة** لا قبلها
    why = (f"استرجاعُ آياتٍ مفقودة: المرشَّحُ {r['key'].split('/')[-1]} يزيد "
           f"**{r['gain']} مدخلاً** على المنشور، وقد مرّ بحكمه الصوتيّ بأربعة ملوحٍ فأكثر.")
    subprocess.run([sys.executable, prom, "--unfreeze", r["live"], "--reason", why],
                   cwd=str(ROOT), text=True)
    done = subprocess.run([sys.executable, prom, "--only", r["key"], "--yes"],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=str(ROOT))
    ok = "→ ✅" in done.stdout
    # ⛔⛔ **يُسدّ ما رُفع إن رُدّت الترقية** (عطبٌ مقيسٌ 2026-09-23): رفعٌ بلا
    #    ترقيةٍ ناجحة ترك الهدفَ مفتوحاً، فرقّى `keepalive` فوقه نسخةً أقدم
    #    (رجع fateh_douri 6235⇒6209 وtrabulsi 6236⇒6214). ⇒ يُعاد التجميدُ على
    #    المنشور الحاليّ فوراً — تشديدٌ لا إرخاء، ولا يكتب في timings/.
    if not ok:
        subprocess.run([sys.executable, str(ROOT / "tools" / "ci_fleet" / "refreeze.py"),
                        r["live"], "", "سدٌّ بعد ترقيةٍ مردودة — يُغلق الرفعَ السابق"],
                       cwd=str(ROOT), text=True)
    print(f"   {'✅ رُقّي' if ok else '⛔ لم يُرقَّ'} {r['reciter']} (+{r['gain']})")
    for l in done.stdout.splitlines():
        if any(m in l for m in ("🧊", "⛔", "⏳", "🔴")):
            print("      " + l.strip()[:160])
    # ⭐ **تشخيصُ الكتالوج القديم يُجدَّد آليّاً** (‏قِيس 2026-09-24 أربعَ مرّات:
    #    darweez · a_alhazmi · mrifai · bader، ثمّ deban · husary_qalun): الترقيةُ
    #    تُردّ بـ«تشخيص الكتالوج يصف فهرساً آخر» فيبقى المرشّحُ ساعةً أو أكثر
    #    حتى يُطلق أحدٌ `diagnosis.yml` بيده. فيُطلق هنا، والحارسُ نفسُه لا يُمسّ:
    #    الترقيةُ تنتظر التشخيصَ الجديد في الجولة التالية كما كانت.
    if not ok:
        maybe_diagnose(r["key"], done.stdout, fired)
    return ok, done.stdout


def cmd_explain(a):
    """لماذا لا يظهر قارئٌ في مرشّحي الترقية؟ قراءةٌ فقط — لا يكتب ولا يُطلق.

    ⭐ (2026-09-25) مرّ إحصاءُ a_alhazmi بعد إصلاح نافذة D ثمّ غاب عن جولة
    الترقية كلّها بلا سطرٍ واحد، ومثلُه khan وsoufi_sousi وh_saleh. والمصفاةُ
    في `_staged_improvements` صامتةٌ عمّا تُسقطه، فهذا يطبع لكلّ بصمةٍ مسرحيّة
    زمنَها وزمنَ المنشور والزيادةَ، وعلّةَ الإسقاط إن سقطت."""
    cl, b = s3()
    live_key = f"timings/{a.who}.jz"
    try:
        live_mt = cl.head_object(Bucket=b, Key=live_key)["LastModified"]
    except Exception as ex:                                    # noqa: BLE001
        print(f"⛔ لا منشورَ في {live_key}: {ex}"); return
    o, _ = fetch_index(live_key)
    print(f"المنشور {live_key} · {live_mt:%Y-%m-%dT%H:%MZ} · مداخل {len(o['entries'])}")
    riw, rid = a.who.split("/")
    for pg in cl.get_paginator("list_objects_v2").paginate(
            Bucket=b, Prefix=f"timings-staging/{riw}/{rid}."):
        for ob in pg.get("Contents", []):
            k = ob["Key"]
            if not k.endswith(".jz"):
                continue
            why = []
            if is_partial(k):
                why.append("جزئيّ")
            if ob["LastModified"] <= live_mt:
                why.append("أقدمُ من المنشور")
            try:
                n, _ = fetch_index(k)
                g = len(n["entries"]) - len(o["entries"])
            except Exception as ex:                            # noqa: BLE001
                g = None; why.append(f"تعذّرت قراءتُه: {ex}")
            if g is not None and g <= 0:
                why.append("لا زيادة")
            print(f"  {k} · {ob['LastModified']:%Y-%m-%dT%H:%MZ} · زيادة {g} · "
                  f"ملوح {_salt_count(k)} · {'يُسقَط: ' + '، '.join(why) if why else 'مرشَّح'}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("scan");    p1.add_argument("--limit", type=int, default=3)
    p2 = sub.add_parser("gate");    p2.add_argument("--limit", type=int, default=6)
    sub.add_parser("promote")
    p4 = sub.add_parser("explain"); p4.add_argument("who", nargs="+", help="riwaya/reciter")
    a = ap.parse_args()
    if a.cmd == "explain":
        for w in a.who:
            cmd_explain(argparse.Namespace(who=w))
        return
    {"scan": cmd_scan, "gate": cmd_gate, "promote": cmd_promote}[a.cmd](a)


if __name__ == "__main__":
    main()
