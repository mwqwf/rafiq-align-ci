#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نواةُ برهانِ القارئ الجديد — **كاشفُ النسبة الخاطئة** يُحسب هنا لا يُوصف.

    python tools/index_qa/reciter_evidence.py --self-test
    python tools/index_qa/reciter_evidence.py --prove          # بتفريغاتٍ حقيقيةٍ من الدلو
    python tools/index_qa/reciter_evidence.py --assemble probe.json --riwaya warsh --out ev.json

## ⛔ العلّةُ التي أنشأت هذا الملفّ (‏مقيسةٌ 2026-09-07، جنديّ الفهرسة)

`add_surah_reciter.py` **يرفض إدخالَ قارئٍ بلا `--evidence`** بنصّه، وحارسُه
الثالث يقرأ من ذلك الملفّ حقلَي `scoreDeclared` و`scoreHafs`. **ولا مُنتِجَ
لهذين الحقلين في المستودعين** (‏قِيس: `grep -rn scoreHafs` خارج الأداة نفسِها =
صفر). ⇒ **ذراعُ «القرّاء الجدد» في الأمر الدائم كانت مسدودةً بأداةٍ ناقصةٍ
نصفَها**، لا بنقص مرشَّحين: جدولُ المسح فيه **خمسون** مرشَّحاً بروابطَ محقَّقة.

## ⛔⛔ ولماذا الطيُّ هنا **شرطُ صحّةٍ** لا تحسيناً

الحارسُ الثالث يردّ من طابق **نصَّ حفصٍ** أكثر من نصّ روايته المعلَنة. وتفريغُ
whisper يكتب بالرسم الإملائيّ الحديث (‏`الله`)، ونصُّ حفصٍ في أصولنا بألف الوصل
(‏`ٱللَّهِ`) وهي **16.4% من كلماته**، ونصُّ ورشٍ وقالون **صفر**. فالمطبِّعُ الحاليّ
`run.words` يمحو ألفَ الوصل قبل أن يطويها (‏`لله`) ⇒ **يعاقب مرجعَ حفصٍ وحدَه**:

⇒ تلاوةُ **حفصٍ** تسجّل درجةً أعلى على **مرجع ورشٍ** منها على مرجع حفص،
   فينقلب الكاشفُ **في الاتجاه الخطر بالضبط**: مصحفُ حفصٍ يُعلَن ورشاً فيمرّ.

وهذا مقيسٌ لا مظنون — `--prove` يعيد القياسَ على تفريغاتٍ حقيقيةٍ محفوظةٍ في
تقارير `audio_qa` على الدلو، ويطبع الجدول بالأسماء. والاختبارُ الذاتيّ (٥)
يثبّت الانقلابَ حالةً سالبةً كي لا يعود المطبِّعُ الساذج إلى هذا الموضع أبداً.

⛔ **ولا يمسّ هذا الملفُّ `run.words`** — حكمُ `audio_qa` يبقى بمسطرته التي
حُكم بها كلُّ مشهود (‏قرارُ 2026-09-07، مرفوعٌ للمشرف). الطيُّ **هنا وحدَه**،
حيث تُقابَل روايةٌ برواية.

## ما ينتجه CI وما يُحسب هنا

| الحقل | من أين | لماذا هناك |
|---|---|---|
| `files{}` (‏114 × `status`/`durationMs`) | CI: ‏114 `HEAD` + `Range` لرأس MP3 | ‏≈15 م.ب لكل مرشَّح — لا تُحمَّل شبكةُ المالك |
| `transcripts{}` (‏سورتا الشاهد) | CI: تنزيل + whisper | ثقيلٌ حسابياً |
| **`scoreDeclared`/`scoreHafs`/`conflict`** | **هنا — بصفرِ شبكة** | المرجعان على القرص، والطيُّ شرطُ صحّة |

فـ`--assemble` يأخذ مخرَجَ المسبار الخام ويكتب ملفَّ البرهان الذي يقبله
`add_surah_reciter.py`. **ولا تُخترع درجةٌ بلا تفريغ**: مسبارٌ بلا نصٍّ مسموع
يُردّ بنصّه.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:                                     # noqa: BLE001
        pass

