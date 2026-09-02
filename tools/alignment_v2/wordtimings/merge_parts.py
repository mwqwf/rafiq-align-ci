# -*- coding: utf-8 -*-
"""دمج أجزاء التوليد المتوازي في ملف واحد **ببراهين رقمية مطبوعة** — أو التحقق من ملف قائم.

كل عملية توليد تكتب جزءها `out/parts/<stem>.part<ID>.jz` ولا تلمس ملف غيرها. هذا
يجمعها بترتيب ثابت (السورة ثم الآية عددياً) بعد **خمسة براهين** كلٌّ يطبع أرقامه
تحته، وأيّ برهان يسقط يمنع الكتابة:

  1. **وحدة المرجع والاصطلاح:** كل جزء بُني على الفهرس نفسه بايتاً-بايتاً
     (`generatedAgainst.sha256` = sha256 ملف الفهرس المعطى) وبنفس `riwaya/reciterId/
     indexing/endsPolicy/engineVersion`.
  2. **لا تكرار ولا مجهول:** آية في جزأين بمحتوى مختلف = تعارض؛ وكل آية موجودة في
     الفهرس وموسومة HIGH.
  3. **عدد المقاطع = الرموز الخام:** `len(words) == len(text[ayah].split())` لكل آية،
     و`subIndex/wordId` متسلسلان بلا ثقب (اصطلاح RAW_TOKENS).
  4. **الاتصال والحصر:** لكل كلمة `startMs <= endMs`، ونهاية كل كلمة = بداية التالية
     (endsPolicy contiguous)، وأول بداية >= بداية الآية في الفهرس، وآخر نهاية = نهايتها.
  5. **معيار القبول المطلق (استقراء = 0 نقطة قطع مخمَّنة):** لا تُكتب آية إلا بمدخل
     `evidence` وكل نقطة قطع بين كلمتين فيها علامةُ نهاية مقيسة من DTW (`interpCuts == 0`)
     ومطابقة حرفية ≥50% ولا كلمة منطوقة بمدى صفري. الرمز الأخير غير المطابق لا يخلق نقطة
     مخمَّنة (مداه بين نهاية مقيسة ونهاية الآية من الفهرس) فيُقبل موسوماً ما دام له مدى.
     ما دونه يُسقَط **ويُعدّ ويُذكر بسببه** — لا تجميل.

ثم يُحسب `coverageScope` **بالأرقام** من الاتحاد الفعلي مقابل HIGH الفهرس لكل بند
من خطة run_plan + بند «المصحف كاملاً»، وتُكتب الترويسة ببرهانها (`acceptance`
و`verification`) وتقرير جانبي `<out>.report.json` بقوائم الساقط.

python merge_parts.py --index <idx.jz> --parts out/parts --out out/wordtimings_husary_qalun.jz
python merge_parts.py --index <idx.jz> --verify-only <file.jz>      # البراهين 1و2و3و4و5 على ملف قائم
"""
import argparse
import glob
import hashlib
import json
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_HERE = os.path.dirname(os.path.abspath(__file__))
_V2 = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(os.path.dirname(_V2), "alignment"))

from common import load_index, load_text, norm, read_jz, write_jz  # noqa: E402

ACCEPTANCE = {
    "rule": "ABSOLUTE_NO_GUESSED_CUT",
    "guessedCutsAllowed": 0,
    "requires": "every cut point between two words is a measured DTW end-mark "
                "(evidence.interpCuts == 0), no spoken token with an empty span, "
                "and >=50% of tokens match exactly; an unmatched LAST token adds no "
                "guessed cut (its span is [measured end of previous word, index end "
                "of ayah]) and is flagged evidence.lastTokenUnmatched",
    "approvedOn": "2026-09-01",
    "rationale": "التخمين لا يُكتب فوق قياس: آية بلا توقيت كلمي أصدق من آية بتوقيت مخترع",
}
HEADER_KEYS = ("riwaya", "reciterId", "indexing", "endsPolicy", "engineVersion")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _sa(aid):
    s, a = aid.split(":")
    return int(s), int(a)


def _plan_items():
    """بنود خطة التغطية (من run_plan) + بند المصحف كاملاً."""
    try:
        import run_plan  # noqa: E402
        items = list(run_plan.PLAN)
    except Exception as ex:  # run_plan يستورد whisper/numpy — لا يُشترط هنا
        print("  ⚠️ تعذّر استيراد خطة run_plan (%s) — البنود: المصحف كاملاً فقط" % ex)
        items = []
    items.append(("المصحف كاملاً (كل HIGH)", lambda sn, an: True))
    return items


