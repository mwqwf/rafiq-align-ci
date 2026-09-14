#!/usr/bin/env python3
"""♻️ **إصلاحُ `audit.json` بصور الحاكم بلا إعادة تشغيل whisper** (‏D-292).

`label_audit.py` كان يحسب `match` بتساوٍ صارم مع صورةٍ **واحدة** للكلمة، والحاكمُ المشحون يقبل
صوراً أخرى أُضيفت لأنّ whisper يكتبها ⇒ عتبةُ `--min-match` كانت تُسقط مقاطعَ سليمةً، وبنسبٍ
غيرِ متساوية بين الروايات. أُصلح المدقِّق؛ لكنّ `audit.json` المرفوعَ إلى R2 كُتب بالصارم،
وإعادةُ توليده تكلّف شوطَ whisper كاملاً على المجموعة (ساعاتُ معالجٍ على أربع مهامّ).

ولا حاجة: المقطعُ آيةٌ كاملة، واسمُ ملفّه هو رقمُها (`2_255.flac` ⇐ 2:255 — `prep.py`)، فالنصُّ
المشكولُ الأصليُّ يُستعاد من المصحف يقيناً، وتُعاد المطابقةُ على `hyp` المحفوظ. لا صوتَ ولا نموذج.

    python tools/finetune/audit_rescore.py g0.audit.json [g1.audit.json ...] [--min-match 0.85] [--in-place]

يطبع لكلِّ ملفّ: المتوسّطَ قبل/بعد، وكم مقطعاً كانت العتبةُ تُسقطه **بالمِسطرة لا بالضجيج**،
مفصَّلاً بالرواية. و`--in-place` يكتب `match` المصحَّح (ويحفظ القديم في `match_strict`).
"""
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tasmi_bench"))
sys.path.insert(0, os.path.join(HERE, "..", "alignment"))
import scorer                                    # noqa: E402
from common import load_text                     # noqa: E402

sys.path.insert(0, HERE)
from label_audit import norm, align, ref_forms   # noqa: E402  المدقِّقُ نفسُه (لا نسخةَ ثانية)

COUNTS = [7,286,200,176,120,165,206,75,129,109,123,111,43,52,99,128,111,110,98,135,112,78,118,64,77,227,93,88,69,60,
          34,30,73,54,45,83,182,88,75,85,54,53,89,59,37,35,38,29,18,45,60,49,62,55,78,96,29,22,24,13,14,11,11,18,12,
          12,30,52,52,44,28,28,20,56,40,31,50,40,46,42,29,19,36,25,22,17,19,26,30,20,15,21,11,8,8,19,5,8,8,11,11,8,
          3,9,5,4,7,3,6,3,5,4,5,6]
OFFS = [0]
for c in COUNTS: OFFS.append(OFFS[-1] + c)