TOOL = "reciter_evidence-1.0"
CONFLICT_MARGIN = 0.05      # فارقٌ دون هذا بين المرجعين ⇒ الشاهدان لا يحسمان


# ───────────────────────── المرجع والدرجة ─────────────────────────
def surah_text(riwaya: str, surah: int) -> str:
    """نصُّ السورة من أصول التطبيق — بصفرِ شبكة، وبعدّ حفصٍ الكوفيّ."""
    from run import ASSETS, COUNTS
    p = ASSETS / f"text_{riwaya}.jz"
    if not p.exists():
        raise SystemExit(f"⛔ لا أصلَ نصّيّ للرواية {riwaya} على القرص: {p}")
    txt = json.loads(gzip.decompress(p.read_bytes()).decode("utf-8"))
    if len(txt) != 6236:
        raise SystemExit(f"⛔ نصُّ {riwaya} = {len(txt)} لا 6236")
    if not (1 <= surah <= 114):
        raise SystemExit(f"⛔ سورةٌ خارج المدى: {surah}")
    start = sum(COUNTS[: surah - 1])
    return " ".join(txt[start: start + COUNTS[surah - 1]])


def score(heard: str, ref: str, fold: bool = True) -> float:
    """نسبةُ كلمات المرجع التي سُمعت — تقاطعُ مجموعتين متعدّدتين.

    ⛔ **بلا ترتيب** عمداً: التفريغُ يُدغم ويقدّم ويؤخّر، والمطلوب هنا
    **هويّةُ النصّ** لا دقّةُ الحدود (‏تلك حكمُ `audio_qa`). والقسمةُ على
    المرجع لا على المسموع، فإطالةُ التفريغ لا ترفع الدرجة.
    """
    if fold:
        from normalizer_audit import words_folded as W
    else:
        from run import words as W
    r = collections.Counter(W(ref))
    if not r:
        return 0.0
    h = collections.Counter(W(heard))
    return sum((r & h).values()) / sum(r.values())


def witness(heard: str, surah: int, riwaya: str, fold: bool = True) -> dict:
    """صفُّ شاهدٍ كما يقرؤه الحارسُ الثالث في `add_surah_reciter.py`."""
    own = score(heard, surah_text(riwaya, surah), fold)
    hafs = score(heard, surah_text("hafs", surah), fold)
    return {"surah": surah, "scoreDeclared": round(own, 4),
            "scoreHafs": round(hafs, 4),
            "conflict": abs(own - hafs) < CONFLICT_MARGIN,
            "normalizer": "folded" if fold else "run.words"}


# ───────────────────────── مدّةٌ لكل حرف (‏حارسُ البتر) ─────────────────────────
_LETTER = re.compile(r"[ء-يٱ]")


def letters(riwaya: str, surah: int) -> int:
    """حروفُ السورة بلا حركةٍ ولا فراغ — مقامُ حارس الخامس، ويُحسب محلّيّاً."""
    return len(_LETTER.findall(surah_text(riwaya, surah)))


def per_letter(duration_ms: float, riwaya: str, surah: int) -> float:
    """**ثانيةٌ لكل حرف** — والوحدةُ مقيسةٌ لا مفترَضة (2026-09-07).

    ⛔ **العلّة:** الحارسُ الخامس في `add_surah_reciter.py` يردّ ما خرج عن
    `0.25 ≤ durationPerLetter ≤ 4.0`، **ولا مُنتِجَ للحقل في المستودعين**
    (‏قِيس: `grep -rn durationPerLetter` خارج الأداة واختبارِها = صفر) ⇒
    **حارسٌ ميّتٌ يمرّ عليه كلُّ بترٍ مصدريّ**، وهي علّةُ الدرس 29 نفسُها في
    ثوبٍ ثانٍ: نصفُ أداةٍ غائبٌ لا نقصُ مرشَّحين.

    **والوحدةُ استُنبطت بالقياس من الأصول لا من ظنّ:** بحساب حروف السور من
    `text_{riwaya}.jz` ومدَدٍ حقيقيةٍ من جدول المسح — س2 = 25,700 حرفاً في
    7679ث ⇒ **0.299** · س1 = 139 في 45ث ⇒ 0.324 · س112 = 47 في 30ث ⇒ 0.638 ·
    س108 = 42 في 16ث ⇒ 0.381. فالنطاقُ يسع السليمَ كلَّه بهامشٍ واسع،
    ويردّ البترَ الجسيم (‏`3siri` س9 = 22% من المتوقَّع ⇒ 0.066 خارجَه).
    ولو كانت الوحدةُ مللي ثانيةٍ لكانت القيمُ بالمئات وردَّ الحارسُ الكلَّ.
    """
    n = letters(riwaya, surah)
    if n <= 0:
        raise SystemExit(f"⛔ صفرُ حروفٍ في س{surah} من {riwaya}")
    return round((duration_ms / 1000.0) / n, 4)