def proofs(doc, index_path, ti, text, starts, label):
    """يشغّل البراهين 1..5 على وثيقة ويعيد (verification, admitted, dropped, high)."""
    v = {}
    # ── 1) وحدة المرجع
    idx_sha = sha256_file(index_path)
    ga = doc.get("generatedAgainst") or {}
    v["p1_indexSha256"] = idx_sha
    v["p1_docSha256"] = ga.get("sha256")
    v["p1_ok"] = ga.get("sha256") == idx_sha and all(doc.get(k) for k in HEADER_KEYS)
    print("[%s] برهان 1 وحدة المرجع: فهرس %s… مقابل الوثيقة %s… · الترويسة %s ⇒ %s"
          % (label, idx_sha[:12], str(ga.get("sha256"))[:12],
             {k: doc.get(k) for k in HEADER_KEYS}, "✅" if v["p1_ok"] else "⛔"))
    high = {e["ayahId"]: e for e in ti["entries"]
            if e.get("confBand") == "HIGH" and e.get("startMs") is not None}
    entries = doc.get("entries") or []
    # ── 2) لا مجهول (التكرار بين الأجزاء يُفحص عند الدمج)
    unknown = [e["ayahId"] for e in entries if e["ayahId"] not in high]
    v["p2_unknownOrNotHigh"] = len(unknown)
    print("[%s] برهان 2 كل آية HIGH في الفهرس: مجهولة/غير HIGH = %d %s ⇒ %s"
          % (label, len(unknown), unknown[:5], "✅" if not unknown else "⛔"))
    # ── 3) الرموز الخام
    bad_tok, bad_seq = [], []
    for e in entries:
        sn, an = _sa(e["ayahId"])
        n_raw = len(text[starts[sn] + an - 1].split())
        w = e.get("words") or []
        if len(w) != n_raw:
            bad_tok.append((e["ayahId"], len(w), n_raw))
        if any(w[i].get("subIndex") != i or w[i].get("wordId") != "%s:%d" % (e["ayahId"], i + 1)
               for i in range(len(w))):
            bad_seq.append(e["ayahId"])
    v["p3_tokenMismatch"] = len(bad_tok)
    v["p3_seqMismatch"] = len(bad_seq)
    v["p3_words"] = sum(len(e.get("words") or []) for e in entries)
    print("[%s] برهان 3 مقاطع = رموز خام: %d آية · %d كلمة · مخالفة العدد %d %s · "
          "مخالفة التسلسل %d ⇒ %s"
          % (label, len(entries), v["p3_words"], len(bad_tok), bad_tok[:3], len(bad_seq),
             "✅" if not bad_tok and not bad_seq else "⛔"))
    # ── 4) الاتصال والحصر
    inv, gap, oob, zero = [], [], [], 0
    for e in entries:
        w = e.get("words") or []
        if not w:
            inv.append(e["ayahId"])
            continue
        if any(x["startMs"] > x["endMs"] for x in w):
            inv.append(e["ayahId"])
        if any(w[i]["endMs"] != w[i + 1]["startMs"] for i in range(len(w) - 1)):
            gap.append(e["ayahId"])
        c = high.get(e["ayahId"])
        if c and (w[0]["startMs"] < c["startMs"] or w[-1]["endMs"] != c["endMs"]):
            oob.append(e["ayahId"])
        zero += sum(1 for x in w if x["endMs"] <= x["startMs"])
    v.update({"p4_inverted": len(inv), "p4_nonContiguous": len(gap),
              "p4_outOfIndexSpan": len(oob), "p4_zeroLenWords": zero})
    print("[%s] برهان 4 اتصال وحصر: مقلوب %d · غير متصل %d · خارج مدى الفهرس %d · "
          "كلمات صفرية الطول %d (تُذكر لا تمنع) ⇒ %s"
          % (label, len(inv), len(gap), len(oob), zero,
             "✅" if not inv and not gap and not oob else "⛔"))
    # ── 5) القبول المطلق: **صفر نقطة قطع مخمَّنة**
    # بنية المولّد (generate.py، `DTW_MARKS_WORD_END`): الكلمة j = [نهاية j-1، نهاية j]،
    # فنقطة القطع k (بين الكلمتين k-1 وk) هي علامة نهاية الكلمة k-1 المقيسة. كلمة لم
    # يطابقها المفرِّغ تجعل نقطة القطع **التالية لها** مستقرأة — إلا **الكلمة الأخيرة**:
    # بدايتها نهاية سابقتها المقيسة ونهايتها نهاية الآية من الفهرس، فلا تُخمَّن فيها نقطة.
    # لذلك المقياس الصادق للاستقراء هو عدد نقاط القطع المخمَّنة لا عدد الرموز غير
    # المطابقة (مقيس على الخادم: 264 من 530 كلمة «مستقرأة» كانت الكلمة الأخيرة وحدها).
    admitted, dropped = [], {}
    last_only = 0
    for e in entries:
        ev = e.get("evidence")
        w = e.get("words") or []
        if not ev or not w:
            dropped.setdefault("no-evidence", []).append(e["ayahId"])
            continue
        mx = max(x["conf"] for x in w)
        interp_idx = [x["subIndex"] for x in w if x["conf"] < mx - 1e-9]
        cuts = [j for j in interp_idx if j < len(w) - 1]        # نقاط قطع مخمَّنة
        ev["interpCuts"] = len(cuts)
        # كلمة منطوقة بلا مدى (نهاية = بداية) لا تُظلَّل أبداً وجارتها ابتلعت زمنها —
        # عطب لا برهان (مقيس: علامة نهاية الكلمة قبل الأخيرة تتشبّع عند حافة النافذة
        # فتُلصق على نهاية الآية). الرموز غير المنطوقة (۞ وعلامات الوقف) مداها صفر بحق.
        sn, an = _sa(e["ayahId"])
        raw = text[starts[sn] + an - 1].split()
        zero_speech = [x["subIndex"] for x in w
                       if x["endMs"] <= x["startMs"] and norm(raw[x["subIndex"]])]
        if cuts:
            dropped.setdefault("guessed-cut", []).append(e["ayahId"])
        elif zero_speech:
            dropped.setdefault("zero-length-speech-word", []).append(e["ayahId"])
        elif ev.get("exact", 0) < 0.5 * ev.get("n", len(w)):
            dropped.setdefault("exact<50%", []).append(e["ayahId"])
        else:
            if interp_idx:                          # الأخيرة وحدها: زمنها مقيس الطرفين
                last_only += 1
                ev["lastTokenUnmatched"] = True
                w[-1]["conf"] = mx
            admitted.append(e)
    v["p5_admitted"] = len(admitted)
    v["p5_admittedLastTokenUnmatched"] = last_only
    v["p5_dropped"] = {k: len(x) for k, x in dropped.items()}
    print("[%s] برهان 5 القبول المطلق (صفر نقطة قطع مخمَّنة + مطابقة حرفية ≥50%%): مقبولة %d "
          "(منها %d آخر رمز غير مطابق بطرفين مقيسين) · ساقطة %s"
          % (label, len(admitted), last_only, v["p5_dropped"] or "0"))
    v["structuralOk"] = bool(v["p1_ok"] and not unknown and not bad_tok and not bad_seq
                             and not inv and not gap and not oob)
    return v, admitted, dropped, high


