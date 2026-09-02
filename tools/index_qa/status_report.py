#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تقرير حالة فهارس التوقيتات على الدلو — من الملفّات وحدها، بلا خادم.

    python tools/index_qa/status_report.py [--out docs/qa/INDEX_STATUS_2026-09-02.md]

يجمع لكل فهرسٍ منشور: الرواية · المداخل والتغطية · نسبة MED · جيلَه (‏`v2.1`
أو `none` أو **غير مصنَّف** حين لا حقل أصلاً) · حكمَ الصوت إن وُجد في `state/`
(ممثِّلة أو عيّنة MED — ولا يُخلطان) · وحالةَ الإعادة إن كان له كائنٌ في
`timings-staging/`.

⛔ **ولا يُخترع ما لا يُقاس:** ما لا يُعرف يُكتب «—» صراحةً، فالجدول الذي يملأ
فراغه بالتخمين أسوأ من جدولٍ فيه فراغ.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import hashlib
import json
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                 # noqa: BLE001
        pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import promote                                                       # noqa: E402

AYAHS = 6236
SURAH_AYAHS = [
    7, 286, 200, 176, 120, 165, 206, 75, 129, 109, 123, 111, 43, 52, 99, 128,
    111, 110, 98, 135, 112, 78, 118, 64, 77, 227, 93, 88, 69, 60, 34, 30, 73,
    54, 45, 83, 182, 88, 75, 85, 54, 53, 89, 59, 37, 35, 38, 29, 18, 45, 60,
    49, 62, 55, 78, 96, 29, 22, 24, 13, 14, 11, 11, 18, 12, 12, 30, 52, 52, 44,
    28, 28, 20, 56, 40, 31, 50, 40, 46, 42, 29, 19, 36, 25, 22, 17, 19, 26, 30,
    20, 15, 21, 11, 8, 8, 19, 5, 8, 8, 11, 11, 8, 3, 9, 5, 4, 7, 3, 6, 3, 5, 4,
    5, 6]
assert sum(SURAH_AYAHS) == AYAHS


def verdicts():
    """أحكام `state/` مرتّبة على المفتاح، مفصولةً: ممثِّلة عن عيّنة نطاق."""
    out = collections.defaultdict(lambda: {"rep": None, "band": None})
    for _name, rep in promote.reports():
        key = rep.get("key")
        slot = "band" if rep.get("band") else "rep"
        cur = out[key][slot]
        if cur is None or (rep.get("ts") or 0) > (cur.get("ts") or 0):
            out[key][slot] = rep
    return out