# ───────────────────────── تركيبُ ملفّ البرهان ─────────────────────────
def assemble(probe: dict, riwaya: str) -> dict:
    """يحوّل مخرَجَ المسبار الخام إلى ملفّ برهانٍ يقبله `add_surah_reciter`."""
    tr = probe.get("transcripts") or {}
    if len(tr) < 2:
        raise SystemExit(f"⛔ المسبارُ فيه {len(tr)} تفريغاً والمطلوب اثنان — "
                         "ولا تُخترع درجةٌ بلا نصٍّ مسموع")
    wits = []
    for k in sorted(tr, key=lambda x: int(x)):
        heard = (tr[k] or "").strip()
        if not heard:
            raise SystemExit(f"⛔ تفريغُ س{k} فارغ — يُعاد المسبار، ولا يُقدَّر")
        wits.append(witness(heard, int(k), riwaya, fold=True))
    # ⛔ **الحقلُ يُحسب هنا ولا يُقبل من المسبار**: المسبارُ يقيس الشبكةَ
    #    (‏`status` و`durationMs`)، والمقامُ نصٌّ على القرص. ولو تُرك للمسبار
    #    لبقي الحارسُ الخامسُ ميّتاً كما وُجد.
    files = dict(probe.get("files") or {})
    for s, v in list(files.items()):
        v = dict(v)
        ms = v.get("durationMs")
        if v.get("status") == 200 and ms:
            v["durationPerLetter"] = per_letter(ms, riwaya, int(s))
        files[s] = v
    ev = {"builtBy": TOOL, "riwaya": riwaya,
          "files": files,
          "witnesses": wits,
          "license": probe.get("license") or {}}
    # ⛔ **جدولُ الأسماء يُمرَّر كما هو ولا يُبنى هنا**: هو **قياسُ شبكةٍ** من
    #    `metadata/<id>/files` — شأنُ المسبار لا شأنُ هذه الأداة. وحذفُه هنا
    #    عطبٌ صامتٌ بعينه: يمرّ المرشَّحُ الحُرّاسَ السبعةَ كلَّها ويدخل الكتالوجَ
    #    **بلا `files`**، فيبني المشغِّلُ `base + NNN.mp3` على مضيفٍ لا يرقّم
    #    ⇒ **مصحفٌ كاملٌ صامت**. (‏قِيس 2026-09-09: سقط الحقلُ في أوّل تمريرة.)
    if probe.get("names"):
        ev["names"] = probe["names"]
    return ev


# ───────────────────────── البرهانُ بتفريغاتٍ حقيقية ─────────────────────────
def ayah_text(riwaya: str, surah: int, ayah: int) -> str:
    """آيةٌ واحدةٌ بعدّ حفصٍ الكوفيّ — مرجعُ الصفّ في تقرير `audio_qa`."""
    from run import ASSETS, COUNTS
    txt = json.loads(gzip.decompress(
        (ASSETS / f"text_{riwaya}.jz").read_bytes()).decode("utf-8"))
    return txt[sum(COUNTS[: surah - 1]) + ayah - 1]


def belongs(snippet: str, ref_ayah: str, fold: bool) -> float:
    """نسبةُ كلمات **المسموع** الموجودةِ في الآية المرجعية.

    ⛔ القسمةُ هنا على المسموع لا على المرجع — عكسُ `score` — لأن صفَّ
    `audio_qa` **نافذةٌ جزئيةٌ عند الحدّ** لا سورةٌ كاملة، فالقسمةُ على الآية
    كلِّها تخلط قِصَرَ النافذة بعدم الانتماء. والسؤالُ هنا واحد: **هذا
    المسموعُ لأيِّ الرسمَين أقربُ؟**
    """
    return score(ref_ayah, snippet, fold)


