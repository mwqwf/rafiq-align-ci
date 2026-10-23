#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""رفعُ التجميد ثمّ الترقيةُ ثمّ إعادةُ التجميد **في عمليّةٍ واحدة** — لا نافذةَ مفتوحةً بينها.

    python tools/ci_fleet/promote_atomic.py <staging key> <old sha8> "<سبب>"

⛔ **العطبُ الذي وُلد منه (مقيسٌ 2026-10-17):** كان الرفعُ والترقيةُ وإعادةُ التجميد
أربعةَ أوامرَ متتابعةً في قناة الأوامر، وبينها ما يصل إلى 30 دقيقةً من الطابور. وفي
تلك النافذة يمرّ `restore_loop` المجدولُ (‏`_try_promote` ⇒ `refreeze.py` «سدٌّ بعد
ترقيةٍ مردودة») فيعيد تجميدَ الهدف قبل أن تبلغه ترقيتُنا ⇒ رُدّت ترقيةُ
`a_albadr` و`swlim` بـ«الهدف مجمَّد» بعد اجتياز كلّ البوّابات.

⚖️ **يُشدّد ولا يُرخي:** الحكمُ كلُّه لـ`promote.py --only <key> --yes` بحُرّاسه دون
تغيير، والرفعُ بسببٍ مكتوب كما يشترط `--unfreeze`، ثمّ يُجمَّد **ما هو منشورٌ فعلاً**
بعدها: الجديدُ إن رُقّي، أو القديمُ إن رُدّ ⇒ لا يبقى الهدفُ مفتوحاً أبداً.
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

ROOT = Path(__file__).resolve().parents[2]
PROM = str(ROOT / "tools" / "index_qa" / "promote.py")
REFREEZE = str(ROOT / "tools" / "ci_fleet" / "refreeze.py")
SHA_GUARD = str(ROOT / "tools" / "index_qa" / "mirror_sha_guard.py")


def guard_mirror(riw: str, rid: str) -> None:
    """بعد كلّ ترقيةٍ ناجحة: يطابق ملفّات مرآة القارئ بـaudioSha256 الفهرس الجديد ويحجب قصاصاتِ ما يخالف.

    ⛔ حجبٌ فقط (رتابيّ) وفي مانيفست المرآة وحده؛ ولا يُفشل الترقيةَ ولا يُلغيها — الفهرسُ سليمٌ والحجبُ
    مجرّد وقايةٍ للمنزَّل (مقيس 2026-10-23: 22 سورةً بقصاصاتٍ على صوتٍ غيرِ ما بُني عليه الفهرس).
    """
    rc = run(SHA_GUARD, "apply", "--only", f"{riw}/{rid}", "--verify-size")
    print(f"🛡️ حارسُ بصمة المرآة لـ{riw}/{rid}: rc={rc}" + ("" if rc == 0 else " — راجِع المخرَج أعلاه"))


def run(*args) -> int:
    return subprocess.run([sys.executable, *args], cwd=str(ROOT), text=True).returncode


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__); return 2
    key, old, reason = sys.argv[1:]
    parts = key.split("/")                        # timings-staging/<riw>/<rid>.<sha8>.jz
    if len(parts) != 3 or not parts[0] == "timings-staging" or not reason.strip():
        print("⛔ مفتاحٌ غيرُ صالح أو سببٌ فارغ"); return 2
    riw, fn = parts[1], parts[2]
    rid, new = fn.split(".")[0], fn.split(".")[1]
    target = f"timings/{riw}/{rid}.jz"
    # الأصلُ يجب أن يكون المتوقَّع قبل أيّ رفع: رفعٌ على أصلٍ تبدّل يُرقّي فوق ما لم نفحصه
    if run(REFREEZE, target, old, "تحقّقٌ من الأصل قبل الرفع") != 0:
        print("⛔ الأصلُ تبدّل — لا رفعَ ولا ترقية"); return 3
    if run(PROM, "--unfreeze", target, "--reason", reason) != 0:
        print("⛔ تعذّر رفعُ التجميد — لا ترقية"); return 4
    rc = run(PROM, "--only", key, "--yes")
    # يُجمَّد المنشورُ فعلاً بعدها أيّاً كان: الجديد إن رُقّي وإلا القديم
    if run(REFREEZE, target, new, "تجميدٌ بعد ترقية " + new) == 0:
        print(f"✅ رُقّي {target} ⇒ {new}")
        guard_mirror(riw, rid)
        return 0
    r2 = run(REFREEZE, target, old, "إعادةُ تجميد " + old + " بعد ترقيةٍ مردودة — لا هدفَ مفتوح")
    print(f"⛔ لم يُرقَّ (rc={rc}) · أُعيد تجميدُ {old}: {'نعم' if r2 == 0 else 'لا — راجِع فوراً'}")
    return 1 if r2 == 0 else 5


if __name__ == "__main__":
    sys.exit(main())
