# -*- coding: utf-8 -*-
"""🧠 **أيَرُدُّ النموذجُ الأكبرُ الكلمةَ المحذوفةَ من حفظه؟** — فرضيّةُ «يعرف القرآن أكثرَ من أن يسمعك».

سؤالٌ يولد من نتيجةٍ محيّرة (‏D-350): النموذجُ الأكبرُ **أدقُّ نسخاً** (‏‎+25 نقطةً في الصعب)
و**أقلُّ كشفاً للخطأ** (‏‎−6.3 على النظيف). والظاهرُ أنّ الأدقَّ نسخاً أولى بأن يمسك الخطأ — فما
لم يكن **يصحّحه من عنده**: نموذجٌ أقوى لغويّاً يجرّ النصَّ إلى المحفوظ الصحيح ولو نطق القارئُ
غيرَه. وهذا — إن صحّ — **أخطرُ عيبٍ يمكن أن يُصيب مُسمِّعاً**، لأنّ مقياسَه (دقّةُ النسخ) يرتفع
بينما وظيفتُه (‏أن يقول لك: أخطأتَ) تنهار.

والحَكَمُ حالةُ **الحذف (`OMIT`)**: كلمةٌ **مقصوصةٌ من الصوت** فلا سبيل إلى سماعها. فإن ظهرت في
النسخ فهي **من الحفظ لا من الأذن** — ولا احتمالَ ثالث.

⛔ **وشرطٌ يُشترط كي لا يكون الرقمُ وهماً:** تُستبعد الكلمةُ إن تكرّرت في الآية، وإلّا حُسب
ظهورُها في موضعها الآخر «ردّاً» وهو نسخٌ صحيح.

    python tools/tasmi_bench/restore_probe.py --dirs work/_bg/emu-0:B work/_br/emu-2:B2
"""
import argparse
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import scorer  # noqa: E402

PLAN = os.path.join(HERE, "inject_plan_riwaya.json")


def cfg(riwaya):
    return scorer.Config(strip_yeh_barree=True, dagger_optional=True, naql=riwaya == "warsh",
                         sila=riwaya in ("warsh", "qalun"), mark_sila=True, strict_short=True)


def load(dirs):
    acc = {}
    for spec in dirs:
        d, suf = spec.rsplit(":", 1)
        d = d if os.path.isabs(d) else os.path.join(HERE, d)
        for f in sorted(os.listdir(d)):
            # ⚠️ **ولا يُفترض أنّ كلَّ ما بدأ بالبادئة يحمل `_cap_`:** في `work/` ملفّاتٌ
            # قديمةٌ بأسماءٍ أخرى، فكان `split(...)[1]` يرمي `IndexError` على أوّلها.
            if not (f.startswith("hyps_emu_g3r") and f.endswith(".json") and "_cap_" in f):
                continue
            arm = f[:-5].split("_cap_", 1)[1]
            if arm.endswith("-" + suf):
                arm = arm[: -len(suf) - 1]
            tag = f[:-5].split("hyps_emu_", 1)[1].split("_cap_", 1)[0]
            h = json.load(open(os.path.join(d, f), encoding="utf-8")).get("hyps", {})
            acc.setdefault(arm, {}).update({tag + "/" + k: v for k, v in h.items()
                                            if v.get("text") is not None and "error" not in v})
    return acc


def arms_or_die(acc, names):
    """⛔ **`KeyError` ليس رسالةَ عطب.** يقول الاسمَ المفقود ولا يقول ما الموجود، فيُظنّ العطبُ
    في الأداة وهو في اسمِ ذراعٍ أو مسارِ مجلّد. ⇒ تُسمّى الأذرعُ الحاضرةُ في الرسالة نفسِها."""
    out = []
    for k in names:
        if k not in acc:
            raise SystemExit("⛔ لا ذراعَ باسم " + repr(k) + " — الموجود: "
                             + (" · ".join(sorted(acc)) or "لا شيء")
                             + " ⇒ راجِع --dirs و--arms")
        out.append(acc[k])
    return out


def boot(pairs, seed=7, n=4000):
    rng = random.Random(seed)
    d = []
    for _ in range(n):
        p = [pairs[rng.randrange(len(pairs))] for _ in range(len(pairs))]
        d.append((sum(x[1] for x in p) - sum(x[0] for x in p)) / len(p) * 100)
    d.sort()
    return d[int(0.025 * n)], d[int(0.975 * n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dirs", nargs="+", required=True)
    ap.add_argument("--arms", nargs=2, default=["shipped", "base-ar"])
    a = ap.parse_args()
    plan = {it["id"]: it for it in json.load(open(PLAN, encoding="utf-8"))["items"]}
    acc = load(a.dirs)
    ha, hb = arms_or_die(acc, a.arms)
    keys = sorted(set(ha) & set(hb))

    pairs, skipped, examples = [], 0, []
    for k in keys:
        it = plan.get(k.split("/", 1)[1])
        if not it or it["op"] != "OMIT":
            continue
        c = cfg(it.get("riwaya"))
        tgt = scorer.norm(it["targetWord"], c)
        if not tgt or sum(1 for w in it["refText"].split() if scorer.norm(w, c) == tgt) != 1:
            skipped += 1                      # ⛔ كلمةٌ مكرّرةٌ في الآية: ظهورُها ليس ردّاً
            continue
        v = []
        for h in (ha[k], hb[k]):
            v.append(1 if tgt in [scorer.norm(w, c) for w in h["text"].split()] else 0)
        pairs.append(tuple(v))
        if v == [0, 1] and len(examples) < 3:
            examples.append((k, it["targetWord"]))
    if len(pairs) < 15:
        raise SystemExit(f"⛔ بنودُ الحذف الصالحة {len(pairs)} فقط — لا يُقرأ الصفرُ نتيجةً")

    ra = sum(x[0] for x in pairs) / len(pairs)
    rb = sum(x[1] for x in pairs) / len(pairs)
    lo, hi = boot(pairs)
    print(f"‏بنودُ **الحذف** الصالحة: **{len(pairs)}** (‏استُبعد {skipped} لتكرّر الكلمة في آيتها)\n")
    print("| الذراع | يردّ الكلمةَ المقصوصةَ من حفظه |")
    print("|---|---:|")
    print(f"| `{a.arms[0]}` | {ra*100:.1f}٪ ({sum(x[0] for x in pairs)}/{len(pairs)}) |")
    print(f"| **`{a.arms[1]}`** | **{rb*100:.1f}٪** ({sum(x[1] for x in pairs)}/{len(pairs)}) |")
    print(f"\n**الفرق {(rb-ra)*100:+.1f} نقطة · مجال 95٪ [{lo:+.1f} .. {hi:+.1f}]** ⇒ "
          + ("✅ **الفرضيّةُ تصمد**: الأكبرُ يردّ ما لم يُنطَق." if lo > 0 else
             ("⛔ **الفرضيّةُ تسقط**: لا فرقَ يُعتدّ به." if hi > 0 else "↩️ الأصغرُ يردّ أكثر.")))
    if examples:
        print("\nأمثلةٌ ردَّها الأكبرُ وحدَه: " + " · ".join(f"`{w}` ({i})" for i, w in examples))


if __name__ == "__main__":
    sys.exit(main())
