#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني دليلَ `--timing-evidence` لسورةٍ من شاهدَي Whisper عامَّين بمسحٍ يُصنّف كلَّ آيةٍ غطّاها الشاهدان، ويختار المسابيرَ بقاعدةٍ ثابتة.

    python tools/index_qa/timing_evidence_scan.py --surah 10 --riwaya qalun --audio-sha <64hex> \\
        --runs 111111,222222 --witness-artifacts ops/out/a.txt,ops/out/b.txt \\
        --entries ops/out/entries.txt --out ops/evidence/timing-x.json --report ops/evidence/timing-x-scan.json

⚖️ يعمل **محلّيّاً على مخرَجات الشواهد العامّة وحدَها**: لا دلوَ ولا سرَّ ولا شبكة (يقرأ ملفّاتٍ نصّيّةً في المستودع). ولا يمسّ `timing_repair.py`
ولا `W_K` ولا تشابهاً تقريبيّاً؛ فالبوّابةُ تعيد التحقّقَ من مضمون الدليل بدالّتها هي (‏`timing_repair.evidence_error`) بعد البناء.

التصنيف (‏لكلّ آيةٍ في نافذةٍ لدى الشاهدين معاً)، لكلّ شاهدٍ على حدة ثمّ بالاتّفاق:
  «في موضعها»      — `heard_gate._witness_eval` نفسُها تؤكّد أنّ نصّ الآية مسموعٌ عند بدئها المنشور؛
  «منحرفة مثبتة»   — `timing_repair.drift_error` نفسُها تؤكّد أنّ عند بدئها المنشور نصَّ آيةٍ أخرى واحدةٍ بعينها (W_K كلماتٍ متّصلة بثقة `_span_ok`)؛
  «غير محسومة»     — ما سوى ذلك (‏خلافٌ بين الشاهدين · آيتان محتملتان · تكرارٌ · لا تغطية كافية).
المسابير: الأولى والوسطى والأخيرة من «المنحرفة المثبتة» بقاعدةٍ ثابتةٍ غيرِ متجاورة (‏`pick_probes`) — لا بيدٍ ولا بانتقاءٍ بعد النتيجة.
الشرط (٤): إن زادت «في موضعها» على «المنحرفة المثبتة» فلا تُحجب السورةُ كاملةً (‏يُرفض البناء برمز 3) ويُحجب العنقودُ بـ`drop_ayahs`.
التغطية: إن غطّى الشاهدان معاً أقلَّ من ثلاثة أرباع آيات السورة رُدّ البناءُ برمز 5 (‏العنقودُ المغطّى بـ`drop_ayahs`).

