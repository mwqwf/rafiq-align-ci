#!/usr/bin/env python3
"""يبني صور المصحف الملوّن الرسمي (مجمع الملك فهد) للروايات الثلاث.

المصدر: ملفّات `.ai` الرسميّة المنشورة على archive.org — 604 ملفاً لكل رواية،
وهي في حقيقتها **مستندات PDF** (`%PDF-1.5`) فتُفتح مباشرةً بلا تحويل وسيط.

**لماذا PyMuPDF حصراً؟** جُرّب pdfium فسطّح الزخرفة (ضاع الإطار المسنَّن وشارة
الجزء/الحزب وتلوين علامات الآيات). PyMuPDF يعرض الصفحة كاملةً بزخرفتها.

**لماذا خارج المستودع؟** 1812 صورة ≈ مئات الميغابايت، والصور تُستضاف خارجاً
وتُجلب عند الطلب — فلا تدخل حزمة التطبيق أبداً.

السكربت **قابل لإعادة التشغيل**: ينزّل إن لم يجد الأرشيف في الكاش، ويتخطّى كل
صفحة أُنتجت سليمة من قبل. فمقاطعتُه لا تُضيّع عملاً.

التشغيل:  python tools/build_mushaf_images.py [hafs warsh qalon]
          python tools/build_mushaf_images.py --width 1440 --quality 80 --out-prefix mushaf_hd hafs

الخيارات (الافتراضي بلا تغيير: 1000 · 80 · المجلّد `mushaf-out`): `--width` عرضُ الصورة بالبكسل ·
`--quality` جودة WebP · `--out-prefix` اسمُ مجلّد المخرجات تحت TEMP (فتكون نسخةُ HD في مجلّدٍ مستقلّ
`mushaf-hd` ولا تختلط بالعاديّة، وتُرفع إلى `mushaf_hd/` في الدلو). الصورُ تُبنى من ملفّ المجمع الأصلي بالأداة
نفسِها ولا تُمسّ يدوياً.
"""

import concurrent.futures as futures
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

TEMP = os.environ.get("TEMP") or tempfile.gettempdir()
CACHE = os.path.join(TEMP, "mushaf-cache")
OUT = os.path.join(TEMP, "mushaf-out")

# الروابط مُتحقَّق منها؛ الإذن المنشور من المجمع يبيح الاستعمال الحاسوبي المجاني.
SOURCES = {
    "hafs": "https://archive.org/download/1441-ai-hafs_202109/1441-AI-hafs.zip",
    "warsh": "https://archive.org/download/1442-ai-warsh/1442-ai-warsh.zip",
    "qalon": "https://archive.org/download/qaloon-vector/1443-qalon.zip",
}

# مصدر الملفّات يسمّي رواية قالون `qalon`، والتطبيق يسمّيها `qalun` (انظر
# `riwayat` في `index.jz`). فمجلّد الصور باسم التطبيق كي يبنيه الرابط مباشرةً.
ASSET_ID = {"hafs": "hafs", "warsh": "warsh", "qalon": "qalun"}

PAGES = 604
WIDTH = 1000          # عرض الصورة النهائيّة بالبكسل
CROP = None           # صندوق القصّ (يُملأ من --crop-box)
FORMAT = "webp"       # webp | avif (avif: جودة 60 وسرعة 6 كما قِيس؛ المخرجات .avif)
QUALITY = 80          # جودة WebP — الموازنة بين وضوح الرسم وحجم التنزيل
MIN_BYTES = 10 * 1024  # أقل حجم مقبول؛ ما دونه دليل على تحويل فاشل
BATCH = 32             # صفحات الدفعة الواحدة — سقفٌ لاستهلاك الذاكرة


CHUNK = 8 * 1024 * 1024   # حجم القطعة في التنزيل المتوازي
SEGMENTS = 8              # عدد الاتصالات المتزامنة لكل أرشيف