def rate_of(rep):
    """الحكم ومعدّل عطبه — والرقم **لا يُكتب عارياً عن حكمه**: قارئٌ يرى «2.1%»
    وحدها يظنّها قبولاً، وقد تكون في فهرسٍ مرفوضٍ بنيوياً."""
    if not rep:
        return "—"
    verdict = rep.get("verdict") or ""
    mark = ("✅" if verdict == "مقبول"
            else "🔴" if verdict.startswith("مرفوض") else "⚠️")
    sev = rep.get("severeRate")
    if isinstance(sev, dict):
        txt = (f"{sev.get('rate', 0) * 100:.1f}% "
               f"[{sev.get('lo', 0) * 100:.1f}–{sev.get('hi', 0) * 100:.1f}]")
    elif isinstance(sev, (int, float)):
        txt = f"{sev * 100:.1f}%"
    else:
        txt = verdict or "—"
    return f"{mark} {txt}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "docs" / "qa" /
                                         f"INDEX_STATUS_{time.strftime('%Y-%m-%d')}.md"))
    args = ap.parse_args()
    cl, bucket = promote.s3()

    published, staging = [], collections.defaultdict(list)
    for page in cl.get_paginator("list_objects_v2").paginate(
            Bucket=bucket, Prefix="timings"):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if not key.endswith(".jz"):
                continue
            if key.startswith("timings/"):
                published.append((key, obj["Size"], obj["LastModified"]))
            elif key.startswith("timings-staging/"):
                parts = key.split("/")
                if len(parts) == 3:
                    staging[parts[2].split(".")[0]].append(key)

    judged = verdicts()
    frozen, _ftext, _fetag = promote.load_frozen(cl, bucket)
    holds = promote.held()
    wds = promote.withdrawn()
    rows, summary = [], collections.Counter()
    for key, size, mtime in sorted(published):
        body = cl.get_object(Bucket=bucket, Key=key)["Body"].read()
        idx = json.loads(gzip.decompress(body).decode("utf-8"))
        entries = idx.get("entries", [])
        # **هل النقص «لم يُفهرس» أم «فُقد»؟** يُفصل بالبنية لا بالظنّ: عددُ
        # بصمات الصوت (‏114 = كل السور نُزّلت وعولجت) وعددُ السور الحاضرة في
        # المداخل وكم منها **كاملة**. فإن كانت البصمات 114 والسور حاضرة كلّها
        # ولا سورة كاملة، فالنقص **فقدٌ متناثر داخل السور** لا تشغيلٌ لم يتمّ.
        surahs = collections.Counter(int(e["ayahId"].split(":")[0])
                                     for e in entries if e.get("ayahId"))
        complete = sum(1 for s, n in surahs.items()
                       if 1 <= s <= 114 and n == SURAH_AYAHS[s - 1])
        bands = collections.Counter(e.get("confBand") for e in entries)
        med = bands.get("MED", 0)
        vad = idx.get("vad") or {}
        versions = vad.get("versions")
        vad_txt = "—"
        if isinstance(versions, dict) and versions:
            vad_txt = " · ".join(f"{k}×{v}" for k, v in versions.items())
        elif versions == "unknown":
            vad_txt = "غير مسجَّل"
        elif idx.get("writerHostVadVersion"):
            vad_txt = f"(كاتب: {idx['writerHostVadVersion']})"
        elif vad.get("writerHostVadVersion"):
            # بين قوسين عمداً: هذه **نسخة جهاز الكاتب** لا نسخة بناء السور،
            # فلا تُقرأ وصفاً للفهرس (اقتراح github-3a).
            vad_txt = f"(كاتب: {vad['writerHostVadVersion']})"
        gen = idx.get("refineVersion")
        gen_txt = "غير مصنَّف" if gen is None else str(gen)
        rid = idx.get("reciterId") or key.split("/")[-1][:-3]
        v = judged.get(key, {"rep": None, "band": None})
        rebuild = "في الطابور" if staging.get(rid) else "—"
        # **تشخيص البتر المصدري** (‏github-12): عمودٌ يقول أفُحص أم لا — ولا
        # يُترك الفراغ يُقرأ «سليم». والمحجوز يُعلَن بسببه لا بصمته.
        cut, had = promote.truncation(cl, bucket, row_riwaya := idx.get("riwaya", "?"),
                                      rid)
        if not had:
            diag = "—"
        elif cut:
            diag = "🔴 " + "، ".join(str(x.get("surah")) for x in cut[:3])
        else:
            diag = "✅"
        row = {
            "key": key, "riwaya": idx.get("riwaya", "?"), "id": rid,
            "entries": len(entries), "cover": len(entries) / AYAHS * 100,
            "med": med, "medPct": (med / len(entries) * 100) if entries else 0,
            "gen": gen_txt, "rep": rate_of(v["rep"]), "band": rate_of(v["band"]),
            "rebuild": rebuild, "frozen": key in frozen,
            "sha": hashlib.sha256(body).hexdigest()[:8],
            "missing": AYAHS - len(entries),
            "surahs": len(surahs), "complete": complete, "vad": vad_txt,
            "diag": diag, "hold": holds.get(key),
            # **شاهدٌ مسحوب:** حكمُ صوتِه أقدمُ من لحظة سحب دليله،
            # فالعمود يقول ذلك بدل أن يُقرأ الحكم سليماً.
            "wd": bool(wds.get(rid)) and (
                ((v["rep"] or {}).get("ts") or 0) < wds[rid][0]),
            "audioSha": len(idx.get("audioSha256") or []),
        }
        rows.append(row)
        summary["الكل"] += 1
        summary["غير مصنَّف" if gen is None else "مصنَّف"] += 1
        summary["بحكم صوتي ممثِّل" if v["rep"] else "بلا حكم صوتي ممثِّل"] += 1
        if (v["rep"] or {}).get("verdict") == "مقبول":
            summary["حكمه مقبول"] += 1
        if row["cover"] < 98:
            summary["ناقص التغطية"] += 1
        if row["cover"] >= 98:
            summary["تغطية ≥98%"] += 1
        if row["frozen"]:
            summary["مجمَّد"] += 1
        if row["audioSha"] == 114:
            summary["صوته كامل (114 بصمة)"] += 1
        if gen == "v2.1":
            summary["جيل v2.1"] += 1
        if vad_txt != "—":
            summary["يحمل وسم VAD"] += 1
        if idx.get("missing") is not None:
            summary["يحمل وسم اكتمال"] += 1
        if had:
            summary["مفحوصُ البتر"] += 1
        if cut:
            summary["فيه سورةٌ مبتورة"] += 1
        if holds.get(key):
            summary["محجوز"] += 1
        if row["wd"]:
            summary["شاهدٌ مسحوب"] += 1

    # وسيطا التغطية مفصولين: المرفوع الليلة بالوصفة الجديدة، وما قبله.
    new_cov = sorted(r["cover"] for r in rows if r["gen"] == "v2.1")
    old_cov = sorted(r["cover"] for r in rows if r["gen"] != "v2.1")
    med = lambda xs: (xs[len(xs) // 2] if xs else None)   # noqa: E731

    lines = [
        f"# حالة فهارس التوقيتات على الدلو — {time.strftime('%Y-%m-%d %H:%M')}",
        "",
        "> مولَّد آلياً بـ`tools/index_qa/status_report.py` من **الملفّات على الدلو**",
        "> وأحكام `tools/index_qa/state/` — بلا خادم ولا تفريغ صوت.",
        "> و«—» تعني **لا نعلم**، ولا يُملأ فراغٌ بتخمين.",
        "",
        "| # | الرواية | القارئ | مداخل | تغطية | غياب | سور/كاملة | بصمات | MED | الجيل | VAD | حكم ممثِّل | عيّنة MED | بتر | إعادة | 🧊 | شاهد |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(sorted(rows, key=lambda x: (x["riwaya"], x["id"])), 1):
        lines.append(
            f"| {i} | {r['riwaya']} | `{r['id']}` | {r['entries']} | "
            f"{r['cover']:.1f}% | {r['missing']} | {r['surahs']}/{r['complete']} | "
            f"{r['audioSha']} | {r['med']} ({r['medPct']:.1f}%) | "
            f"{r['gen']} | {r['vad']} | {r['rep']} | {r['band']} | {r['diag']} | "
            f"{'⛔' if r['hold'] else r['rebuild']} | "
            f"{'✅' if r['frozen'] else ''} | "
            f"{'⚠️ مسحوب' if r['wd'] else ''} |")
    lines += [
        "",
        "## الخلاصة",
        "",
        "· ".join(f"**{k}** {v}" for k, v in summary.items()),
        "",
        f"**وسيط التغطية:** الجيل الثاني (‏v2.1) "
        f"{('%.1f%%' % med(new_cov)) if new_cov else '—'} على {len(new_cov)} فهرساً · "
        f"ما قبله {('%.1f%%' % med(old_cov)) if old_cov else '—'} على {len(old_cov)}.",
        "",
        "**وما يعنيه هذا للترقية:** بوابة `promote.py` تشترط في الفهرس نفسه أثرَ",
        "صقلٍ صريحاً ووسمَ اكتمال — وهما لم يدخلا كاتب الترويسة إلا ليلة 09-02.",
        "فكلّ ما في الجدول **غير مصنَّف**، ولا يُرقّى منه شيء حتى يُعاد بناؤه",
        "بالوصفة الجديدة (قرار المشرف github-f4: لا استثناء انتقالي). وهذه",
        "الفهارس **منشورةٌ تعمل**، وحُراس التطبيق هي التي تحكم ظهورها للمستخدم.",
        "",
        "**والتغطية الناقصة فقدٌ حقيقي لا «لم يكتمل بعد» — والقياس يفصل:** الـ39",
        "كلّها تحمل **114 بصمة صوت** (‏أي أن كل سورةٍ نُزّلت وعولجت)، وسورُها",
        "الحاضرة في المداخل 112–114، **ووسيط السور الحاضرة 114**. ومع ذلك فأدنى",
        "الجدول تغطيةً (‏`a_ahmed` 29.4% · `deban_douri` 35.4%) فيه **صفر سورة",
        "كاملة**. فالنقص **متناثرٌ داخل السور** لا سورٌ لم تُشغَّل — وهو فقدُ",
        "ليلة الحمل الزائد (تصحيح المشرف github-f4، وقد قِسته قبل كتابته).",
        "",
        "> وكنتُ كتبتُ في أول توليدٍ أن النقص «قد يكون لأن الأسطول لم يكمل».",
        "> **والقياس أبطله**: عمودا «سور/كاملة» و«بصمات» أُضيفا ليجعلا هذا",
        "> السؤال مقروءاً من الجدول لا مظنوناً — فالبصمة 114 تُغلق باب «لم",
        "> يُشغَّل»، وصفرُ السور الكاملة يفتح باب «فُقد».",
        "",
        "**وما يميّز الفقد من الابتلاع** يبقى في تصنيف سبب الغياب الذي صار",
        "يكتبه كاتب الترويسة (`surah-absent` · `no-align` · `low-conf` ·",
        "`swallowed`) — وهو **غائبٌ عن هذه الـ39** لأنها بُنيت قبله."
        "",
        "**ولا يُخلط حكمان:** «حكم ممثِّل» عيّنةٌ عنقودية على الفهرس كلّه، و«عيّنة",
        "MED» معدّلُ عطبِ تلك الشريحة وحدها — ومن رقّى بالثانية رقّى برقمٍ لا",
        "يخصّ الملفّ.",
    ]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{out.relative_to(ROOT)} — {len(rows)} فهرساً")
    print("· ".join(f"{k} {v}" for k, v in summary.items()))


if __name__ == "__main__":
    main()