def rescore(path, texts, min_match=0.85, in_place=False):
    """♻️ يُعيد تسجيلَ ملفِّ تدقيقٍ واحدٍ — **دالّةٌ تُنادى من الاختبار كما تُنادى من الأمر**.

    ترجع حصيلةً: `n` بنوداً · `done` أُعيد تسجيلُها · `bad_id` تعذّر تحليلُ اسمِه ·
    `ref_mismatch` نصُّه المستعادُ لا يطابق المحفوظ · `by` تفصيلاً بالرواية · `wrote` أكُتب الملفّ.

    ⛔⛔ **ولا تُكتب شهادةٌ على فراغ (‏D-484):** كان العدّان مجموعَين في `miss_key` ويُطبعان
    **تحذيراً**، ثمّ يُكتب «✍ كُتب في مكانه» **ولو لم يُعَد تسجيلُ بندٍ واحد** — فيقرأ المشغّلُ
    أنّ `audit.json` صُلح وهو كما كان، **فيُصفّي عند 0.85 بالأرقام الصارمة** فتعود إليه
    **مِسطرةُ D-292 بعينها** التي أُصلحت (‏وهي التي كانت تُسقط ورشاً وقالون أكثرَ بلا ضجيج).
    ⇒ **صفرُ إعادةٍ = امتناعٌ عن الكتابة وخروجٌ بخطأ.**
    """
    j = json.load(open(path, encoding="utf-8"))
    items = j["items"]
    by, bad_id, ref_mismatch, done = {}, 0, 0, 0
    for it in items:
        rw = it["riwaya"]
        stem = os.path.splitext(it["id"])[0]
        try:
            s, v = map(int, stem.split("_")[:2])
            ref_text = texts[rw][OFFS[s - 1] + v - 1]
        except Exception:
            bad_id += 1
            continue
        # حارسٌ: النصُّ المستعادُ يجب أن يطابق `ref` المحفوظ بالصورة الصارمة، وإلا فالمقطعُ ليس آيتَه
        if " ".join(norm(ref_text)) != it["ref"]:
            ref_mismatch += 1
            continue
        forms = ref_forms(ref_text, rw)
        hyp = it["hyp"].split()
        ok = align(forms, hyp)[0]
        it["match_strict"] = it.get("match_strict", it["match"])   # ⛔ لا يُطمس عند إعادة النداء
        it["match"] = ok / max(len(forms), 1)
        done += 1
        b = by.setdefault(rw, [0, 0.0, 0.0, 0, 0])
        b[0] += 1; b[1] += it["match_strict"]; b[2] += it["match"]
        b[3] += it["match_strict"] < min_match
        b[4] += it["match"] < min_match
    wrote = False
    if in_place and done:
        m = [it["match"] for it in items if "match_strict" in it]
        j["summary"]["mean"] = sum(m) / len(m)
        j["summary"]["below_0.85"] = sum(x < 0.85 for x in m) / len(m)
        j["summary"]["rescored_by"] = "audit_rescore.py (D-292)"
        json.dump(j, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        wrote = True
    return {"n": len(items), "done": done, "bad_id": bad_id,
            "ref_mismatch": ref_mismatch, "by": by, "wrote": wrote}


def selftest():
    """🧪 **حارسُ المُصلِح — بلا صوتٍ ولا نموذجٍ ولا مجموعة** (‏D-484).

    ⚠️ **ولِمَ يُحرَس مُصلِحٌ؟** لأنّه يكتب في `audit.json` الذي **يُصفّى عليه** بناءُ v4:
    خطؤه لا ينفجر — يُنتج مجموعةً منحازةً بصمت، وهو بعينه ما أصلحه D-292.
    """
    import tempfile
    texts = {rw: load_text(rw) for rw in ("hafs", "qalun", "warsh")}
    ref_text = texts["hafs"][OFFS[1] + 254]          # 2:255 — آيةُ الكرسيّ
    ref_strict = " ".join(norm(ref_text))
    ok = True

    def case(name, items, in_place=True, **expect):
        nonlocal ok
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "g0.audit.json")
            json.dump({"summary": {"mean": 0.0}, "items": items}, open(path, "w", encoding="utf-8"),
                      ensure_ascii=False)
            r = rescore(path, texts, 0.85, in_place)
            after = json.load(open(path, encoding="utf-8"))
        good = all(r[k] == v for k, v in expect.items())
        ok &= good
        print(f"{'✅' if good else '❌'} {name}: " +
              " · ".join(f"{k}={r[k]}" for k in ("n", "done", "bad_id", "ref_mismatch", "wrote")))
        return r, after

    base = {"id": "2_255.flac", "riwaya": "hafs", "ref": ref_strict, "hyp": ref_strict, "match": 0.5}
    # ① تلاوةٌ مطابقةٌ ⇒ تُعاد بـ1.0 ويُحفظ القديم
    r, after = case("مطابقٌ يُعاد تسجيلُه", [dict(base)], done=1, bad_id=0, ref_mismatch=0, wrote=True)
    good = abs(after["items"][0]["match"] - 1.0) < 1e-9 and after["items"][0]["match_strict"] == 0.5
    ok &= good
    print(f"{'✅' if good else '❌'} القديمُ محفوظٌ في `match_strict` والجديدُ {after['items'][0]['match']:.3f}")
    good = after["summary"].get("rescored_by", "").startswith("audit_rescore")
    ok &= good
    print(f"{'✅' if good else '❌'} الخلاصةُ مختومةٌ بمن أعادها")

    # ② اسمٌ لا يُحلَّل ⇒ يُعَدّ وحدَه ولا يُخلط بعطبِ النصّ
    case("اسمٌ لا يُحلَّل يُعَدّ وحدَه", [dict(base, id="clip-007.flac")],
         done=0, bad_id=1, ref_mismatch=0, wrote=False)
    # ③ نصٌّ محفوظٌ لا يطابق المستعادَ ⇒ **يُتخطّى** (المقطعُ ليس آيتَه)
    case("نصٌّ لا يطابق يُتخطّى", [dict(base, ref="نصٌّ آخرُ تماماً")],
         done=0, bad_id=0, ref_mismatch=1, wrote=False)
    # ④⛔ **وصفرُ إعادةٍ لا يُكتب ولا يُقرأ سلامةً** — وهذا بندُ D-484 نفسُه
    r, after = case("صفرُ إعادةٍ ⇒ لا كتابةَ البتّة", [dict(base, id="x.flac")],
                    done=0, wrote=False)
    good = "rescored_by" not in after["summary"]
    ok &= good
    print(f"{'✅' if good else '❌'} ولا خَتمَ على ملفٍّ لم يُصلَح")

    # ⑤ إعادةُ النداء لا تطمس `match_strict` (التطبيقُ مرّتين آمن)
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "g0.audit.json")
        json.dump({"summary": {}, "items": [dict(base)]}, open(path, "w", encoding="utf-8"), ensure_ascii=False)
        rescore(path, texts, 0.85, True)
        rescore(path, texts, 0.85, True)
        again = json.load(open(path, encoding="utf-8"))["items"][0]
    good = again["match_strict"] == 0.5 and abs(again["match"] - 1.0) < 1e-9
    ok &= good
    print(f"{'✅' if good else '❌'} نداءان: `match_strict` ما زال {again['match_strict']} (لا يُطمس)")

    # ⑥ ضابطٌ موجَب: تلاوةٌ ناقصةٌ كلمةً ⇒ تطابقٌ دون الواحد (فالمقياسُ يقيس شيئاً)
    short = " ".join(ref_strict.split()[:-3])
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "g0.audit.json")
        json.dump({"summary": {}, "items": [dict(base, hyp=short)]}, open(path, "w", encoding="utf-8"),
                  ensure_ascii=False)
        rescore(path, texts, 0.85, True)
        got = json.load(open(path, encoding="utf-8"))["items"][0]["match"]
    good = 0.8 < got < 1.0
    ok &= good
    print(f"{'✅' if good else '❌'} ضابطٌ موجَب: ثلاثُ كلماتٍ ناقصةٍ ⇒ {got:.3f} (دون الواحد)")

    print("\n" + ("✅ المُصلِحُ يفعل ما يدّعي — ولا يشهد على فراغ" if ok
                  else "❌ المُصلِحُ لا يفعل ما يدّعي"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--min-match", type=float, default=0.85)
    ap.add_argument("--in-place", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.files:
        sys.exit("⛔ لا ملفَّ تدقيقٍ — مرّرْ `g*.audit.json` أو `--selftest`")
    texts = {rw: load_text(rw) for rw in ("hafs", "qalun", "warsh")}
    bad = 0
    for path in a.files:
        r = rescore(path, texts, a.min_match, a.in_place)
        miss = r["bad_id"] + r["ref_mismatch"]
        print(f"\n📄 {os.path.basename(path)} · {r['n']} مقطعاً · أُعيد تسجيلُ {r['done']}"
              + (f" · ⚠ تعذّر ربطُ {miss} (اسمٌ لا يُحلَّل {r['bad_id']} · نصٌّ لا يطابق {r['ref_mismatch']})"
                 if miss else ""))
        print(f"   {'الرواية':8} {'ن':>6} {'متوسّطٌ صارم':>12} {'بصور الحاكم':>12} "
              f"{'يسقط صارماً':>12} {'يسقط بعدُ':>10} {'أُنقذ':>7}")
        tot = [0, 0, 0]
        for rw, (n, ss, sj, ds, dj) in sorted(r["by"].items()):
            print(f"   {rw:8} {n:6d} {ss/n:12.4f} {sj/n:12.4f} "
                  f"{ds:7d} ({100*ds/n:4.1f}٪) {dj:5d} ({100*dj/n:4.1f}٪) {ds-dj:7d}")
            tot[0] += n; tot[1] += ds; tot[2] += dj
        if tot[0]:
            print(f"   {'الكلّ':8} {tot[0]:6d} {'':12} {'':12} "
                  f"{tot[1]:7d} ({100*tot[1]/tot[0]:4.1f}٪) {tot[2]:5d} ({100*tot[2]/tot[0]:4.1f}٪) {tot[1]-tot[2]:7d}")
        if r["wrote"]:
            print("   ✍ كُتب في مكانه (‏`match` بصور الحاكم · `match_strict` القديم محفوظ)")
        elif a.in_place:
            bad += 1
            print("   ⛔ **لم يُكتب شيء: صفرُ مقاطعَ أُعيد تسجيلُها** — ولا تُقرأ هذه سلامةً. "
                  "أهي أسماءُ ملفّاتٍ بصيغةٍ أخرى؟ أم مصحفٌ غيرُ الذي بُنيت به المجموعة؟ (D-484)")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