def fetch(riwaya):
    """يُعيد مسار الأرشيف، منزِّلاً إيّاه على قطعٍ متوازية إن لم يكن في الكاش.

    **لماذا تنزيلٌ مقطَّع؟** archive.org يخنق الاتّصال الواحد (قِيس: ≈٢.٥ م.ب/د)،
    فنصفُ غيغابايت يستغرق ساعات. والخنق **لكل اتّصال** لا لكل عميل، فثمانية
    اتّصالات متوازية تضاعف الحصيلة أضعافاً.

    والقطع تُحفظ ملفّاتٍ مستقلّة ثم تُدمج: هكذا تكون المقاطعة بلا ثمن — كل قطعة
    تمّت تبقى، ولا يُعاد إلا الناقص. (والقطعة الأخيرة قد تكون ناقصة عند القطع،
    فتُحذف كل قطعة لم تبلغ حجمها المتوقَّع.)
    """
    import concurrent.futures as futures

    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"{riwaya}.zip")
    if os.path.exists(path) and zipfile.is_zipfile(path):
        return path

    url = SOURCES[riwaya]
    total = int(subprocess.run(
        ["curl", "-sIL", url], capture_output=True, check=True
    ).stdout.decode("latin-1").lower().rsplit("content-length:", 1)[1].split()[0])

    parts = os.path.join(CACHE, f"{riwaya}.parts")
    os.makedirs(parts, exist_ok=True)
    count = (total + CHUNK - 1) // CHUNK

    def size_of(i):
        return min(CHUNK, total - i * CHUNK)

    def grab(i):
        dest = os.path.join(parts, f"{i:05d}")
        if os.path.exists(dest) and os.path.getsize(dest) == size_of(i):
            return 0
        start = i * CHUNK
        end = start + size_of(i) - 1
        for _ in range(5):
            subprocess.run(["curl", "-sL", "--retry", "3", "-r", f"{start}-{end}",
                            "-o", dest, url], check=False)
            if os.path.exists(dest) and os.path.getsize(dest) == size_of(i):
                return 1
        raise SystemExit(f"[{riwaya}] تعذّرت القطعة {i}")

    print(f"[{riwaya}] تنزيل {total // 1048576} م.ب على {count} قطعة", flush=True)
    done = 0
    with futures.ThreadPoolExecutor(max_workers=SEGMENTS) as pool:
        for got in pool.map(grab, range(count)):
            done += got
            if done and done % 10 == 0:
                print(f"[{riwaya}] {done} قطعة", flush=True)

    with open(path, "wb") as out:
        for i in range(count):
            with open(os.path.join(parts, f"{i:05d}"), "rb") as part:
                shutil.copyfileobj(part, out)
    if not zipfile.is_zipfile(path):
        raise SystemExit(f"[{riwaya}] الأرشيف المدموج تالف")
    shutil.rmtree(parts, ignore_errors=True)
    return path


def page_files(zf):
    """يرتّب ملفّات الصفحات 604 بالرقم المستخرَج من الاسم.

    أسماء الروايات الثلاث تختلف (مثل `001___Hafs39__DM.ai`)، فالاعتماد على أوّل
    عدد في اسم الملفّ أمتنُ من افتراض نمطٍ واحد.
    """
    entries = [n for n in zf.namelist()
               if n.lower().endswith(".ai") and not n.endswith("/")]
    keyed = []
    for name in entries:
        m = re.search(r"(\d{1,4})", os.path.basename(name))
        if m:
            keyed.append((int(m.group(1)), name))
    keyed.sort()
    if len(keyed) != PAGES:
        raise SystemExit(f"عدد الصفحات {len(keyed)} بدل {PAGES}")
    return keyed


def render(args):
    """يحوّل صفحة واحدة إلى WebP. يعمل في عمليّة مستقلّة (استيراد داخليّ لازم)."""
    import fitz
    from PIL import Image

    number, data, dest, width, quality, crop, fmt = args
    doc = fitz.open(stream=data, filetype="pdf")
    page = doc[0]
    zoom = width / page.rect.width          # التكبير يُشتقّ من العرض المطلوب
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    img = Image.open(io.BytesIO(pix.tobytes("ppm")))
    if crop:
        # قصٌّ بصندوق الهوامش نفسِه (مُعرَّفٍ على عرض 1000) مضروباً في نسبة العرض: يُبقي الإحداثياتِ المطبَّعة صالحةً للنسخة العالية.
        k = width / 1000
        img = img.crop(tuple(int(round(v * k)) for v in crop))
    if fmt == "avif":
        # حارس فقد الحبر: كلُّ مكوّنٍ حبريٍّ في المصدر المصيَّر (g<128، اتصال 8) يجب أن يبقى في AVIF المفكوك
        # فيه بكسلُ حبرٍ واحدٌ على الأقل (وإلا ضاعت نقطةٌ أو حركة). يُكتب "عدد مكوّنات المصدر الضائعة".
        import numpy as np
        from scipy import ndimage as ndi
        img.save(dest, "AVIF", quality=quality, speed=6)
        g = np.asarray(img.convert("L"))
        ga = np.asarray(Image.open(dest).convert("L"))
        lab, cnt = ndi.label(g < 128, structure=np.ones((3, 3)))
        alive = np.unique(lab[(ga < 128) & (lab > 0)])
        with open(dest + ".ink", "w") as f:
            f.write("%d %d" % (cnt, cnt - len(alive)))
    else:
        img.save(dest, "WEBP", quality=quality, method=6)
    doc.close()
    return number, os.path.getsize(dest)