def _rows(report: dict) -> list:
    s = report.get("sample") or {}
    r = s.get("rows") or report.get("rows") or []
    return [x for x in r if isinstance(x, dict)]


def _fwd(row: dict) -> str:
    h = row.get("heard")
    if isinstance(h, str):
        return h
    if isinstance(h, dict):
        return (h.get("fwd") or "").strip()
    return ""


def witness_surahs(riwaya: str, top: int = 12) -> int:
    """⭐ **اختيارُ الشاهدَين يُقاس ولا يُورَث** — أيُّ السور تفرّق هذه الروايةَ من حفص؟

    ⛔ العلّةُ مقيسةٌ: ترويسةُ `add_surah_reciter` تسمّي **1 و112** شاهدَين،
    و**112 نصُّها واحدٌ في الروايتين** فدرجتاها متساويتان دائماً ⇒ `conflict`
    لكلّ مرشَّح ⇒ الحارسُ الرابع يطلب سورةً ثالثةً **في كلّ مرّة**، فيُنفَق
    مسبارٌ زائدٌ على كلّ واحدٍ من الخمسين بلا فائدة. والشاهدُ الذي لا يفرّق
    ليس شاهداً.
    """
    from normalizer_audit import words_folded as W
    from run import COUNTS
    if riwaya == "hafs":
        raise SystemExit("⛔ حفصٌ لا يُقابَل بنفسه — سمِّ روايةً أخرى")
    rows = []
    for s in range(1, 115):
        a, b = W(surah_text(riwaya, s)), W(surah_text("hafs", s))
        ca, cb = collections.Counter(a), collections.Counter(b)
        same = sum((ca & cb).values())
        tot = max(sum(ca.values()), 1)
        rows.append((1 - same / tot, s, COUNTS[s - 1], tot - same, tot))
    rows.sort(reverse=True)
    dead = sum(1 for d, *_ in rows if d == 0)
    print(f"# سورٌ تفرّق {riwaya} من حفص — بالمطبِّع المطويّ · {TOOL}\n")
    print(f"{'س':>4} {'آي':>5} {'كلماتٌ تفترق':>13} {'من':>7} {'الفرق':>8}")
    print("-" * 42)
    for d, s, ay, diff, tot in rows[:top]:
        print(f"{s:>4} {ay:>5} {diff:>13,} {tot:>7,} {d:>7.1%}")
    print(f"\n⇒ سورٌ **لا تفرّق شيئاً** (فرقٌ 0.0%): **{dead}** من 114 — "
          "وكلُّ واحدةٍ منها شاهدٌ ميّتٌ يُنتج `conflict` دائماً.")
    z = [s for d, s, *_ in rows if d == 0]
    if 112 in z:
        print("⛔ و**سورة 112 منها** — وهي الشاهدُ الثاني المكتوبُ في الترويسة، "
              "فيُستبدل بأعلى الجدول.")
    print(f"\n⇒ الشاهدان المقترحان لـ{riwaya}: "
          f"**{rows[0][1]} و{rows[1][1]}** (فرقٌ {rows[0][0]:.1%} و{rows[1][0]:.1%}) — "
          "وقِصَرُ السورة يُوازَن بقدرتها على التفريق.")
    short = [(d, s, ay) for d, s, ay, *_ in rows if ay <= 30][:3]
    if short:
        print("   ومن القصار (‏≤30 آية، أرخصُ مسباراً): " +
              " · ".join(f"س{s} ({ay} آية · {d:.1%})" for d, s, ay in short))
    return 0


