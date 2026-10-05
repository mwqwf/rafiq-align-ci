#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تثبيتُ بدء آياتٍ على **أداءٍ مسموعٍ مقيس** في تسجيلٍ فيه تكرار — أداءٌ واحدٌ متّصلٌ لكلّ آية (fixV · 2026-10-05).

    python tools/index_qa/pin_heard.py --key timings/hafs/asim.jz --sha 0da4de06 --surah 77 \\
        --run 37105755745 --pin 21:95500,22:100600,23:105300,24:114200 --reason "…" --yes

⭐ **سببُه:** تسجيلاتٌ يعيد فيها القارئُ آيةً أو مقطعاً (‏عاصم 77:21–23 تُقرأ مرّتين؛ الجليل 27:64–93
مرّتين؛ المروش 22:5 بتكرارٍ داخلها). المحاذاةُ القسريّة تفرض النصَّ مرّةً واحدةً على صوتٍ فيه مرّتان،
فتردّها حرّاسُ الثقة والمدّة (‏بحقّ)، ويبقى المنشورُ يبتلع الأداءَ الأوّل في مدخلٍ ويُصفّر جارَه (‏77:22 = 200م.ث).
والصوابُ — كما قرّر المنسّق — **أداءٌ واحدٌ متّصلٌ لكلّ آية لا اختلاق**: يبدأ المدخلُ حيث يُسمع أداءُ
الآية فعلاً، وما تكرّر قبله يبقى بلا مدخل (‏فجوةٌ بين مدخلين، لا آيةٌ على صوت غيرها).

**ما يفعله بالضبط:**
1. يقرأ خريطةَ السماع (‏`ctc_heard_map --probe`) من مخرَج التشغيلة `--run` نفسِها (‏لا من نصٍّ يكتبه المُطلِق)،
   ويشترط أن تكون لصوت السورة **نفسِه** في الفهرس: الرابطُ ذاتُه، والبصمةُ = `audioSha256` للسورة.
2. كلُّ بدءٍ في `--pin` يجب أن يقع (‏±150م.ث) على **بدءٍ مقيس** لتلك الآية: مرساتُها العامّة بجودة ≥0.5،
   أو أداءٌ لها بتشابه ≥0.7 — وإلا رُدّ. فالأداةُ **تختار** بين أداءاتٍ مسموعة ولا تُنشئ زمناً.
3. نهايةُ الآية المثبَّتة = بدءُ تاليتها؛ ونهايةُ الآية التي قبل أوّل تثبيتٍ تُقصّ إلى البدء الجديد إن تجاوزته،
   أو إلى قيمة `--trim a:ms` إن أُعطيت، وشرطُها أن تكون **حدّاً مقيساً** في الخريطة (‏بدءَ أداءٍ أو نهايتَه
   للآية نفسِها أو لتاليتها) ودون البدء المثبَّت.
4. ⛔ حُرّاسٌ قبل الرفع: البدءُ لا يتغيّر إلا للمثبَّت · الحدودُ صاعدةٌ بلا تداخل · وحكمُ `heard_gate`
   على السورة بالخريطة نفسِها سليم (‏وإلا لا معنى لرفعه) — ثمّ البوّابةُ الكاملة على المرشّح.
5. `engineBySurah[س] = heard-pin-1` ⇒ تطلب الترقيةُ **إحصاءً صوتيّاً شاملاً** (‏Whisper، شاهدٌ مستقلّ عن
   خريطة CTC) لكلّ آيةٍ في السورة، فوق الملوح الأربعة والمطالع و`heard_gate` (‏بخريطةٍ تُقاس من جديد).
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import subprocess
import sys
import time
import zipfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                 # noqa: BLE001
        pass

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import heard_gate                                                    # noqa: E402

REPO = "mwqwf/rafiq-align-ci"
ENGINE = "heard-pin-1"
SNAP_MS = 150
MIN_ANCHOR_Q = heard_gate.MIN_Q
MIN_OCC_SIM = heard_gate.REPEAT_SIM


def _key(aid):
    s, a = str(aid).split(":")
    return int(s), int(a)


def parse_pairs(txt):
    out = {}
    for part in (txt or "").replace("،", ",").split(","):
        if part.strip():
            a, ms = part.split(":")
            out[int(a)] = int(ms)
    return out


def measured_starts(hmap, ayah):
    """البدءاتُ المقيسة للآية: [(بدء، نهاية، مصدر)]."""
    rec = (hmap.get("heardMap") or {}).get(str(ayah)) or {}
    out = []
    am, q = rec.get("anchorMs"), rec.get("anchorQuality")
    if am and q is not None and float(q) >= MIN_ANCHOR_Q:
        out.append((int(am[0]), int(am[1]), f"مرساة {q}"))
    for o in rec.get("occurrences") or []:
        if float(o[2]) >= MIN_OCC_SIM:
            out.append((int(o[0]), int(o[1]), f"أداء {o[2]}"))
    return out


