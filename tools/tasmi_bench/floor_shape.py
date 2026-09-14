#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧱 **شكلُ الأرضيّة** — الاتّهامُ الكاذبُ على تلاواتٍ **صحيحة**: أنَواةٌ أم انتشار؟ ومفردٌ أم سلاسل؟

يقرأ ملفَّ أرضيّةٍ (`results/CLEAN_FLOOR.json` · `results/NOISY_FLOOR.json`) — وهو **سجلُّ كلِّ
كلمةٍ اتُّهمت ظلماً** في مجموعةٍ من التلاوات الصحيحة — ويجيب أربعةَ أسئلةٍ لا يجيبها العدُّ:

1. **أنِتشارٌ أم نواة؟** كم بنداً من بنود المجموعة فيه اتّهامٌ واحدٌ على الأقلّ. فأرضيّةٌ في
   **بندَين** عطبُ مادّةٍ بعينها، وأرضيّةٌ في **كلّ بند** عطبٌ عامٌّ في العدّة.
2. **أمفردٌ أم سلاسل؟** طولُ السلاسل المتّصلة. فالكلمةُ المفردةُ خلطُ سمعٍ، و**سلسلةُ خمسٍ
   متّصلةٍ ضياعُ خطٍّ** — وهما عطبان مختلفان لا يُعالجان بعلاجٍ واحد.
3. ⛔⛔ **وأتشبه الأرضيّةُ خطأَ المستخدم الأخطر؟** سلسلةُ `MISSED` **خالصةٌ** طولُها ≥ 4 هي
   بصمةُ «قارئٌ تخطّى سطراً» بعينها. فإن وُجدت في أرضيّةٍ **كلُّ تلاواتها صحيحة** فكلُّ قاعدةٍ
   تُسكت السلاسلَ **تُعمي المحرّكَ عن التخطّي** — وهو أوجبُ ما يُكشف. **يُعَدُّ ويُعلَن.**
4. **وأينَ تقع؟** أخماسُ الموضع من **طولِ المرجع الحقيقيّ** (مصحفاً)، لا من أقصى مُتَّهَمٍ.

⛔⛔ **والفخُّ الذي وقعتُ فيه أنا ثمّ صار حارساً:** تطبيعُ الموضع بـ«أقصى فهرسٍ متَّهَم»
**يرفع الخُمسَ الأخيرَ بالبناء** (‏أقصى مُتَّهَمٍ في كلّ بندٍ يقع فيه بالضرورة) — فبدا الذيلُ
ثقيلاً وليس بثقيل. ⇒ **فالطولُ يُقرأ من المصحف، وما لم يُقرأ منه يُعَدُّ «مجهولَ الطول»
ولا يُبَنّ**. (`--selftest` يحرس هذا بضابطٍ يسقط لو عاد التطبيعُ الكاذب.)

الاستعمال:
    python tools/tasmi_bench/floor_shape.py results/NOISY_FLOOR.json [results/CLEAN_FLOOR.json]
    python tools/tasmi_bench/floor_shape.py --selftest
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

SKIP_RUN_MIN = 4          # سلسلةُ `MISSED` الخالصةُ من هذا الطول = بصمةُ «تخطّى سطراً»
COLLAPSE_SHARE = 0.60     # عتبةُ حارس الانهيار المشحون (D-268) — تُقرأ ولا تُغيَّر


def _mods():
    """‏`error_triage` ومعه `common` على الطريق — ونداؤه أوّلاً يضع `tools/alignment` في المسار."""
    sys.path.insert(0, HERE)
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "alignment"))
    import error_triage as ET
    ET._mods()
    return ET


def runs_of(idxs):
    """سلاسلُ الفهارس المتّصلة ⇒ قائمةُ قوائمَ (‏كلُّ قائمةٍ فهارسُ سلسلةٍ واحدةٍ مرتَّبة)."""
    out = []
    cur = []
    for i in sorted(set(idxs)):
        if cur and i == cur[-1] + 1:
            cur.append(i)
        else:
            if cur:
                out.append(cur)
            cur = [i]
    if cur:
        out.append(cur)
    return out