def build(riwaya):
    zip_path = fetch(riwaya)
    out_dir = os.path.join(OUT, ASSET_ID[riwaya])
    os.makedirs(out_dir, exist_ok=True)

    with zipfile.ZipFile(zip_path) as zf:
        keyed = page_files(zf)
        todo = [(n, name) for n, name in keyed
                if not (os.path.exists(os.path.join(out_dir, f"{n:03d}.{FORMAT}"))
                        and os.path.getsize(os.path.join(out_dir, f"{n:03d}.{FORMAT}")) >= MIN_BYTES)]

        print(f"[{riwaya}] {len(todo)} صفحة للتحويل", flush=True)
        done = 0
        # عمليّات لا خيوط: العرض عمل حسابيّ بحت يقيّده قفل بايثون العام.
        # ودفعاتٌ صغيرة لا قائمةٌ واحدة: بيانات الصفحات تُنقل بالنسخ إلى
        # العمليّات، وتحميل 604 صفحة دفعةً واحدة يعني مئات الميغابايت في
        # الذاكرة بلا داعٍ.
        with futures.ProcessPoolExecutor(max_workers=os.cpu_count()) as pool:
            for i in range(0, len(todo), BATCH):
                jobs = [(n, zf.read(name), os.path.join(out_dir, f"{n:03d}.{FORMAT}"), WIDTH, QUALITY, CROP, FORMAT)
                        for n, name in todo[i:i + BATCH]]
                for _ in pool.map(render, jobs, chunksize=2):
                    done += 1
                print(f"[{riwaya}] {done}/{len(todo)}", flush=True)

    return verify(riwaya, out_dir)


def verify(riwaya, out_dir):
    """يفشل بصوت عالٍ بدل تسليم مجموعة ناقصة بصمت."""
    missing, tiny, total = [], [], 0
    for n in range(1, PAGES + 1):
        path = os.path.join(out_dir, f"{n:03d}.{FORMAT}")
        if not os.path.exists(path):
            missing.append(n)
            continue
        size = os.path.getsize(path)
        total += size
        if size < MIN_BYTES:
            tiny.append(n)
    if missing or tiny:
        raise SystemExit(f"[{riwaya}] ناقصة: {missing[:10]} | صغيرة: {tiny[:10]}")
    print(f"✓ [{riwaya}] 604 صفحة | {total / 1048576:.1f} م.ب | "
          f"متوسّط {total // PAGES // 1024} ك.ب", flush=True)
    return total


def main():
    global WIDTH, QUALITY, OUT, CROP, FORMAT
    import argparse
    ap = argparse.ArgumentParser(description="يبني صور المصحف الملوّن")
    ap.add_argument("riwayat", nargs="*", help="hafs warsh qalon (الافتراضي: الثلاث)")
    ap.add_argument("--width", type=int, default=WIDTH, help=f"عرض الصورة بالبكسل (الافتراضي {WIDTH})")
    ap.add_argument("--quality", type=int, default=QUALITY, help=f"جودة WebP (الافتراضي {QUALITY})")
    ap.add_argument("--format", default="webp", choices=("webp", "avif"), help="صيغة المخرجات")
    ap.add_argument("--out-prefix", default="mushaf-out",
                    help="اسم مجلّد المخرجات تحت TEMP (الافتراضي mushaf-out)")
    ap.add_argument("--crop-box", default="",
                    help="x0,y0,x1,y1 على قاعدة عرض 1000 (صندوق قصّ الهوامش الذي طبّقه crop_mushaf_margins.py)")
    args = ap.parse_args()
    CROP = tuple(int(v) for v in args.crop_box.split(",")) if args.crop_box else None
    if CROP is not None and len(CROP) != 4:
        raise SystemExit("--crop-box يلزمه أربع قيم")
    WIDTH, QUALITY, FORMAT = args.width, args.quality, args.format
    OUT = os.path.join(TEMP, args.out_prefix)
    bad = [r for r in args.riwayat if r not in SOURCES]
    if bad:
        raise SystemExit(f"رواية مجهولة: {bad}")
    which = args.riwayat or list(SOURCES)
    if not shutil.which("curl"):
        raise SystemExit("curl غير موجود")
    for riwaya in which:
        build(riwaya)


if __name__ == "__main__":
    main()
