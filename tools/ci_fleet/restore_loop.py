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
import statistics
import subprocess
import sys
import urllib.request
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                          # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "index_qa"))

from run import fetch_index, list_indexes, s3                  # noqa: E402
from drop_surah import SURAH_AYAHS_OF                          # noqa: E402

# مراجعُ كاملةُ الصوت — أربعةٌ لا واحد (§2 أعلاه).
REFS = ["timings/hafs/a_turki.jz", "timings/hafs/tblawi.jz",
        "timings/hafs/harthi.jz", "timings/hafs/abdullahk.jz"]
UA = {"User-Agent": "Mozilla/5.0"}
SOUND = 0.85          # وسيطُ نسبةِ الحجم الذي دونه يُعدّ المصدرُ مبتوراً
LOWCOV = 0.75         # تغطيةُ سورةٍ حاضرةٍ تُعدّ دونها ناقصة
MIN_AYAHS = 3         # لا يُنفق عدّاءٌ على أقلَّ من هذا


def head_len(url: str) -> int:
    rq = urllib.request.Request(url, method="HEAD", headers=UA)
    with urllib.request.urlopen(rq, timeout=45) as r:
        return int(r.headers.get("Content-Length", 0))


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


def source_ratio(idx, base: str, surah: int, refs) -> float | None:
    """نسبةُ حجمِ الملفّ إلى المتوقَّع — **وسيطُ أربعةِ مراجع**."""
    d = surah_ends(idx)
    probe = [s for s in sorted(d, key=lambda x: -d[x]) if s != surah][:3]
    if not probe:
        return None
    try:
        bps = sum(head_len(f"{base}{s:03d}.mp3") / (d[s] / 1000.0) for s in probe) / len(probe)
        actual = head_len(f"{base}{surah:03d}.mp3")
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
    out = set()
    repo = os.environ.get("GITHUB_REPOSITORY", "mwqwf/rafiq-align-ci")
    for st in ("in_progress", "queued", "pending"):
        txt = gh("api", f"repos/{repo}/actions/runs?status={st}&per_page=100",
                 "-q", ".workflow_runs[].display_title")
        for ln in txt.splitlines():
            out.add(ln.strip())
    return out


def candidates():
    """السورُ التي يُرجى استرجاعُها، الأكثرُ آياتٍ أوّلاً."""
    rows = []
    for r in list_indexes():
        k = r["key"]
        try:
            idx, _ = fetch_index(k)
        except Exception:                                      # noqa: BLE001
            continue
        riw, rid = k.split("/")[1], k.split("/")[2][:-3]
        counts = SURAH_AYAHS_OF(idx)
        per = {}
        for e in idx["entries"]:
            s = int(e["ayahId"].split(":")[0])
            per[s] = per.get(s, 0) + 1
        for s in range(1, 115):
            have, exp = per.get(s, 0), counts[s - 1]
            gap = exp - have
            if gap >= MIN_AYAHS and (have == 0 or have / exp < LOWCOV):
                rows.append({"riwaya": riw, "reciter": rid, "surah": s,
                             "have": have, "expected": exp, "gap": gap, "key": k})
    rows.sort(key=lambda x: -x["gap"])
    return rows


# ───────────────────────── scan: يقيس ثمّ يُطلق المحاذاة ─────────────────────────
def cmd_scan(a):
    bases = catalog_bases()
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
        base = bases.get((riw, rid))
        if not base:
            print(f"   ⛔ {rid}: لا مصدرَ في الكتالوج")
            continue
        idx, _ = fetch_index(r["key"])
        ratio = source_ratio(idx, base, s, refs)
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
        out = gh("workflow", "run", "realign_surah.yml",
                 "--repo", os.environ.get("GITHUB_REPOSITORY", "mwqwf/rafiq-align-ci"),
                 "-f", f"parent=timings/{riw}/{rid}.jz", "-f", f"surahs={s}",
                 "-f", f"skip_ms={skip}", "-f", f"url_template={base}{{s:03d}}.mp3",
                 "-f", f"reciter_id={rid}", "-f", f"riwaya={riw}", "-f", f"reason={reason}")
        print(f"      ▶ أُطلقت إعادةُ المحاذاة {out.strip()}")
        done += 1
    print(f"⇒ أُطلق {done}")