def true_lengths(items, ET=None):
    """طولُ مرجعِ كلِّ بندٍ من **المصحف** ⇒ (‏خريطةٌ · قائمةُ مجهولي الطول).

    ⛔ وما تعذّر طولُه **لا يُقدَّر** بأقصى فهرسٍ متَّهَم: يُعَدُّ مجهولاً ويُعلَن.
    """
    if ET is None:
        ET = _mods()
    from common import load_text, load_index
    index = load_index()
    lengths, unknown = {}, []
    for it in items:
        try:
            riw, words = ET.item_words(it, load_text, index)
        except Exception:
            riw, words = None, None
        if words:
            lengths[it] = len(words)
        else:
            unknown.append(it)
    return lengths, unknown


def shape(floor, lengths=None):
    """📐 شكلُ أرضيّةٍ واحدة ⇒ قاموسُ أرقامٍ لا نصّ (‏والنصُّ في `render`)."""
    rows = floor.get("rows") or []
    items_all = list(floor.get("items") or [])
    by = collections.defaultdict(dict)
    for r in rows:
        by[r["item"]][int(r["idx"])] = r.get("status")

    st = {
        "set": floor.get("set"),
        "arm": floor.get("arm"),
        "rows": len(rows),
        "items_all": len(items_all),
        "items_hit": len(by),
        "status": dict(collections.Counter(r.get("status") for r in rows)),
        "riwaya": dict(collections.Counter(r.get("riwaya") for r in rows)),
    }

    # ① الانتشارُ والتركيز
    per = {it: len(m) for it, m in by.items()}
    tot = sum(per.values()) or 1
    order = sorted(per.values(), reverse=True)
    acc = 0
    half_k = 0
    for v in order:
        acc += v
        half_k += 1
        if acc * 2 >= tot:
            break
    st["half_in_k"] = half_k
    st["top1_share"] = round(100.0 * order[0] / tot, 1) if order else 0.0

    # ② السلاسلُ ③ وبصمةُ التخطّي
    hist = collections.Counter()
    words_ge3 = 0
    skip_runs, skip_words = 0, 0
    for it, m in by.items():
        for run in runs_of(m):
            L = len(run)
            hist[L] += 1
            if L >= 3:
                words_ge3 += L
            if L >= SKIP_RUN_MIN and all(m[i] == "MISSED" for i in run):
                skip_runs += 1
                skip_words += L
    st["runs"] = dict(sorted(hist.items()))
    st["runs_total"] = sum(hist.values())
    st["words_in_runs_ge3"] = words_ge3
    st["skip_runs"] = skip_runs
    st["skip_words"] = skip_words

    # ④ الموضعُ والنسبةُ — بالطول الحقيقيّ وحدَه
    lengths = lengths or {}
    bins = [0] * 5
    shares = []
    over_collapse = []
    unknown = 0
    for it, m in by.items():
        L = lengths.get(it)
        if not L or L < 5:
            unknown += len(m)
            continue
        shares.append(len(m) / float(L))
        if len(m) / float(L) >= COLLAPSE_SHARE:
            over_collapse.append(it)
        for i in m:
            b = int(5 * i / L)
            bins[min(4, max(0, b))] += 1
    st["bins"] = bins
    st["pos_unknown"] = unknown
    st["share_median"] = round(sorted(shares)[len(shares) // 2], 3) if shares else None
    st["share_max"] = round(max(shares), 3) if shares else None
    st["over_collapse"] = over_collapse
    return st


def render(st):
    """📝 جدولُ سطرٍ واحدٍ لكلّ سؤال — يُقرأ من الهاتف."""
    L = []
    L.append("| ما قِيس | الرقم | ما يعنيه |")
    L.append("|---|---:|---|")
    hit, all_ = st["items_hit"], st["items_all"]
    pct = (100.0 * hit / all_) if all_ else 0.0
    verdict = "**انتشارٌ لا نواة**" if pct >= 80 else ("نواةٌ في بعض المادّة" if pct <= 40 else "بينهما")
    L.append(f"| ① الانتشار | **{hit}/{all_}** ({pct:.0f}٪) | {verdict} |")
    # 🧮 والتركيزُ يُحكَم بميزانٍ مكتوب: التوزيعُ المتساوي يضع نصفَ الكتلة في **نصف** البنود.
    #    ⇒ فالربعُ وما دونه «تركيزٌ»، وما فوق الثلث «انتشارٌ»، وبينهما «ميلٌ» — ولا ذوقَ.
    #    ⛔ ونسبةٌ من بنودٍ قليلةٍ لا تُحكَم أصلاً (1 من 3 = 33٪ وهو «تساوٍ» بالحساب وبندٌ
    #    واحدٌ يحمل ثلاثةَ أرباعها بالواقع) ⇒ دون ثمانيةِ بنودٍ **لا يُنطَق بحكم**،
    #    وأكبرُ بندٍ يحمل ربعَ الأرضيّة تركيزٌ ولو تساوى الباقي.
    ratio = (float(st["half_in_k"]) / hit) if hit else 0.0
    if hit < 8:
        conc = "عيّنةٌ أصغرُ من أن تُحكَم (‏%d بنداً مصاباً)" % hit
    elif st["top1_share"] >= 25.0 or ratio <= 0.25:
        conc = "**تركيزٌ**: قلّةٌ تحمل نصفَها"
    elif ratio >= 0.33:
        conc = "**مبثوثةٌ**: قريبةٌ من التساوي"
    else:
        conc = "ميلٌ خفيفٌ لا تركيز"
    L.append(f"| ① التركيز | نصفُها في **{st['half_in_k']}** من {hit} بنداً مصاباً ({int(round(ratio*100))}٪) · "
             f"وأكبرُ بندٍ {st['top1_share']}٪ | {conc} |")
    runs = st["runs"]
    shape_txt = " · ".join(f"طول {k}: {v}" for k, v in runs.items())
    L.append(f"| ② السلاسل | {st['runs_total']} سلسلةً — {shape_txt} | "
             f"**{st['words_in_runs_ge3']}** من {st['rows']} كلمةً في سلاسلَ ≥3 |")
    if st["skip_runs"]:
        L.append(f"| ⛔⛔ ③ بصمةُ «تخطّى سطراً» | **{st['skip_runs']}** سلسلةً · {st['skip_words']} كلمةً | "
                 f"`MISSED` خالصةٌ ≥{SKIP_RUN_MIN} **على تلاوةٍ صحيحة** ⇒ كلُّ قاعدةٍ تُسكت السلاسلَ "
                 f"**تُعمي عن التخطّي** |")
    else:
        L.append(f"| ✅ ③ بصمةُ «تخطّى سطراً» | **0** | لا سلسلةَ `MISSED` خالصةً ≥{SKIP_RUN_MIN} "
                 f"⇒ التضاربُ **غيرُ مقيسٍ هنا** (‏ولا يُعمَّم على مجموعةٍ أخرى) |")
    if st["share_median"] is not None:
        oc = len(st["over_collapse"])
        L.append(f"| ④ نسبةُ البند المتَّهَمة | وسيطٌ **{int(round(st['share_median']*100))}٪** · وأقصى {int(round(st['share_max']*100))}٪ | "
                 f"{'✅ ولا بندَ فوق عتبةِ الانهيار %.0f٪ ⇒ الأرضيّةُ **بعد** الحارس' % (COLLAPSE_SHARE * 100) if not oc else '⚠️ و**%d** بنداً فوق %.0f٪ — وحارسُ الانهيار كان يجب أن يُسكتها ⇒ يُفحَص' % (oc, COLLAPSE_SHARE * 100)} |")
        L.append(f"| ④ أخماسُ الموضع | {' · '.join(str(b) for b in st['bins'])} | "
                 f"بالطول الحقيقيّ مصحفاً — ومجهولُ الطول **{st['pos_unknown']}** كلمةً (‏لم يُبَنّ) |")
    else:
        L.append(f"| ④ الموضع | — | **لا طولَ حقيقيّاً** لبندٍ واحد ⇒ لا يُبَنّ شيءٌ (‏ولا يُقدَّر بأقصى متَّهَم) |")
    return "\n".join(L)


# ──────────────────────────── الضوابط ────────────────────────────

def _selftest():
    fails = []

    def ok(cond, msg):
        if not cond:
            fails.append(msg)

    # ① السلاسل
    ok(runs_of([0, 1, 2, 5]) == [[0, 1, 2], [5]], "runs_of: سلسلتان")
    ok(runs_of([3, 3, 4]) == [[3, 4]], "runs_of: المكرَّرُ لا يطيل")
    ok(runs_of([]) == [], "runs_of: الفراغ")

    def floor(rows, items, name="g_test"):
        return {"set": name, "arm": "t", "items": items, "rows": rows, "n": len(rows)}

    def row(it, i, s="SUBSTITUTED"):
        return {"item": it, "idx": i, "riwaya": "warsh", "ref": "x", "heard": None if s == "MISSED" else "y", "status": s}

    # ② بصمةُ التخطّي: أربعُ `MISSED` خالصةٍ تُعَدّ — وثلاثٌ لا
    f = floor([row("a", i, "MISSED") for i in range(4)], ["a", "b"])
    s = shape(f, {"a": 20})
    ok(s["skip_runs"] == 1 and s["skip_words"] == 4, "التخطّي: سلسلةُ أربعٍ خالصةٍ تُعَدّ")
    f3 = floor([row("a", i, "MISSED") for i in range(3)], ["a"])
    ok(shape(f3, {"a": 20})["skip_runs"] == 0, "التخطّي: ثلاثٌ دون الحدّ")
    fm = floor([row("a", 0, "MISSED"), row("a", 1, "MISSED"),
                row("a", 2, "SUBSTITUTED"), row("a", 3, "MISSED")], ["a"])
    ok(shape(fm, {"a": 20})["skip_runs"] == 0, "التخطّي: المختلطةُ ليست بصمة")

    # ③ الانتشارُ والتركيز
    f = floor([row("a", 0), row("b", 0), row("c", 0)], ["a", "b", "c", "d", "e"])
    s = shape(f, {k: 20 for k in "abcde"})
    ok(s["items_hit"] == 3 and s["items_all"] == 5, "الانتشار: 3 من 5")
    f = floor([row("a", i) for i in (0, 2, 4, 6, 8)] + [row("b", 0), row("c", 0)],
              ["a", "b", "c"])
    ok(shape(f, {"a": 20, "b": 20, "c": 20})["half_in_k"] == 1, "التركيز: نصفُها في بندٍ واحد")
    ok("أصغرُ من أن تُحكَم" in render(shape(f, {"a": 20, "b": 20, "c": 20})),
       "التركيز: ثلاثةُ بنودٍ لا تُحكَم — والنسبةُ وحدَها تكذب (‏1/3 = «تساوٍ» وبندٌ يحمل 71٪)")
    # وميزانُ الحكم يُجرَّب طرفاه: متساوٍ تماماً ⇒ «مبثوثة» · وواحدٌ من ثمانٍ ⇒ «تركيز»
    ev = floor([row(c, 0) for c in "abcdefgh"], list("abcdefgh"))
    ok("**مبثوثةٌ**" in render(shape(ev, {c: 20 for c in "abcdefgh"})),
       "الميزان: توزيعٌ متساوٍ يُقرأ مبثوثاً لا مركَّزاً")
    sk = floor([row("a", i) for i in range(0, 16, 2)] + [row(c, 0) for c in "bcdefgh"],
               list("abcdefgh"))
    ok("**تركيزٌ**" in render(shape(sk, {c: 20 for c in "abcdefgh"})),
       "الميزان: بندٌ واحدٌ يحمل نصفَها يُقرأ تركيزاً")

    # ④ الموضعُ — والضابطُ الذي يسقط لو عاد التطبيعُ بأقصى متَّهَم
    f = floor([row("a", 0), row("a", 1)], ["a"])
    s = shape(f, {"a": 10})
    ok(s["bins"] == [2, 0, 0, 0, 0],
       "الموضع: اتّهامان في صدر بندٍ طولُه 10 ⇒ الخُمسُ الأوّلُ وحدَه (‏وبأقصى متَّهَمٍ لصار [1,0,0,0,1])")
    s2 = shape(floor([row("a", 9)], ["a"]), {"a": 10})
    ok(s2["bins"] == [0, 0, 0, 0, 1], "الموضع: آخرُ كلمةٍ في الخُمس الأخير")

    # ⑤ مجهولُ الطول لا يُبَنّ ولا يُقدَّر
    s = shape(floor([row("a", 0), row("z", 3)], ["a", "z"]), {"a": 10})
    ok(s["bins"] == [1, 0, 0, 0, 0] and s["pos_unknown"] == 1,
       "مجهولُ الطول: يُعَدّ ولا يُبَنّ")
    ok(shape(floor([row("z", 0)], ["z"]), {})["share_median"] is None,
       "لا طولَ ⇒ لا وسيطَ نسبةٍ (‏ولا صفرٌ كاذب)")

    # ⑥ عتبةُ الانهيار: بندٌ فوقها يُعلَن ولا يُسكَت
    s = shape(floor([row("a", i) for i in range(7)], ["a"]), {"a": 10})
    ok(s["over_collapse"] == ["a"], "فوق عتبةِ الانهيار ⇒ يُعلَن")
    s = shape(floor([row("a", i) for i in range(5)], ["a"]), {"a": 10})
    ok(s["over_collapse"] == [], "دون العتبةِ ⇒ لا إعلان")

    # ⑦ العدُّ الأساسُ
    s = shape(floor([row("a", 0), row("a", 1, "MISSED")], ["a"]), {"a": 10})
    ok(s["status"] == {"SUBSTITUTED": 1, "MISSED": 1}, "عدُّ الأصناف")
    ok(s["words_in_runs_ge3"] == 0, "سلسلةُ اثنتَين ليست ≥3")
    ok("| ما قِيس |" in render(s), "الجدولُ يُبنى")

    # ⑧ وقراءةُ الأمر: قيمةُ `--md` ليست ملفَّ أرضيّة (‏سقطت الأداةُ بها فعلاً)
    ok(split_argv(["a.json", "--md", "out.md"]) == (["a.json"], "out.md"),
       "‏`--md` وقيمتُها تُفصَلان عن ملفّات الدخل")
    ok(split_argv(["a.json", "b.json"]) == (["a.json", "b.json"], None),
       "بلا `--md`: الملفّانِ كلاهما دخل")
    ok(split_argv(["--md"]) == ([], None), "‏`--md` بلا قيمةٍ لا تُسقط الأداة")
    ok("**0**" in render(shape(floor([row("a", 0)], ["a"]), {"a": 10})),
       "صفرُ بصمةٍ يُكتب صريحاً لا يُسكت عنه")

    print("🧪 ضوابطُ `floor_shape`: %d إخفاقاً" % len(fails))
    for m in fails:
        print("  ⛔", m)
    return 1 if fails else 0


def split_argv(argv):
    """‏(‏ملفّاتُ الأرضيّة · مخرَجُ `--md`) — ⛔ وقيمةُ الخيار **ليست** ملفَّ أرضيّة.

    (‏وقع فعلاً: `--md results/FLOOR_SHAPE.md` قُرئ ملفَّ دخلٍ فسقطت الأداةُ بـ`FileNotFound`.)
    """
    paths, md, skip = [], None, False
    for i, a in enumerate(argv):
        if skip:
            skip = False
            continue
        if a == "--md":
            md = argv[i + 1] if i + 1 < len(argv) else None
            skip = True
        elif not a.startswith("-"):
            paths.append(a)
    return paths, md


def main(argv):
    if "--selftest" in argv:
        return _selftest()
    paths, md_out = split_argv(argv)
    if not paths:
        print(__doc__)
        return 2
    ET = _mods()
    out = []
    for p in paths:
        floor = json.load(open(p, encoding="utf-8"))
        lengths, unknown = true_lengths(floor.get("items") or [], ET)
        st = shape(floor, lengths)
        head = "## 🧱 `%s` — مجموعةُ `%s` · ذراعُ `%s` · **%d** كلمةً متَّهَمةً ظلماً" % (
            os.path.basename(p), st["set"], st["arm"], st["rows"])
        out.append(head)
        if unknown:
            out.append("⚠️ ومجهولُ الطول مصحفاً: **%d** بنداً (%s…) — عُدّ ولم يُبَنّ."
                       % (len(unknown), unknown[0]))
        out.append(render(st))
        out.append("")
    txt = "\n".join(out)
    print(txt)
    if md_out:
        open(md_out, "w", encoding="utf-8").write(txt + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