⭐ `--kind end` (‏دليلُ «نهاية المدخل» لـ`drop_ayahs` · موافقةُ القائد 2026-11-10): لآياتٍ مسمّاةٍ بـ`--ayahs` يبني سجلَّ
`{"kind": "end", probe, witnesses, heard, method, detail}` لكلّ آيةٍ سمع الشاهدان معاً عند **آخر لحظةٍ من مدخلها المنشور**
نصَّ آيةٍ أخرى واحدةٍ بعينها — والحكمُ لـ`timing_repair.end_drift_error` نفسِها بنصّ `heard_gate.disputed_ref_words` (‏دالّةِ البوّابة)،
ثمّ يُعاد كلُّ سجلٍّ مبنيٍّ على `timing_repair.end_record_error` قبل كتابته. وما لم يثبت عند الشاهدين معاً لا يُكتب له دليل.
"""
from __future__ import annotations

import argparse
import math
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

SRC_KEYS = ("surah", "riwaya", "fileRef", "sha256", "model", "computeType", "ayahs")
IN_PLACE, PROVEN, UNDECIDED = "في موضعها", "منحرفة مثبتة", "غير محسومة"
MIN_PROBES = 3
MIN_COVER_NUM, MIN_COVER_DEN = 3, 4                                # حجبُ السورة كاملةً يلزمه تغطيةُ الشاهدين معاً لثلاثة أرباع آياتها (أمر القائد 2026-11-10)
RUN_RE = re.compile(r"[1-9]\d{5,14}")


def load_artifact(path):
    """سجلُّ الشاهد من مخرَج `show_artifact.py` المحفوظ نصّاً (‏السطرُ الذي يبدأ بـ{"surah"…) أو من ملفّ JSON."""
    t = Path(path).read_text(encoding="utf-8")
    if t.lstrip().startswith("{"):
        return json.loads(t)
    i = t.find('{"surah"')
    if i < 0:
        raise SystemExit(f"⛔ لا سجلَّ شاهدٍ في {path}")
    return json.loads(t[i:].split("\n", 1)[0])


def load_starts(path, surah):
    """{آية: بدءٌ منشور} من مخرَج `show_entries.py` («س:آ<TAB>بدء<TAB>نهاية…»)."""
    out = {}
    for ln in Path(path).read_text(encoding="utf-8").splitlines():
        m = re.match(rf"\s*{surah}:(\d+)\t(\d+)\t(\d+)", ln)
        if m:
            out[int(m.group(1))] = int(m.group(2))
    return out


def gram_index(surah, riwaya, ref_words, n_ayahs):
    """{W_K كلماتٍ متّصلة: {الآيات}} من النصّ المرجعيّ — تصفيةٌ مسبقةٌ لا حكم: الحكمُ لـ`drift_error` وحدَها على ما تُبقيه."""
    import pin_heard as PH                                            # noqa: PLC0415
    k, idx = PH.W_K, {}
    for o in range(1, n_ayahs + 1):
        w = list(ref_words(riwaya, surah, o))
        for i in range(len(w) - k + 1):
            idx.setdefault(tuple(w[i:i + k]), set()).add(o)
    return idx


def drift_candidates(src, t, idx):
    """الآياتُ التي يقع نصٌّ متّصلٌ منها حرفاً في ما سمعه الشاهدُ عند الزمن t (‏فوقُها يُستدعى `drift_error`)."""
    import heard_gate as HG                                           # noqa: PLC0415
    import pin_heard as PH                                            # noqa: PLC0415
    k, out = PH.W_K, set()
    for rec in (src.get("ayahs") or {}).values():
        tk = HG._wtoks(rec)
        for i in range(len(tk) - k + 1):
            span = tk[i:i + k]
            if span[0][1] <= t < span[-1][2]:
                out |= idx.get(tuple(x[0] for x in span), set())
    return out


def witness_state(src, surah, a, starts, riwaya, ref_words, n_ayahs, want_sha, idx=None):
    """حالةُ الآية `a` عند شاهدٍ واحد: ("own",) · ("drift", o) · ("ambiguous",) · ("none",) · ("uncovered",) · ("invalid", سبب)."""
    import heard_gate as HG                                           # noqa: PLC0415
    import timing_repair as T                                         # noqa: PLC0415
    if str(a) not in (src.get("ayahs") or {}):
        return ("uncovered",)
    g_map = {"sha256": want_sha, "fileRef": src.get("fileRef")}
    res, bad = HG._witness_eval(src, surah, g_map, want_sha, riwaya, starts, [a], ref_words)
    if bad:
        return ("invalid", str(bad))
    own = bool(res.get(a, (False, ""))[0])
    t = int(starts[a])
    idx = idx if idx is not None else gram_index(surah, riwaya, ref_words, n_ayahs)
    drift = sorted(o for o in drift_candidates(src, t, idx) if o != a and T.drift_error(
        src, surah, {"ayah": a, "heardAyah": o, "startMs": t}, riwaya, ref_words) is None)
    if own and drift:
        return ("ambiguous",)                                         # تكرارٌ في الصوت: لا حكم
    if own:
        return ("own",)
    if len(drift) == 1:
        return ("drift", drift[0])
    return ("ambiguous",) if drift else ("none",)


def classify(srcs, surah, starts, riwaya, ref_words, n_ayahs, want_sha):
    """{آية: (التصنيف، heardAyah أو None)} للآيات المغطّاة عند الشاهدين معاً؛ وما لم يغطّه أحدُهما يُهمل."""
    out, idx = {}, gram_index(surah, riwaya, ref_words, n_ayahs)
    for a in sorted(starts):
        sts = [witness_state(s, surah, a, starts, riwaya, ref_words, n_ayahs, want_sha, idx) for s in srcs]
        if any(x[0] == "uncovered" for x in sts):
            continue
        if all(x == ("own",) for x in sts):
            out[a] = (IN_PLACE, None)
        elif all(x[0] == "drift" for x in sts) and len({x[1] for x in sts}) == 1:
            out[a] = (PROVEN, sts[0][1])
        else:
            out[a] = (UNDECIDED, None)
    return out


def pick_probes(proven):
    """القاعدةُ الثابتة: الأولى والوسطى والأخيرة من المثبتة، غيرَ متجاورة؛ وما تعذّر استُكمل بالأقدم فالأقدم. أقلُّ من ثلاثٍ ⇒ None."""
    p = sorted(proven)
    if len(p) < MIN_PROBES:
        return None
    pick = []
    for c in (p[0], p[len(p) // 2], p[-1]):
        if all(abs(c - q) >= 2 for q in pick):
            pick.append(c)
    for c in p:
        if len(pick) >= MIN_PROBES:
            break
        if all(abs(c - q) >= 2 for q in pick):
            pick.append(c)
    return sorted(pick) if len(pick) == MIN_PROBES else None


def build(srcs, runs, surah, starts, riwaya, ref_words, n_ayahs, want_sha):
    """(سجلُّ الدليل أو None، تقريرُ المسح، رمزُ الخروج 0/3/4)."""
    if len(runs) != 2 or len(set(runs)) != 2 or not all(RUN_RE.fullmatch(str(r)) for r in runs):
        raise SystemExit("⛔ يلزم معرّفا تشغيلتين قانونيّان متمايزان")
    cls = classify(srcs, surah, starts, riwaya, ref_words, n_ayahs, want_sha)
    proven = sorted(a for a, (c, _) in cls.items() if c == PROVEN)
    own = sorted(a for a, (c, _) in cls.items() if c == IN_PLACE)
    undec = sorted(a for a, (c, _) in cls.items() if c == UNDECIDED)
    rep = {"surah": surah, "runs": [str(r) for r in runs], "counts": {PROVEN: len(proven), IN_PLACE: len(own), UNDECIDED: len(undec)},
           PROVEN: proven, IN_PLACE: own, UNDECIDED: undec, "probes": None, "verdict": None}
    need = math.ceil(n_ayahs * MIN_COVER_NUM / MIN_COVER_DEN)
    rep["coverage"] = {"covered": len(cls), "ayahs": n_ayahs, "need": need}
    if len(cls) < need:                                               # التغطية: لا حكمَ على سورةٍ لم يُسمع ربعُها
        rep["verdict"] = (f"coverage: غطّى الشاهدان معاً {len(cls)} من {n_ayahs} آية (يلزم {need}) — "
                          "لا حجبَ كاملاً للسورة، العنقودُ المغطّى بـdrop_ayahs")
        return None, rep, 5
    if len(own) > len(proven):                                        # الشرط (٤)
        rep["verdict"] = "cluster_only: «في موضعها» أكثر من «المنحرفة المثبتة» — لا حجبَ كاملاً للسورة، العنقودُ بـdrop_ayahs"
        return None, rep, 3
    pick = pick_probes(proven)
    if pick is None:
        rep["verdict"] = f"insufficient: أقلُّ من {MIN_PROBES} آياتٍ منحرفةٍ مثبتةٍ غيرِ متجاورة ({len(proven)} مثبتة)"
        return None, rep, 4
    rep["probes"] = pick
    rep["verdict"] = "ok"
    probes = [{"ayah": a, "startMs": int(starts[a]), "heardAyah": cls[a][1]} for a in pick]
    wits = {str(r): {k: s.get(k) for k in SRC_KEYS} for r, s in zip(runs, srcs)}
    return {"probes": probes, "witnesses": wits}, rep, 0


def load_ends(path, surah):
    """{آية: نهايةٌ منشورة} من مخرَج `show_entries.py` («س:آ<TAB>بدء<TAB>نهاية…»)."""
    out = {}
    for ln in Path(path).read_text(encoding="utf-8").splitlines():
        m = re.match(rf"\s*{surah}:(\d+)\t(\d+)\t(\d+)", ln)
        if m:
            out[int(m.group(1))] = int(m.group(3))
    return out


def _end_spans(src, e):
    """مقاطعُ W_K كلماتٍ متّصلةٍ تغطّي آخرَ لحظةٍ من المدخل (‏endMs−1) عند شاهدٍ واحد: [(كلمات، نافذة)]."""
    import heard_gate as HG                                           # noqa: PLC0415
    import pin_heard as PH                                            # noqa: PLC0415
    k, out = PH.W_K, []
    for rec in (src.get("ayahs") or {}).values():
        tk = HG._wtoks(rec)
        for i in range(len(tk) - k + 1):
            span = tk[i:i + k]
            if span[0][1] < e <= span[-1][2]:
                out.append(tuple(x[0] for x in span))
    return out


def end_witness_state(src, surah, a, ends, riwaya, ref_words, idx, want_sha):
    """حالةُ نهاية الآية `a` عند شاهدٍ واحد: ("end", o, نصّ) · ("ambiguous",) · ("none",) · ("uncovered",) · ("invalid", سبب)."""
    import pin_heard as PH                                            # noqa: PLC0415
    import timing_repair as T                                         # noqa: PLC0415
    if src.get("sha256") != want_sha:
        return ("invalid", "بصمةُ الصوت غيرُ audioSha256 للسورة")
    if src.get("model") not in PH.W_MODELS or src.get("computeType") != "float32":
        return ("invalid", "نموذجٌ غيرُ مقبول")
    e = int(ends[a])
    spans = _end_spans(src, e)
    if not spans:
        return ("uncovered",)
    cands = set()
    for w in spans:
        cands |= idx.get(w, set())
    ok = sorted(o for o in cands if o != a and T.end_drift_error(
        src, surah, {"ayah": a, "heardAyah": o, "endMs": e}, riwaya, ref_words) is None)
    if len(ok) == 1:
        oth = list(ref_words(riwaya, surah, ok[0]))
        txt = next(" ".join(w) for w in spans if any(list(w) == oth[j:j + len(w)] for j in range(len(oth) - len(w) + 1)))
        return ("end", ok[0], txt)
    return ("ambiguous",) if ok else ("none",)


def build_end(srcs, runs, surah, ends, ayahs, riwaya, ref_words, n_ayahs, want_sha, idx_meta):
    """({"س:آ": سجلُّ دليل النهاية}، تقرير، رمز 0/4). `idx_meta` = {riwaya, audioSha256} للتحقّق بـ`end_record_error`."""
    import timing_repair as T                                         # noqa: PLC0415
    if len(runs) != 2 or len(set(runs)) != 2 or not all(RUN_RE.fullmatch(str(r)) for r in runs):
        raise SystemExit("⛔ يلزم معرّفا تشغيلتين قانونيّان متمايزان")
    gidx = gram_index(surah, riwaya, ref_words, n_ayahs)
    out, rep = {}, {"surah": surah, "kind": T.END_KIND, "runs": [str(r) for r in runs], "proven": [], "unproven": {}}
    for a in sorted(ayahs):
        if a not in ends:
            rep["unproven"][str(a)] = "لا مدخلَ منشورٌ للآية"
            continue
        sts = [end_witness_state(s, surah, a, ends, riwaya, ref_words, gidx, want_sha) for s in srcs]
        if not (all(x[0] == "end" for x in sts) and len({x[1] for x in sts}) == 1):
            rep["unproven"][str(a)] = " · ".join(f"{r}:{x[0]}" for r, x in zip(runs, sts))
            continue
        o, e = sts[0][1], int(ends[a])
        src0 = srcs[0]
        rec = {"method": "whisper", "kind": T.END_KIND,
               "detail": (f"شاهدا Whisper {src0.get('model')} {src0.get('computeType')} (التشغيلتان {runs[0]} و{runs[1]}) سمعا عند "
                          f"آخر لحظةٍ من المدخل المنشور (نهايته {e}م.ث) نصَّ الآية {surah}:{o} لا نصَّ {surah}:{a} "
                          "(W_K كلماتٍ متّصلة بثقة _span_ok عند الشاهدين معاً بدالّة timing_repair.end_drift_error)"),
               "heard": {"witness": f"whisper_witness.yml {src0.get('model')} {src0.get('computeType')}",
                         "runId": int(runs[0]), "text": sts[0][2]},
               "probe": {"ayah": a, "heardAyah": o, "endMs": e},
               "witnesses": {str(r): {k: s.get(k) for k in SRC_KEYS} for r, s in zip(runs, srcs)}}
        why = T.end_record_error(idx_meta, surah, a, rec, ref_words)  # ⭐ دالّةُ البوّابة نفسُها قبل الكتابة
        if why:
            rep["unproven"][str(a)] = f"end_record_error: {why}"
            continue
        out[f"{surah}:{a}"] = rec
        rep["proven"].append(a)
    rep["verdict"] = "ok" if out else "insufficient: لا آيةَ أثبت الشاهدان معاً أنّ نهايةَ مدخلها في صوت غيرها"
    return out, rep, (0 if out else 4)


def main_end(a):
    """`--kind end`: دليلُ نهاية المدخل لآياتٍ مسمّاة بصيغة drop_ayahs (‏مفاتيحُه «س:آ»)."""
    import heard_gate as HG                                           # noqa: PLC0415
    import promote                                                    # noqa: PLC0415
    if not a.ayahs:
        raise SystemExit("⛔ --kind end يلزمه --ayahs")
    ayahs = sorted({int(x) for x in a.ayahs.replace("،", ",").split(",") if x.strip()})
    runs = [x.strip() for x in a.runs.split(",")]
    srcs = [load_artifact(p.strip()) for p in a.witness_artifacts.split(",")]
    if len(srcs) != 2:
        raise SystemExit("⛔ يلزم شاهدان")
    n = promote._AYAH_COUNTS[a.surah - 1]
    shas = [None] * 114
    shas[a.surah - 1] = a.audio_sha
    out, rep, code = build_end(srcs, runs, a.surah, load_ends(a.entries, a.surah), ayahs, a.riwaya,
                               HG.disputed_ref_words, n, a.audio_sha, {"riwaya": a.riwaya, "audioSha256": shas})
    outp = Path(a.report)
    rp = json.loads(outp.read_text(encoding="utf-8")) if outp.exists() else {}
    rp[f"end:{a.surah}"] = rep
    outp.write_text(json.dumps(rp, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: rep[k] for k in ("surah", "kind", "proven", "unproven", "verdict")}, ensure_ascii=False))
    if out:
        ep = Path(a.out)
        ev = json.loads(ep.read_text(encoding="utf-8")) if ep.exists() else {}
        ev.update(out)
        ep.write_text(json.dumps(ev, ensure_ascii=False, indent=1), encoding="utf-8")
    return code


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--surah", type=int, required=True)
    ap.add_argument("--riwaya", required=True)
    ap.add_argument("--audio-sha", required=True, help="audioSha256 للسورة في الفهرس (64 خانة)")
    ap.add_argument("--runs", required=True, help="تشغيلتان بفاصلة")
    ap.add_argument("--witness-artifacts", required=True, help="ملفّان بفاصلة بترتيب --runs")
    ap.add_argument("--entries", required=True, help="مخرَج show_entries.py للفهرس المنشور")
    ap.add_argument("--out", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--kind", choices=("start", "end"), default="start",
                    help="start (الافتراض: دليلُ انحراف البدء لـdrop_surah كما هو) · end: دليلُ نهاية المدخل لآياتٍ مسمّاةٍ لـdrop_ayahs")
    ap.add_argument("--ayahs", default="", help="--kind end: أرقامُ الآيات في السورة بفاصلة (مثل 24,27)")
    a = ap.parse_args(argv)
    if a.kind == "end":
        return main_end(a)
    import pin_heard as PH                                            # noqa: PLC0415
    import promote                                                    # noqa: PLC0415
    runs = [x.strip() for x in a.runs.split(",")]
    srcs = [load_artifact(p.strip()) for p in a.witness_artifacts.split(",")]
    if len(srcs) != 2:
        raise SystemExit("⛔ يلزم شاهدان")
    n = promote._AYAH_COUNTS[a.surah - 1]
    rec, rep, code = build(srcs, runs, a.surah, load_starts(a.entries, a.surah), a.riwaya, PH.ref_words_for, n, a.audio_sha)
    outp, repp = Path(a.report), None
    rp = json.loads(outp.read_text(encoding="utf-8")) if outp.exists() else {}
    rp[str(a.surah)] = rep
    outp.write_text(json.dumps(rp, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"surah": a.surah, **{k: rep[k] for k in ("counts", "probes", "verdict")}}, ensure_ascii=False))
    if rec is None:
        return code
    ep = Path(a.out)
    ev = json.loads(ep.read_text(encoding="utf-8")) if ep.exists() else {}
    ev[str(a.surah)] = rec
    ep.write_text(json.dumps(ev, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