# ───────────────────────── gate: يُبوّب المحسَّنين ─────────────────────────
def _staged_improvements():
    """بصماتُ مسرحٍ لقارئٍ **منشور** مداخلُها أكثرُ من المنشور."""
    cl, b = s3()
    live, staged = {}, []
    for pg in cl.get_paginator("list_objects_v2").paginate(Bucket=b, Prefix="timings/"):
        for o in pg.get("Contents", []):
            k = o["Key"]
            if k.endswith(".jz") and k.count("/") == 2:
                live[(k.split("/")[1], k.split("/")[2][:-3])] = k
    mt = {}
    for pg in cl.get_paginator("list_objects_v2").paginate(Bucket=b, Prefix="timings-staging/"):
        for o in pg.get("Contents", []):
            if o["Key"].endswith(".jz") and "/timings/" not in o["Key"]:
                staged.append(o["Key"]); mt[o["Key"]] = o["LastModified"]
    newest = {}
    for k in staged:
        p = k.split("/")
        if len(p) < 3:
            continue
        who = (p[1], p[2].split(".")[0])
        if who in live and (who not in newest or mt[k] > mt[newest[who]]):
            newest[who] = k
    out = []
    for who, k in newest.items():
        try:
            n, _ = fetch_index(k); o, _ = fetch_index(live[who])
        except Exception:                                      # noqa: BLE001
            continue
        if len(n["entries"]) > len(o["entries"]):
            out.append({"key": k, "live": live[who], "gain": len(n["entries"]) - len(o["entries"]),
                        "riwaya": who[0], "reciter": who[1]})
    out.sort(key=lambda x: -x["gain"])
    return out


def _salt_count(key: str) -> int:
    cl, b = s3()
    stem = key.replace("/", "_").replace(".jz", "")
    n = 0
    for pg in cl.get_paginator("list_objects_v2").paginate(Bucket=b, Prefix="state/"):
        for o in pg.get("Contents", []):
            if stem in o["Key"] and "audio-" in o["Key"]:
                n += 1
    return n


def cmd_gate(a):
    repo = os.environ.get("GITHUB_REPOSITORY", "mwqwf/rafiq-align-ci")
    busy = inflight_reciters()
    todo = [r for r in _staged_improvements()
            if _salt_count(r["key"]) < 4 and r["key"] not in "".join(busy)]
    print(f"محسَّنون بلا حكمٍ كافٍ: {len(todo)}")
    batch = [r["key"] for r in todo[:a.limit]]
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
    print(f"⇒ بُوِّب {len(batch)} بخمسِ تشغيلات")


# ───────────────────────── promote: يرقّي ما مرّ ─────────────────────────
def cmd_promote(a):
    prom = str(ROOT / "tools" / "index_qa" / "promote.py")
    for r in _staged_improvements():
        if _salt_count(r["key"]) < 4:
            continue
        dry = subprocess.run([sys.executable, prom, "--only", r["key"]],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", cwd=str(ROOT))
        tail = "\n".join(l for l in dry.stdout.splitlines() if "🔇" not in l)[-400:]
        if "✅ جاهز" not in dry.stdout:
            print(f"   ⏸️ {r['reciter']}: لم يمرّ بعدُ — {tail.splitlines()[-1] if tail else ''}")
            continue
        # ⛔ التجميدُ يُرفع **للحظةِ ترقيةٍ متحقَّقة** لا قبلها
        why = (f"استرجاعُ آياتٍ مفقودة: المرشَّحُ {r['key'].split('/')[-1]} يزيد "
               f"**{r['gain']} مدخلاً** على المنشور، وقد مرّ بحكمه الصوتيّ بأربعة ملوحٍ فأكثر.")
        subprocess.run([sys.executable, prom, "--unfreeze", r["live"], "--reason", why],
                       cwd=str(ROOT), text=True)
        done = subprocess.run([sys.executable, prom, "--only", r["key"], "--yes"],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", cwd=str(ROOT))
        ok = "→ ✅" in done.stdout
        print(f"   {'✅ رُقّي' if ok else '⛔ لم يُرقَّ'} {r['reciter']} (+{r['gain']})")
        for l in done.stdout.splitlines():
            if "🧊" in l or "⛔" in l:
                print("      " + l.strip()[:160])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("scan");    p1.add_argument("--limit", type=int, default=3)
    p2 = sub.add_parser("gate");    p2.add_argument("--limit", type=int, default=6)
    sub.add_parser("promote")
    a = ap.parse_args()
    {"scan": cmd_scan, "gate": cmd_gate, "promote": cmd_promote}[a.cmd](a)


if __name__ == "__main__":
    main()
