#!/usr/bin/env python3
"""🩹 **إعادةُ كتابة `target_text` في بيان المجموعة بعد إصلاحٍ في `prep.target_text`** — بلا إعادة قصِّ الصوت.

    python tools/finetune/fix_targets.py [--manifest /content/data/manifest.jsonl] [--dry-run]
    python tools/finetune/fix_targets.py --selftest

⛔⛔ **ولماذا صار يكتب ذرّيّاً (‏D-488 · 2026-09-14):** كان يفتح البيانَ نفسَه بـ`open(p,"w")`
**فيمحوه أوّلاً ثمّ يكتب**: انقطاعٌ في المنتصف (‏نفادُ ذاكرةٍ · قتلُ خليّة كولاب · قرصٌ امتلأ)
يترك **بياناً مبتوراً** — و**عناوينُ المجموعة كلِّها فيه**. والقاعدةُ مكتوبةٌ في العدّة نفسِها
منذ `label_audit.dump` («يُكتب بذرّيّةٍ كي لا يترك القتلُ في منتصف الكتابة ملفّاً مبتوراً»)
**ولم تُطبَّق هنا** — وهذا ملفٌّ **يكتب في العناوين** لا يقرؤها.

⚠️ **وصفرُ صفوفٍ لا يُكتب**: بيانٌ فارغٌ أو مسارٌ خطأ كان يُنتج ملفّاً فارغاً ورسالةَ
«rewritten 0 of 0» تُقرأ نجاحاً. ⇒ يمتنع ويخرج بخطأ.
"""
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, "/content")          # كولاب: `prep.py` منسوخٌ هناك
from prep import target_text            # noqa: E402

DEFAULT = "/content/data/manifest.jsonl"


def retarget(rows):
    """يُعيد حساب `target_text` لكلّ صفٍّ — **دالّةٌ صرفةٌ تُنادى من الاختبار**.

    ترجع (الصفوفُ بعد التعديل · عددُ ما تغيّر · عددُ ما لا مرجعَ نصّيَّ له).
    """
    changed = no_ref = 0
    out = []
    for r in rows:
        r = dict(r)
        if "ref_text" not in r:
            no_ref += 1                 # ⛔ يُعَدّ ولا يُطمس: صفٌّ بلا مرجعٍ لا يُعاد هدفُه
            out.append(r)
            continue
        t = target_text(r["ref_text"])
        if t != r.get("target_text"):
            r["target_text"] = t
            changed += 1
        out.append(r)
    return out, changed, no_ref


def write_atomic(path, rows):
    """يكتب بـ`tmp` ثمّ `os.replace` — **فالقتلُ في المنتصف لا يترك بياناً مبتوراً**."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def selftest():
    """🧪 حارسُ المُصلِح — بلا مجموعةٍ ولا صوت (‏D-488)."""
    import tempfile
    ok = True

    def say(good, line):
        nonlocal ok
        ok &= bool(good)
        print(("✅ " if good else "❌ ") + line)

    ref = "ٱلْحَمْدُ لِلَّهِ"
    good_t = target_text(ref)
    rows = [{"ref_text": ref, "target_text": "قديمٌ خطأ"},
            {"ref_text": ref, "target_text": good_t},
            {"target_text": "بلا مرجع"}]
    out, changed, no_ref = retarget(rows)
    say(changed == 1 and no_ref == 1 and out[0]["target_text"] == good_t,
        f"إعادةُ الهدف: تغيّر {changed} · بلا مرجعٍ {no_ref} · والسليمُ لم يُمَسّ")
    say(rows[0]["target_text"] == "قديمٌ خطأ", "ولا يُعدَّل المدخلُ في مكانه (نسخةٌ لا مسخ)")

    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "m.jsonl")
        write_atomic(p, out)
        say(not os.path.exists(p + ".tmp"), "الكتابةُ ذرّيّةٌ: لا بقيّةَ `.tmp`")
        back = [json.loads(l) for l in open(p, encoding="utf-8")]
        say(len(back) == 3 and back[0]["target_text"] == good_t,
            f"والمقروءُ بعدها {len(back)} صفوفٍ سليمةُ الترميز")
        # ⛔ والملفُّ القديمُ لا يُمسّ إلا عند النجاح: نكتب فوقَه ونتحقّق
        write_atomic(p, back[:2])
        say(len([1 for _ in open(p, encoding="utf-8")]) == 2, "والكتابةُ فوقَه تُبدّله كاملاً لا جزئيّاً")

    # ⛔ صفرُ صفوفٍ: لا كتابةَ ولا شهادة (يُفحص في `main` — ويُحاكى هنا)
    out0, ch0, _ = retarget([])
    say(not out0 and ch0 == 0, "وصفرُ صفوفٍ يُعطي صفراً — و`main` يرفض الكتابة عليه")

    print("\n" + ("✅ المُصلِحُ يكتب ذرّيّاً ولا يشهد على فراغ" if ok else "❌ المُصلِحُ لا يفعل ما يدّعي"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=DEFAULT, help=f"بيانُ المجموعة (الافتراض {DEFAULT})")
    ap.add_argument("--dry-run", action="store_true", help="يقيس ولا يكتب — وهو ما يُبدأ به في ملفٍّ يكتب العناوين")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not os.path.exists(a.manifest):
        sys.exit(f"⛔ لا بيانَ في {a.manifest} — مرّرْ `--manifest` أو `--selftest`")
    rows = [json.loads(l) for l in open(a.manifest, encoding="utf-8") if l.strip()]
    if not rows:
        sys.exit("⛔ **صفرُ صفوفٍ في البيان** — ولا يُكتب شيء، ولا تُقرأ هذه سلامةً (D-488)")
    out, changed, no_ref = retarget(rows)
    print(f"{'(قياسٌ فقط) ' if a.dry_run else ''}أُعيد هدفُ **{changed}** من {len(rows)} صفّاً"
          + (f" · ⚠️ بلا `ref_text`: {no_ref}" if no_ref else ""))
    if a.dry_run:
        return 0
    write_atomic(a.manifest, out)       # ⛔ ذرّيّاً — انظر رأسَ الملفّ
    print(f"✍ كُتب ذرّيّاً في {a.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