def measured_bounds(hmap, ayahs):
    """كلُّ حدٍّ مقيسٍ (بدءٌ أو نهاية) لآياتٍ مسمّاة — من المراسي والأداءات بلا شرط جودة."""
    out = set()
    for a in ayahs:
        rec = (hmap.get("heardMap") or {}).get(str(a)) or {}
        if rec.get("anchorMs"):
            out |= {int(x) for x in rec["anchorMs"][:2]}
        for o in rec.get("occurrences") or []:
            out |= {int(o[0]), int(o[1])}
    return out


def pin(idx, surah, hmap, pins, trims=None):
    """يُعيد (فهرساً جديداً، تقريراً) أو يرفع SystemExit بالسبب."""
    trims = trims or {}
    tr = idx.get("transform") if isinstance(idx.get("transform"), dict) else {}
    if "drop_surah" in str((tr or {}).get("op") or "") or (tr or {}).get("dropSurah"):
        raise SystemExit("⛔ الأصلُ يحمل إعلانَ إسقاطٍ في ترويسته — التثبيتُ يستبدل التحويل فيمحوه؛ لا يُبنى عليه")
    if not pins:
        raise SystemExit("⛔ لا تثبيت")
    if int(hmap.get("surah") or 0) != surah:
        raise SystemExit(f"⛔ الخريطةُ لسورة {hmap.get('surah')} لا {surah}")
    ents = list(idx.get("entries") or [])
    mine = {_key(e["ayahId"])[1]: e for e in ents if _key(e["ayahId"])[0] == surah}
    if not mine:
        raise SystemExit(f"⛔ لا مداخل للسورة {surah}")
    refs = {e.get("fileRef") for e in mine.values()}
    if len(refs) != 1 or hmap.get("fileRef") not in refs:
        raise SystemExit(f"⛔ الخريطةُ سُمعت من {hmap.get('fileRef')} والفهرسُ يشير إلى {sorted(refs)[:2]}")
    present = sorted({_key(e["ayahId"])[0] for e in ents})
    shas = idx.get("audioSha256")
    if isinstance(shas, list) and len(shas) == len(present):
        want = shas[present.index(surah)]
        if want and want != hmap.get("sha256"):
            raise SystemExit(f"⛔ بصمةُ الصوت المسموع {str(hmap.get('sha256'))[:8]} غيرُ بصمة الفهرس {str(want)[:8]}")
    report = []
    for a, ms in sorted(pins.items()):
        if a not in mine:
            raise SystemExit(f"⛔ {surah}:{a} لا مدخلَ لها")
        hit = [m for m in measured_starts(hmap, a) if abs(m[0] - ms) <= SNAP_MS]
        if not hit:
            raise SystemExit(f"⛔ {surah}:{a} بدءٌ {ms} لا يقع على أداءٍ مقيس (المقيس: "
                             f"{[(m[0], m[2]) for m in measured_starts(hmap, a)]})")
        report.append(f"{surah}:{a} ⇐ {hit[0][0]} ({hit[0][2]})")
        pins[a] = hit[0][0]
    new = {a: dict(e) for a, e in mine.items()}
    for a in sorted(pins):
        new[a]["startMs"] = pins[a]
    order = sorted(new)
    for a in trims:
        if a not in new or (a + 1) not in new or ((a + 1) not in pins and a not in pins):
            raise SystemExit(f"⛔ --trim {a}: يُقصّ آخرُ آيةٍ قبل تثبيتٍ أو آيةٌ مثبَّتة وحدهما")
        bounds = measured_bounds(hmap, [a, a + 1])
        hit = [b for b in bounds if abs(trims[a] - b) <= SNAP_MS]
        if not hit:
            raise SystemExit(f"⛔ قصُّ {surah}:{a} إلى {trims[a]} ليس حدّاً مقيساً")
        trims[a] = min(hit, key=lambda b: abs(trims[a] - b))
    for i, a in enumerate(order):
        nxt = order[i + 1] if i + 1 < len(order) else None
        if nxt is None or (a not in pins and nxt not in pins):
            continue
        if a in trims:
            new[a]["endMs"] = trims[a]
            report.append(f"{surah}:{a} نهايتُها ⇐ {trims[a]} (حدٌّ مقيس؛ ما بعده تكرارٌ بلا مدخل)")
        elif mine[a].get("endMs") is not None and int(mine[a]["endMs"]) == int(mine[nxt]["startMs"]):
            new[a]["endMs"] = new[nxt]["startMs"]            # كان متّصلاً بتاليه فيبقى متّصلاً
        else:
            new[a]["endMs"] = min(int(mine[a]["endMs"] or 0) or new[nxt]["startMs"], new[nxt]["startMs"])
    prev_end = -1
    for a in order:
        e = new[a]
        st, en = int(e["startMs"]), int(e["endMs"])
        if not (0 <= st < en) or st < prev_end:
            raise SystemExit(f"⛔ {surah}:{a}: حدودٌ غيرُ صاعدة ({st}→{en}، والسابقة تنتهي {prev_end})")
        prev_end = en
        if a not in pins and int(e["startMs"]) != int(mine[a]["startMs"]):
            raise SystemExit(f"⛔ {surah}:{a}: تغيّر بدءُ آيةٍ غيرِ مثبَّتة")
    rows = heard_gate.surah_rows({a: new[a]["startMs"] for a in order}, heard_gate.compact_map(hmap))
    why = heard_gate.surah_verdict(rows)
    if why:
        raise SystemExit(f"⛔ حكمُ السماع على السورة بعد التثبيت: {why}")
    out = dict(idx)
    out["entries"] = [new[_key(e["ayahId"])[1]] if _key(e["ayahId"])[0] == surah else e for e in ents]
    ebs = dict(idx.get("engineBySurah") or {})
    ebs[str(surah)] = ENGINE
    out["engineBySurah"] = ebs
    out["lowCount"] = sum(1 for e in out["entries"] if e.get("confBand") == "LOW")
    changed = [a for a in order if new[a] != mine[a]]
    return out, report, changed


