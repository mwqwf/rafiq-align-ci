# -*- coding: utf-8 -*-
"""حارسُ «المسطرتين»: يقيس تطابقَ العدّة بين `QuranRafiq` و`rafiq-align-ci`.

⛔ **سببُ وجوده — فخٌّ وقع ستَّ مرّاتٍ في يومين** (2026-09-08/09):
   `normalizer_audit` (1.0 في CI و1.1 محلّيّاً) · عمودُ قالون في
   `new_reciters.tsv` · طلبُ المسبار غيرُ المرمَّز · الحارسُ الخامسُ المعايَر ·
   `batch_run.py` أقدمُ في CI بثلاثة إصلاحاتِ سلامة · وسائرُ سلسلة المحاذاة.
   **والقاعدةُ التي كلّفت هذا كلَّه: التعديلُ في مستودعٍ ليس تعديلاً في العمل.**
   ما يجري في الموجات هو نسخةُ `rafiq-align-ci` وحدَها — فإصلاحٌ يودَع في
   `QuranRafiq` ولا يُنسخ **لا أثرَ له**، ويظنّ صاحبُه أنه أصلح.

⛔ **والأسطرُ تُطبَّع قبل البصم** (`\\r\\n` ⇒ `\\n`): نهايةُ السطر أثرُ
   `autocrlf` في وندوز لا فرقٌ في السلوك، ومقارنةٌ لا تطبّعها تُبلّغ عن
   **كلّ** ملفٍّ فتغرق الحقيقةُ في ضجيج.

الاستعمال:
    python tools/ci_fleet/repo_parity.py            # جردٌ كامل
    python tools/ci_fleet/repo_parity.py --critical # الحرجُ وحدَه (خروج 1 عند اختلاف)
    python tools/ci_fleet/repo_parity.py --sync tools/alignment/vad.py
"""
import argparse
import hashlib
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PEER = os.path.join(os.path.dirname(ROOT), "rafiq-align-ci")

# ⛔ الحرجُ = ما **تستورده الموجةُ فعلاً** (خطوةُ «سلسلة البناء كاملة» في
#    `align.yml` تستورد هذه بأسمائها) + سائقُ الشريحة ورافعُها. اختلافُ واحدٍ
#    منها يعني أنّ ما يجري في السحابة غيرُ ما اختُبر على الجهاز.
CRITICAL = (
    "tools/alignment/batch_run.py",
    "tools/alignment/common.py",
    "tools/alignment/pipeline.py",
    "tools/alignment/validate.py",
    "tools/alignment/vad.py",
    "tools/alignment_v2/refine.py",
    "tools/alignment_v2/transcribe_v2.py",
    "tools/cloud/coverage_guard.py",
    "tools/ci_fleet/run_shard.sh",
    "tools/ci_fleet/stage_upload.py",
    "tools/ci_fleet/prune_certified.py",
)

EXTS = (".py", ".sh", ".tsv", ".txt", ".yml")
SKIP_DIRS = {"work", "__pycache__", ".git", ".venv"}


def digest(path):
    """بصمةٌ بعد تطبيع نهايات الأسطر — الفرقُ في السلوك لا في الحرف."""
    with open(path, "rb") as f:
        return hashlib.md5(f.read().replace(b"\r\n", b"\n")).hexdigest()


def compare(rels):
    same, diff, missing = [], [], []
    for rel in rels:
        a = os.path.join(ROOT, rel.replace("/", os.sep))
        b = os.path.join(PEER, rel.replace("/", os.sep))
        if not os.path.exists(a) or not os.path.exists(b):
            missing.append(rel)
        elif digest(a) == digest(b):
            same.append(rel)
        else:
            diff.append((rel, digest(a), digest(b)))
    return same, diff, missing


def walk_shared():
    """كلُّ ملفّ عدّةٍ موجودٍ في المستودعين معاً."""
    out = []
    for root, dirs, files in os.walk(os.path.join(PEER, "tools")):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f.endswith(EXTS):
                rel = os.path.relpath(os.path.join(root, f), PEER).replace(os.sep, "/")
                if os.path.exists(os.path.join(ROOT, rel.replace("/", os.sep))):
                    out.append(rel)
    return sorted(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--critical", action="store_true",
                    help="اقتصر على سلسلةِ ما تشغّله الموجةُ فعلاً")
    ap.add_argument("--sync", metavar="REL",
                    help="انسخ ملفّاً بايتاً بايتاً من QuranRafiq إلى rafiq-align-ci")
    a = ap.parse_args()

    if not os.path.isdir(PEER):
        print(f"⛔ لا أجد {PEER} — لا يُقاس تطابقٌ بمستودعٍ واحد")
        return 2

    if a.sync:
        src = os.path.join(ROOT, a.sync.replace("/", os.sep))
        dst = os.path.join(PEER, a.sync.replace("/", os.sep))
        if not os.path.exists(src):
            print(f"⛔ لا وجودَ لـ{src}")
            return 2
        shutil.copyfile(src, dst)
        print(f"✅ نُسخ {a.sync} — البصمةُ الآن {digest(dst)}")
        return 0

    rels = list(CRITICAL) if a.critical else walk_shared()
    same, diff, missing = compare(rels)
    print(f"مقيسٌ: {len(rels)} ملفّاً · متطابقٌ {len(same)} · "
          f"مختلفٌ {len(diff)} · غائبٌ في أحدهما {len(missing)}")
    for rel, ha, hb in diff:
        print(f"  ⛔ {rel}\n       QuranRafiq   {ha}\n       rafiq-align-ci {hb}")
    for rel in missing:
        print(f"  ⚠️ غائبٌ في أحد المستودعين: {rel}")
    if diff and a.critical:
        print("\n⛔ اختلافٌ في سلسلةِ التشغيل — ما يجري في السحابة غيرُ ما اختُبر.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