def coverage(admitted, high):
    have = set(e["ayahId"] for e in admitted)
    scope = []
    for name, sel in _plan_items():
        ids = [aid for aid in high if sel(*_sa(aid))]
        cov = sum(1 for aid in ids if aid in have)
        scope.append({"item": name, "covered": cov, "high": len(ids)})
    return scope


def per_surah_missing(admitted, high):
    have = set(e["ayahId"] for e in admitted)
    miss = {}
    for aid in high:
        if aid not in have:
            miss.setdefault(_sa(aid)[0], []).append(aid)
    return {str(k): sorted(vv, key=_sa) for k, vv in sorted(miss.items())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True, help="فهرس الآيات الذي بُنيت عليه الأجزاء")
    ap.add_argument("--parts", help="مجلد الأجزاء .jz أو نمط glob مثل out/parts/wordtimings_X.part*.jz")
    ap.add_argument("--out", help="الملف الموحّد")
    ap.add_argument("--verify-only", help="تحقق من ملف قائم بلا كتابة")
    ap.add_argument("--riwaya", default="qalun")
    args = ap.parse_args()

    ti = read_jz(args.index)
    idx = load_index()
    text = load_text(args.riwaya)
    starts = {s["n"]: s["start"] for s in idx["surahs"]}

    if args.verify_only:
        doc = read_jz(args.verify_only)
        v, admitted, dropped, high = proofs(doc, args.index, ti, text, starts,
                                           os.path.basename(args.verify_only))
        ok = v["structuralOk"] and not dropped
        print("\nالحكم: %s — سنده: بنيوي=%s · ساقط بالقبول المطلق=%s · آيات=%d/%d HIGH · "
              "كلمات=%d" % ("✅ سليم" if ok else "⛔ غير سليم", v["structuralOk"],
                             v["p5_dropped"] or 0, len(admitted), len(high), v["p3_words"]))
        for c in doc.get("coverageScope") or []:
            print("  تغطية · %s: %s/%s" % (c["item"], c["covered"], c["high"]))
        return 0 if ok else 3

    if not (args.parts and args.out):
        ap.error("--parts و--out مطلوبان للدمج")
    # مجلد ⇒ كل *.jz فيه؛ وإلا نمط glob صريح (أجزاء قارئ واحد في مجلد مشترك)
    files = sorted(glob.glob(os.path.join(args.parts, "*.jz"))
                   if os.path.isdir(args.parts) else glob.glob(args.parts))
    if not files:
        print("⛔ لا أجزاء في %s" % args.parts)
        return 1
    print("أجزاء: %d ← %s" % (len(files), [os.path.basename(f) for f in files]))

    base = None
    union, owner, dupes, mismatch = {}, {}, [], []
    for f in files:
        d = read_jz(f)
        name = os.path.basename(f)
        key = tuple(d.get(k) for k in HEADER_KEYS) + ((d.get("generatedAgainst") or {}).get("sha256"),)
        if base is None:
            base, base_key = d, key
        elif key != base_key:
            mismatch.append((name, key))
        n_dup = 0
        for e in d.get("entries") or []:
            aid = e["ayahId"]
            if aid in union:
                if union[aid] != e:
                    dupes.append((aid, owner[aid], name))
                n_dup += 1
                continue
            union[aid] = e
            owner[aid] = name
        print("  %s: %d آية (مكررة %d)" % (name, len(d.get("entries") or []), n_dup))
    print("برهان 1أ اتساق الأجزاء: مخالِفة المرجع/الاصطلاح = %d %s ⇒ %s"
          % (len(mismatch), mismatch[:2], "✅" if not mismatch else "⛔"))
    print("برهان 2أ التكرار: آيات مكررة بمحتوى مختلف = %d %s ⇒ %s"
          % (len(dupes), dupes[:3], "✅" if not dupes else "⛔"))
    if mismatch or dupes:
        print("⛔ لم يُدمج — سند الرفض أعلاه")
        return 2

    merged = dict(base)
    merged["entries"] = sorted(union.values(), key=lambda e: _sa(e["ayahId"]))
    v, admitted, dropped, high = proofs(merged, args.index, ti, text, starts, "الاتحاد")
    if not v["structuralOk"]:
        print("⛔ لم يُكتب — برهان بنيوي ساقط (انظر الأرقام أعلاه)")
        return 3

    scope = coverage(admitted, high)
    missing = per_surah_missing(admitted, high)
    n_missing = sum(len(x) for x in missing.values())
    doc = dict(merged)
    doc["entries"] = admitted
    doc["coverageScope"] = scope
    doc["acceptance"] = ACCEPTANCE
    doc["verification"] = dict(v, mergedAt=int(time.time() * 1000),
                               highTotal=len(high), missingHigh=n_missing)
    doc["mergedFrom"] = [os.path.basename(f) for f in files]
    doc["generatedAt"] = int(time.time() * 1000)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    write_jz(args.out, doc)
    report = {"out": os.path.basename(args.out), "verification": doc["verification"],
              "coverageScope": scope, "dropped": dropped, "missingBySurah": missing}
    with open(args.out + ".report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)

    n_dropped = sum(v["p5_dropped"].values())
    print("\n✅ كُتب %s — %d آية مقبولة من %d HIGH (%.1f%%) · %d كلمة · %d ك.ب"
          % (args.out, len(admitted), len(high), len(admitted) / max(len(high), 1) * 100,
             sum(len(e["words"]) for e in admitted), os.path.getsize(args.out) // 1024))
    print("الساقطة (بلا تجميل): بالقبول المطلق %s · لم يُولَّد لها توقيت أصلاً %d · "
          "مجموع HIGH بلا كلمات %d"
          % (v["p5_dropped"] or "0", n_missing - n_dropped, n_missing))
    for c in scope:
        print("  تغطية · %s: %d/%d (%.1f%%)" % (c["item"], c["covered"], c["high"],
                                                 c["covered"] / max(c["high"], 1) * 100))
    print("التقرير: %s" % (args.out + ".report.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