def load_map(run_id, surah):
    def gh(path, raw=False):
        r = subprocess.run(["gh", "api", path], capture_output=True)
        if r.returncode:
            raise SystemExit(f"⛔ gh api {path}: {r.stderr.decode('utf-8', 'replace')[:200]}")
        return r.stdout if raw else json.loads(r.stdout)
    arts = gh(f"repos/{REPO}/actions/runs/{run_id}/artifacts").get("artifacts", [])
    for art in arts:
        zf = zipfile.ZipFile(io.BytesIO(gh(f"repos/{REPO}/actions/artifacts/{art['id']}/zip", raw=True)))
        for nm in zf.namelist():
            if nm.endswith(f"heard_s{surah:03d}.json"):
                return json.loads(zf.read(nm))
    raise SystemExit(f"⛔ لا خريطةَ سماعٍ للسورة {surah} في مخرَج التشغيلة {run_id}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--key", required=True)
    ap.add_argument("--sha", required=True)
    ap.add_argument("--surah", type=int, required=True)
    ap.add_argument("--run", required=True, help="تشغيلةُ ctc_heard_probe (‏build=false) على صوت السورة نفسِه")
    ap.add_argument("--pin", required=True, help="آية:بدءٌ بالم.ث، مفصولةً بفواصل")
    ap.add_argument("--trim", default="", help="آية:نهايةٌ مقيسة لما قبل أوّل تثبيت")
    ap.add_argument("--reason", required=True)
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    import promote
    cl, bucket = promote.s3()
    body = cl.get_object(Bucket=bucket, Key=a.key)["Body"].read()
    live = hashlib.sha256(body).hexdigest()
    if not live.startswith(a.sha):
        raise SystemExit(f"⛔ البصمة لا تطابق: الحيّة {live[:16]} والمطلوبة {a.sha}")
    idx = json.loads(gzip.decompress(body).decode("utf-8"))
    hmap = load_map(a.run, a.surah)
    out, report, changed = pin(idx, a.surah, hmap, parse_pairs(a.pin), parse_pairs(a.trim))
    out["transform"] = {
        **({"truncatedTail": idx["transform"]["truncatedTail"]}
           if isinstance(idx.get("transform"), dict) and idx["transform"].get("truncatedTail") else {}),
        "op": f"heard_pin:{a.surah}", "fromSha256": live, "fromKey": a.key,
        "evidenceRun": str(a.run), "evidenceAudioSha256": hmap.get("sha256"),
        "pins": report, "changedAyahs": changed, "reason": a.reason,
        "at": int(time.time() * 1000), "by": "pin_heard",
        "note": "بدءُ كلّ آيةٍ مثبَّتةٍ أداءٌ مسموعٌ مقيس؛ ما تكرّر قبله بلا مدخل؛ يلزمه الإحصاءُ الشامل.",
    }
    for k in ("reasonCode", "reasonUser"):
        if isinstance(idx.get("transform"), dict) and idx["transform"].get(k):
            out["transform"][k] = idx["transform"][k]
    blob = gzip.compress(json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), 9)
    new_sha = hashlib.sha256(blob).hexdigest()
    target = f"timings-staging/{idx.get('riwaya')}/{idx.get('reciterId')}.{new_sha[:8]}.jz"
    print(f"من {a.key} ({live[:12]}) · س{a.surah} · الخريطة {a.run} ({str(hmap.get('sha256'))[:8]})")
    for r in report:
        print("  📌", r)
    print(f"  آياتٌ تغيّرت حدودُها: {changed}")
    print(f"إلى {target} ({len(blob)} بايت · بصمة {new_sha[:12]})")
    if not a.yes:
        print("(عرضٌ فقط — أضف --yes للرفع)")
        return
    cl.put_object(Bucket=bucket, Key=target, Body=blob, ContentType="application/gzip")
    got = cl.head_object(Bucket=bucket, Key=target)["ContentLength"]
    print(f"↑ رُفع · الدلو {got} · المحلّي {len(blob)} → {'✅' if got == len(blob) else '❌'}")


if __name__ == "__main__":
    main()