def prove(keys: list[str]) -> int:
    """يعيد قياسَ الكاشف على تفريغاتٍ حقيقيةٍ من الدلو — صفّاً صفّاً بالأسماء."""
    import run
    cl, bucket = run.s3()
    print(f"# برهانُ كاشف النسبة الخاطئة · {TOOL}\n")
    print("لكلّ صفٍّ في تقرير `audio_qa`: نافذتُه المسموعة (`heard.fwd`) تُقابَل")
    print("بنصّ آيتِها في **روايتها المعلَنة** وفي **الرواية المنافسة**، بالمطبِّعَين.")
    print("و«انقلاب» = فوزُ المنافس. والتفريغُ أصلاً بلا ألفِ وصلٍ (‏قِيس أدناه).\n")
    hdr = (f"{'التقرير':<44} {'رواية':<6} {'منافس':<6} {'صفوف':>5} "
           f"{'ٱ في المسموع':>12} | {'خام: فاز/انقلب':>16} | {'مطويّ: فاز/انقلب':>17}")
    print(hdr)
    print("-" * len(hdr))
    tot_raw_inv = tot_fold_inv = tot_rows = 0
    for key in keys:
        try:
            rep = json.loads(cl.get_object(Bucket=bucket, Key=key)["Body"].read())
        except Exception as e:                             # noqa: BLE001
            print(f"⛔ تعذّر {key}: {e}")
            continue
        name = key.split("/")[-1]
        riwaya = rep.get("riwaya")
        if not riwaya:
            print(f"⛔ روايةُ {name} غيرُ معلومة — لا يُخمَّن")
            continue
        rival = "warsh" if riwaya == "hafs" else "hafs"
        rows = _rows(rep)
        raw_inv = fold_inv = n = wasla = 0
        for row in rows:
            aid = row.get("aid") or ""
            snip = _fwd(row)
            if not snip or ":" not in str(aid):
                continue
            s, y = (int(x) for x in str(aid).split(":")[:2])
            if not (1 <= s <= 114):
                continue
            own = ayah_text(riwaya, s, y)
            oth = ayah_text(rival, s, y)
            n += 1
            wasla += sum(1 for w in snip.split() if "ٱ" in w)
            if belongs(snip, oth, False) > belongs(snip, own, False):
                raw_inv += 1
            if belongs(snip, oth, True) > belongs(snip, own, True):
                fold_inv += 1
        if not n:
            print(f"⛔ {name}: لا صفوفَ فيها `heard.fwd`")
            continue
        tot_rows += n
        tot_raw_inv += raw_inv
        tot_fold_inv += fold_inv
        print(f"{name[:44]:<44} {riwaya:<6} {rival:<6} {n:>5} {wasla:>12} | "
              f"{n - raw_inv:>6} / {raw_inv:<3} ({raw_inv / n:>5.1%}) | "
              f"{n - fold_inv:>6} / {fold_inv:<3} ({fold_inv / n:>5.1%})")
    if tot_rows:
        print(f"\n⇒ صفوفٌ حقيقيةٌ قِيست: **{tot_rows}** · انقلبت بالمطبِّع الخام: "
              f"**{tot_raw_inv} ({tot_raw_inv / tot_rows:.1%})** · "
              f"بالمطويّ: **{tot_fold_inv} ({tot_fold_inv / tot_rows:.1%})**")
    return 0


