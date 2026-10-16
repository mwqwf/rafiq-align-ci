#!/usr/bin/env python3
"""يبني حزمةً لكل جزء من صور المصحف المصوَّر المولَّدة (م٧ · تقرير 2026-10-15).

**لماذا؟** التنزيل الكامل للمصحف 604 طلبٍ صغير؛ وعلى نتٍّ ضعيف يكلّف كلُّ طلبٍ مصافحةً وإعادةَ محاولة.
حزمةٌ لكل جزءٍ (≈20 صفحة) تجعله 30 طلباً قابلةً للاستئناف، وكلُّ صفحةٍ فيها تُتحقَّق ببصمتها.

**ما تفعله وما لا تفعله:**
- تأخذ مجلّد الصور المولَّدة نفسها (`mushaf-out/<الرواية>/NNN.webp` من `build_mushaf_images.py`)،
  ⛔ فلا تولّد صوراً ولا تعدّلها ولا تعيد ضغطها: بايتات الصفحة داخل الحزمة هي بايتات ملفّها حرفاً.
- تُخرج لكل رواية ولكل جزء ملفّاً `NN.zip` بصيغة ZIP بلا ضغط (STORED) — فـWebP مضغوطٌ أصلاً.
- ومعه `index.json` فيه sha256 لكل صفحةٍ ولكل حزمة (التطبيق يرفض أي صفحةٍ لا تطابق بصمتها).
- ⛔ لا رفعَ إلى R2 ولا تشغيلَ لسير عمل: الرفعُ خطوةٌ منفصلةٌ يطلقها المدير (انظر أمر الرفع في التقرير).

التقسيم: كل صفحةٍ في حزمة جزءٍ واحد فقط (الجزء الذي تبدأ فيه صفحتُه الأولى حتى ما قبل أولى صفحات التالي)،
وهو تقسيم `JuzPagesPrefetch.juzOf` في التطبيق نفسه (الصفحةُ المشتركة تُنسب إلى التالي).

التشغيل:
    python tools/mushaf/build_juz_packs.py --images <مجلد_الصور> --out <مجلد_الإخراج> [hafs warsh qalun]
البنية المُخرَجة:  <out>/<الرواية>/01.zip … 30.zip + index.json   (والرفعُ إلى `mushaf_juz/<الرواية>/`)
"""
import argparse
import hashlib
import json
import os
import sys
import zipfile

PAGES = 604
RIWAYAT = ("hafs", "warsh", "qalun")
INDEX_VERSION = 1

# مطابقٌ لـReadingProgressRules.JuzPages.DEFAULT.first (ويحرسه اختبارٌ يقرأ ملفّ الكوتلن).
JUZ_FIRST = [1, 22, 42, 62, 82, 102, 121, 142, 162, 182, 201, 222, 242, 262, 282,
             302, 322, 342, 362, 382, 402, 422, 442, 462, 482, 502, 522, 542, 562, 582]

# توقيتٌ ثابت داخل الـZIP كي يكون الإخراج حتميّاً (نفس الصور ⇒ نفس بصمة الحزمة).
FIXED_TIME = (2026, 1, 1, 0, 0, 0)


def juz_ranges(page_count=PAGES):
    """[(جزء, أولى, أخيرة)] — تقسيمٌ بلا تداخل يغطّي 1..page_count."""
    out = []
    for i, first in enumerate(JUZ_FIRST):
        last = (JUZ_FIRST[i + 1] - 1) if i + 1 < len(JUZ_FIRST) else page_count
        out.append((i + 1, first, last))
    return out


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def page_name(page):
    return "%03d.webp" % page


def build_riwaya(images_dir, out_dir, riwaya, page_count=PAGES):
    """يبني حزم رواية واحدة ويكتب index.json؛ يرمي ValueError إن نقصت صفحةٌ أو فرغت."""
    src = os.path.join(images_dir, riwaya)
    dst = os.path.join(out_dir, riwaya)
    os.makedirs(dst, exist_ok=True)
    page_sha = {}
    packs = []
    for juz, first, last in juz_ranges(page_count):
        name = "%02d.zip" % juz
        path = os.path.join(dst, name)
        tmp = path + ".tmp"
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_STORED) as z:
            for page in range(first, last + 1):
                f = os.path.join(src, page_name(page))
                if not os.path.isfile(f) or os.path.getsize(f) == 0:
                    raise ValueError("صفحةٌ ناقصة أو فارغة: %s" % f)
                with open(f, "rb") as fh:
                    data = fh.read()
                page_sha[page] = sha256_bytes(data)
                info = zipfile.ZipInfo(page_name(page), date_time=FIXED_TIME)
                info.compress_type = zipfile.ZIP_STORED
                info.external_attr = 0o644 << 16
                z.writestr(info, data)
        os.replace(tmp, path)
        packs.append({
            "juz": juz, "file": name, "first": first, "last": last,
            "bytes": os.path.getsize(path), "sha256": sha256_file(path),
        })
    index = {
        "version": INDEX_VERSION,
        "riwaya": riwaya,
        "pages": {str(p): page_sha[p] for p in sorted(page_sha)},
        "packs": packs,
    }
    with open(os.path.join(dst, "index.json"), "w", encoding="utf8") as f:
        json.dump(index, f, ensure_ascii=False, indent=1, sort_keys=True)
    return index


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--images", required=True, help="مجلد الصور المولَّدة (يحوي مجلّداً لكل رواية)")
    ap.add_argument("--out", required=True, help="مجلد الإخراج")
    ap.add_argument("riwayat", nargs="*", default=list(RIWAYAT))
    args = ap.parse_args(argv)
    for r in args.riwayat:
        if r not in RIWAYAT:
            print("رواية غير معروفة: %s" % r, file=sys.stderr)
            return 2
    for r in args.riwayat:
        idx = build_riwaya(args.images, args.out, r)
        total = sum(p["bytes"] for p in idx["packs"])
        print("%s: %d حزمة، %.1f م.ب" % (r, len(idx["packs"]), total / 1048576))
    return 0


if __name__ == "__main__":
    sys.exit(main())