# ───────────────────────── الاختبارُ الذاتيّ ─────────────────────────
def _self_test() -> None:
    from run import COUNTS
    assert len(COUNTS) == 114 and sum(COUNTS) == 6236

    # (١) المرجعُ يُقرأ بحدوده — الفاتحةُ سبعُ آياتٍ والإخلاصُ أربع
    f_hafs = surah_text("hafs", 1)
    assert "ٱ" in f_hafs, "نصُّ حفصٍ يحمل ألفَ الوصل — وهو أصلُ العلّة"
    assert "ٱ" not in surah_text("warsh", 1), "ونصُّ ورشٍ لا يحملها"
    print("  ✅ (١) المرجعان يُقرآن من القرص، والتعرّضُ غيرُ متماثلٍ بين الروايتين")

    # (٢) الدرجةُ تامّةٌ حين يُقابَل النصُّ بنفسه، وتنقص حين يُنقص
    assert score(f_hafs, f_hafs) == 1.0
    assert score("", f_hafs) == 0.0
    half = " ".join(f_hafs.split()[: len(f_hafs.split()) // 2])
    assert 0.3 < score(half, f_hafs) < 0.75, score(half, f_hafs)
    print("  ✅ (٢) الدرجةُ 1.0 للنصّ بنفسه · 0.0 للفراغ · وتنقص بنقصان المسموع")

    # (٣) إطالةُ التفريغ لا ترفع الدرجة — القسمةُ على المرجع لا على المسموع
    assert score(f_hafs + " " + surah_text("hafs", 112), f_hafs) == 1.0
    print("  ✅ (٣) حشوُ التفريغ لا يرفع الدرجة (‏القسمةُ على المرجع)")

    # (٤) فرقُ الرواية الحقيقيّ يبقى بعد الطيّ — الكاشفُ لا يُعمى
    assert score("مالك يوم الدين", "ملك يوم الدين") < 1.0
    print("  ✅ (٤) `مالك`/`ملك` يبقى فارقاً بعد الطيّ — فالكاشفُ يرى الرواية")

    # (٥) ⛔⛔ الحالةُ السالبةُ الحاكمة: **الانقلابُ في الاتجاه الخطر**
    #     تفريغٌ إملائيٌّ حديثٌ لتلاوةِ حفص (‏كما يكتبه whisper، بلا ألفِ وصل).
    heard_hafs = ("بسم الله الرحمن الرحيم الحمد لله رب العالمين الرحمن الرحيم "
                  "مالك يوم الدين اياك نعبد واياك نستعين اهدنا الصراط المستقيم "
                  "صراط الذين انعمت عليهم غير المغضوب عليهم ولا الضالين")
    raw_h = score(heard_hafs, surah_text("hafs", 1), fold=False)
    raw_w = score(heard_hafs, surah_text("warsh", 1), fold=False)
    fol_h = score(heard_hafs, surah_text("hafs", 1), fold=True)
    fol_w = score(heard_hafs, surah_text("warsh", 1), fold=True)
    assert raw_w > raw_h, (
        "⛔ الانقلابُ لم يعد يقع — يُعاد قياسُ الأصول قبل حذف هذا الاختبار "
        f"(خام: حفص {raw_h:.3f} · ورش {raw_w:.3f})")
    assert fol_h >= fol_w, (
        f"⛔ الطيُّ لم يشفِ الانقلاب (مطويّ: حفص {fol_h:.3f} · ورش {fol_w:.3f})")
    print(f"  ✅ (٥) الانقلابُ مُثبَّتٌ حالةً سالبة — خام: حفص {raw_h:.3f} < ورش "
          f"{raw_w:.3f} ⛔ · مطويّ: حفص {fol_h:.3f} ≥ ورش {fol_w:.3f} ✅")

    # (٦) `assemble` يردّ المسبارَ الناقص ولا يخترع درجة
    for bad, why in ((({"transcripts": {"1": "x"}}), "تفريغٌ واحد"),
                     (({"transcripts": {"1": " ", "112": "y"}}), "تفريغٌ فارغ")):
        try:
            assemble(bad, "warsh")
        except SystemExit:
            pass
        else:
            raise AssertionError(f"⛔ `assemble` قبِل مسباراً فيه {why}")
    ok = assemble({"transcripts": {"1": heard_hafs, "112": "قل هو الله احد"},
                   "files": {}, "license": {"declared": "x"}}, "hafs")
    assert len(ok["witnesses"]) == 2 and ok["builtBy"] == TOOL
    assert "names" not in ok, "⛔ اختُرع جدولُ أسماءٍ لمسبارٍ بلا أسماء"
    # ⛔ **وجدولُ الأسماء يعبر ولا يسقط** — سقوطُه عطبٌ صامت: مصحفٌ يدخل
    #    الكتالوجَ بلا `files` فيُبنى عنوانُه `NNN.mp3` على مضيفٍ لا يرقّم.
    nm = [f"ar_{s:03d}_X.mp3" for s in range(1, 115)]
    ok2 = assemble({"transcripts": {"1": heard_hafs, "112": "قل هو الله احد"},
                    "files": {}, "license": {"declared": "x"}, "names": nm}, "hafs")
    assert ok2.get("names") == nm, "⛔ سقط جدولُ الأسماء في `assemble`"
    print("  ✅ (٦) `assemble` يردّ المسبارَ الناقصَ ويبني الشاهدَين من التامّ · "
          "وجدولُ الأسماء يعبر كما هو ولا يُخترع")

    # (٧) ⛔⛔ **الحارسُ الخامسُ كان ميّتاً**: لا مُنتِجَ لـ`durationPerLetter`.
    #     فيُثبَّت هنا أنّ `assemble` يحسبه، **وأنّ الوحدةَ ثانيةٌ لا مللي**:
    #     السليمُ داخل نطاق الحارس (0.25–4.0)، والمبتورُ خارجَه.
    two = assemble({"transcripts": {"1": heard_hafs, "112": "قل هو الله احد"},
                    "files": {"2": {"status": 200, "durationMs": 7679000},
                              "112": {"status": 200, "durationMs": 30000},
                              "9": {"status": 200, "durationMs": 659900},
                              "7": {"status": 404}},
                    "license": {"declared": "x"}}, "hafs")["files"]
    assert 0.25 <= two["2"]["durationPerLetter"] <= 4.0, two["2"]
    assert 0.25 <= two["112"]["durationPerLetter"] <= 4.0, two["112"]
    # ⛔ الحالةُ السالبة **من واقعةٍ مقيسة**: `3siri` س9 مبتورةٌ إلى 660ث
    #    (‏22% من المتوقَّع، الدرس 16) — والحارسُ يجب أن يراها.
    assert two["9"]["durationPerLetter"] < 0.25, (
        f"⛔ بترُ `3siri` س9 لا يقع خارج النطاق ⇒ الحارسُ الخامسُ لا يحرس "
        f"({two['9']['durationPerLetter']})")
    assert "durationPerLetter" not in two["7"], "⛔ حُسب لملفٍّ لم يُرَ (404)"
    from add_surah_reciter import check_evidence
    # مسبارٌ سليمٌ اصطناعيّ: 0.40ث لكل حرف — إيقاعُ ترتيلٍ داخل النطاق
    base = {"files": {str(s): {"status": 200,
                               "durationMs": letters("hafs", s) * 400}
                      for s in range(1, 115)},
            "transcripts": {"1": heard_hafs, "112": "قل هو الله احد"},
            "license": {"declared": "x"}}
    assert not any(x.startswith("5:") for x in
                   check_evidence(assemble(base, "hafs"), "hafs")), \
        "⛔ مسبارٌ سليمٌ ردَّه الحارسُ الخامس"
    base["files"]["2"]["durationMs"] = 60000           # البقرةُ في دقيقة = بترٌ
    assert any(x.startswith("5:") for x in
               check_evidence(assemble(base, "hafs"), "hafs")), \
        "⛔ البقرةُ في دقيقةٍ مرّت على الحارس الخامس"
    print("  ✅ (٧) `durationPerLetter` يُحسب بالثانية — والحارسُ الخامسُ صار حيّاً "
          "(‏س2 في دقيقةٍ تُردّ · بترُ `3siri` س9 يُرى)")
    print(f"✅ --self-test أخضر · {TOOL}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--prove", action="store_true")
    ap.add_argument("--key", action="append", default=[],
                    help="مفتاحُ تقرير `audio_qa` على الدلو (‏يُكرَّر)")
    ap.add_argument("--witness-surahs", metavar="RIWAYA",
                    help="يرتّب السورَ بقدرتها على تفريق الرواية من حفص")
    ap.add_argument("--assemble", help="ملفُّ المسبار الخام (JSON)")
    ap.add_argument("--riwaya")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.self_test:
        _self_test()
        return
    if a.witness_surahs:
        sys.exit(witness_surahs(a.witness_surahs))
    if a.prove:
        sys.exit(prove(a.key))
    if a.assemble:
        if not a.riwaya:
            sys.exit("⛔ ينقص --riwaya")
        ev = assemble(json.load(open(a.assemble, encoding="utf-8")), a.riwaya)
        out = json.dumps(ev, ensure_ascii=False, indent=1)
        if a.out:
            open(a.out, "w", encoding="utf-8").write(out)
            print(f"↑ {a.out}")
        else:
            print(out)
        return
    ap.print_help()


if __name__ == "__main__":
    main()
