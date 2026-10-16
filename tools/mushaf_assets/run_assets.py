#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُنسِّقُ توليد صور المصحف العالية (HD) وحزم الأجزاء ورفعها إلى R2.

- hd : يصيّر 604 صفحة من ملفّ المجمع الأصلي بـ`build_mushaf_images.py` (عرض 1440) وبصندوق القصّ نفسِه
       الذي قُصّت به النسخةُ العاديةُ المنشورة (CROP في tools/mushaf/page.py بالمستودع الخاصّ، على قاعدة عرض 1000)،
       ثمّ يرفعها إلى `mushaf_hd/<الرواية>/NNN.webp`.
- juz: ينزّل الصفحات **العاديةَ المنشورة** (`mushaf/<الرواية>/NNN.webp`) بحالها، ويبني منها حزمَ الأجزاء
       بـ`build_juz_packs.py`، ثمّ يرفعها إلى `mushaf_juz/<الرواية>/NN.zip` و`index.json`.

⛔ لا حذفَ من الدلو أبداً (لا delete_object). ⛔ ما رُفع بحجمه لا يُرفع ثانيةً (استئناف).
⛔ يرفض الرفعَ إن قلّ العدد عن 604 أو صغرت صفحةٌ عن MIN_BYTES أو اختلفت نسبةُ الأبعاد عن العاديّة بأكثر من 0.5%.
المفاتيح من البيئة فقط: R2_ENDPOINT · R2_ACCESS_KEY_ID · R2_SECRET_ACCESS_KEY · R2_BUCKET (تُطبع أسماؤها لا قيمُها).
"""
import argparse
import concurrent.futures as futures
import os
import shutil
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PUBLIC = os.environ.get("R2_PUBLIC", "https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev")
PAGES = 604
MIN_BYTES = 10 * 1024
AVIF_Q = 60   # جودة AVIF المقيسة (سرعة 6 · 8 بت · تجزئة الألوان الافتراضية كما في القياس)
WIDTH = 1440
RATIO_TOL = 0.005
RIWAYAT = ("hafs", "warsh", "qalun")
# اسمُ الرواية في مصدر المجمع: qalon، وفي التطبيق والدلو: qalun.
SRC_NAME = {"hafs": "hafs", "warsh": "warsh", "qalun": "qalon"}
# صندوقُ القصّ على قاعدة عرض 1000: (إزاحة x، إزاحة y، العرض، الارتفاع) — منسوخٌ من tools/mushaf/page.py::CROP
# (وأبعادُ المنشور المقيسةُ 920×1301 · 942×1292 · 942×1291 تطابقه، وقد قِيست من الدلو العامّ لا من وثيقة).
CROP = {"hafs": (42, 65, 920, 1301), "warsh": (36, 60, 942, 1292), "qalun": (36, 61, 942, 1291)}
PUBLISHED_SIZE = {"hafs": (920, 1301), "warsh": (942, 1292), "qalun": (942, 1291)}


def http_get(url, dest=None, tries=5):
    last = None
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            if dest:
                with open(dest, "wb") as f:
                    f.write(data)
            return data
        except Exception as e:  # noqa: BLE001
            last = e
    raise SystemExit("تعذّر الجلب %s: %s" % (url, last))


def s3_client():
    need = ("R2_ENDPOINT", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET")
    missing = [n for n in need if not os.environ.get(n)]
    if missing:
        raise SystemExit("ينقص من البيئة: " + "، ".join(missing))
    import boto3
    return boto3.client("s3", endpoint_url=os.environ["R2_ENDPOINT"],
                        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
                        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
                        region_name="auto"), os.environ["R2_BUCKET"]


def remote_size(s3, bucket, key):
    try:
        return s3.head_object(Bucket=bucket, Key=key)["ContentLength"]
    except Exception:  # noqa: BLE001
        return None


def upload_all(items, dry_run):
    """items: [(مسار محلي, مفتاح, نوع المحتوى)] — يرفع الناقص فقط ثم يتحقّق بالحجم من الدلو. لا حذف."""
    if dry_run:
        tot = sum(os.path.getsize(p) for p, _, _ in items)
        print("dry_run: لا رفع — %d ملفاً، %.1f م.ب" % (len(items), tot / 1048576), flush=True)
        return 0, len(items), tot
    s3, bucket = s3_client()

    def one(it):
        path, key, ctype = it
        size = os.path.getsize(path)
        if remote_size(s3, bucket, key) == size:
            return "skip", size
        s3.upload_file(path, bucket, key, ExtraArgs={"ContentType": ctype})
        got = remote_size(s3, bucket, key)
        if got != size:
            raise SystemExit("❌ حجمٌ مخالف بعد الرفع: %s محلي %d دلو %s" % (key, size, got))
        return "up", size

    up = sk = tot = 0
    with futures.ThreadPoolExecutor(max_workers=8) as pool:
        for st, size in pool.map(one, items):
            tot += size
            if st == "up":
                up += 1
            else:
                sk += 1
    print("رُفع %d وتُخطّي %d (موجود بحجمه) من %d؛ المجموع %.1f م.ب" % (up, sk, len(items), tot / 1048576), flush=True)
    return up, sk, tot


def webp_size(path):
    from PIL import Image
    with Image.open(path) as im:
        return im.size


def build_hd(riwaya, quality, work, dry_run):
    out_prefix = "mushaf_hd"
    env = dict(os.environ, TEMP=work)
    x, y, w, h = CROP[riwaya]
    box = "%d,%d,%d,%d" % (x, y, x + w, y + h)
    cmd = [sys.executable, os.path.join(HERE, "build_mushaf_images.py"), "--width", str(WIDTH),
           "--quality", str(quality), "--out-prefix", out_prefix, "--crop-box", box, SRC_NAME[riwaya]]
    print("[%s] %s" % (riwaya, " ".join(cmd[2:])), flush=True)
    subprocess.run(cmd, check=True, env=env)
    d = os.path.join(work, out_prefix, riwaya)
    # --- الحرّاس قبل أي رفع ---
    names = ["%03d.webp" % n for n in range(1, PAGES + 1)]
    missing = [n for n in names if not os.path.isfile(os.path.join(d, n))]
    if missing:
        raise SystemExit("❌ [%s] ناقصة %d صفحة: %s" % (riwaya, len(missing), missing[:10]))
    tiny = [n for n in names if os.path.getsize(os.path.join(d, n)) < MIN_BYTES]
    if tiny:
        raise SystemExit("❌ [%s] صفحات دون الحدّ الأدنى: %s" % (riwaya, tiny[:10]))
    sizes = {webp_size(os.path.join(d, n)) for n in names}
    if len(sizes) != 1:
        raise SystemExit("❌ [%s] أبعادٌ غير موحّدة: %s" % (riwaya, sorted(sizes)[:5]))
    (W, H), = sizes
    pw, ph = PUBLISHED_SIZE[riwaya]
    # نسبة الأبعاد مقابل العاديّة: من أبعاد صفحةٍ منشورة فعلاً (لا من الثابت وحده).
    import io
    from PIL import Image
    live = Image.open(io.BytesIO(http_get("%s/mushaf/%s/001.webp" % (PUBLIC, riwaya)))).size
    if live != (pw, ph):
        raise SystemExit("❌ [%s] أبعاد العاديّة المنشورة %s تخالف المتوقَّع %s" % (riwaya, live, (pw, ph)))
    diff = abs((H / W) / (live[1] / live[0]) - 1)
    print("[%s] HD %dx%d نسبة %.5f · العاديّة %dx%d نسبة %.5f · فرق %.3f%%" %
          (riwaya, W, H, H / W, live[0], live[1], live[1] / live[0], diff * 100), flush=True)
    if diff > RATIO_TOL:
        raise SystemExit("❌ [%s] نسبة الأبعاد تخالف العاديّة بأكثر من %.1f%%" % (riwaya, RATIO_TOL * 100))
    items = [(os.path.join(d, n), "mushaf_hd/%s/%s" % (riwaya, n), "image/webp") for n in names]
    return upload_all(items, dry_run)


def ink_count(gray):
    import numpy as np
    from scipy import ndimage as ndi
    return int(ndi.label(gray < 128, structure=np.ones((3, 3)))[1])


def avif_guards(riwaya, d, names):
    """حرّاس AVIF قبل أي رفع: كلُّ صفحة (لا عيّنة) — الأبعاد مطابقة للمنشورة تماماً، وSSIM ≥ 0.99،
    وعدّ مكوّنات الحبر لا يقلّ عن المصدر المصيَّر (ولا عن المنشورة إلا ضمن ضجيجها: يُسجَّل ما نقص عنها).
    يُعيد (أدنى SSIM، أسوأ صفحة، عدد الصفحات الأنقص من المنشورة)."""
    import io
    import numpy as np
    from PIL import Image
    from skimage.metrics import structural_similarity as ssim
    pw, ph = PUBLISHED_SIZE[riwaya]

    def one(n):
        av = Image.open(os.path.join(d, n)).convert("RGB")
        pub = Image.open(io.BytesIO(http_get("%s/mushaf/%s/%s.webp" % (PUBLIC, riwaya, n[:3])))).convert("RGB")
        if av.size != pub.size or pub.size != (pw, ph):
            return n, "dim", (av.size, pub.size), None, None
        g1 = np.asarray(av.convert("L")).astype(float)
        g2 = np.asarray(pub.convert("L")).astype(float)
        s = float(ssim(g1, g2, data_range=255))
        ca, cp = ink_count(g1), ink_count(g2)
        cr = int(open(os.path.join(d, n + ".ink")).read())
        return n, "ok", s, ca, (cp, cr)

    rows = []
    with futures.ThreadPoolExecutor(max_workers=os.cpu_count() or 2) as pool:
        rows = list(pool.map(one, names))
    bad = [(n, v) for n, st, v, _, _ in rows if st == "dim"]
    if bad:
        raise SystemExit("❌ [%s] أبعادٌ تخالف المنشورة في %d صفحة: %s" % (riwaya, len(bad), bad[:5]))
    low = [(n, round(s, 5)) for n, _, s, _, _ in rows if s < 0.99]
    if low:
        raise SystemExit("❌ [%s] SSIM < 0.99 في %d صفحة: %s" % (riwaya, len(low), low[:10]))
    lost = [(n, ca, cp, cr) for n, _, _, ca, (cp, cr) in rows if ca < min(cp, cr)]
    if lost:
        raise SystemExit("❌ [%s] فقدُ حبرٍ (مكوّنات أقل من المنشورة والمصدر معاً) في %d صفحة: %s" % (riwaya, len(lost), lost[:10]))
    below_pub = [(n, ca, cp) for n, _, _, ca, (cp, cr) in rows if ca < cp]
    worst = min(rows, key=lambda r: r[2])
    mean = sum(r[2] for r in rows) / len(rows)
    worst_ink = min(rows, key=lambda r: r[3] - r[4][0])
    print("[%s] حرّاس AVIF: %d صفحة · أدنى SSIM %.5f (الصفحة %s) · متوسطه %.5f · أبعاد مطابقة 604/604 · "
          "حبر ≥ المصدر 604/604 · أنقص من المنشورة بضجيجها %d صفحة · أسوأ فرق حبر %s (%d مقابل %d منشورة)" %
          (riwaya, len(rows), worst[2], worst[0][:3], mean, len(below_pub), worst_ink[0][:3],
           worst_ink[3], worst_ink[4][0]), flush=True)
    return worst[2], worst[0], len(below_pub)


def build_avif(riwaya, work, dry_run):
    out_prefix = "mushaf_avif"
    env = dict(os.environ, TEMP=work)
    x, y, w, h = CROP[riwaya]
    box = "%d,%d,%d,%d" % (x, y, x + w, y + h)
    # عرض 1000 ثم القصّ بالصندوق نفسِه ⇒ أبعادُ المنشورة تماماً. جودة 60 وسرعة 6 كما قِيس.
    cmd = [sys.executable, os.path.join(HERE, "build_mushaf_images.py"), "--width", "1000", "--quality", str(AVIF_Q),
           "--format", "avif", "--out-prefix", out_prefix, "--crop-box", box, SRC_NAME[riwaya]]
    print("[%s] %s" % (riwaya, " ".join(cmd[2:])), flush=True)
    subprocess.run(cmd, check=True, env=env)
    d = os.path.join(work, out_prefix, riwaya)
    names = ["%03d.avif" % n for n in range(1, PAGES + 1)]
    present = sorted(f for f in os.listdir(d) if f.endswith(".avif"))
    if present != names:
        raise SystemExit("❌ [%s] العدد %d بدل %d بالضبط" % (riwaya, len(present), PAGES))
    tiny = [n for n in names if os.path.getsize(os.path.join(d, n)) < 5 * 1024]
    if tiny:
        raise SystemExit("❌ [%s] صفحات صغيرة: %s" % (riwaya, tiny[:10]))
    avif_guards(riwaya, d, names)
    items = [(os.path.join(d, n), "mushaf_avif/%s/%s" % (riwaya, n), "image/avif") for n in names]
    return upload_all(items, dry_run)


def build_juz(riwaya, work, dry_run):
    import build_juz_packs as bj
    img_root = os.path.join(work, "normal")
    d = os.path.join(img_root, riwaya)
    os.makedirs(d, exist_ok=True)
    names = ["%03d.webp" % n for n in range(1, PAGES + 1)]

    def get(n):
        dest = os.path.join(d, n)
        if not (os.path.isfile(dest) and os.path.getsize(dest) >= MIN_BYTES):
            http_get("%s/mushaf/%s/%s" % (PUBLIC, riwaya, n), dest)
        return os.path.getsize(dest)

    with futures.ThreadPoolExecutor(max_workers=16) as pool:
        sizes = list(pool.map(get, names))
    tiny = [n for n, s in zip(names, sizes) if s < MIN_BYTES]
    if len(sizes) != PAGES or tiny:
        raise SystemExit("❌ [%s] العاديّة المنشورة ناقصة أو صغيرة: %s" % (riwaya, tiny[:10]))
    print("[%s] نُزّلت %d صفحة عاديّة، %.1f م.ب" % (riwaya, len(sizes), sum(sizes) / 1048576), flush=True)
    out = os.path.join(work, "juz_out")
    idx = bj.build_riwaya(img_root, out, riwaya)
    # تحقّق ذاتيّ: كلُّ حزمة تحوي صفحات حدودها بالضبط وببايتات الملفّ نفسِه.
    import hashlib
    import zipfile
    seen = []
    for p in idx["packs"]:
        with zipfile.ZipFile(os.path.join(out, riwaya, p["file"])) as z:
            got = z.namelist()
            want = ["%03d.webp" % n for n in range(p["first"], p["last"] + 1)]
            if got != want:
                raise SystemExit("❌ [%s] %s تحوي صفحاتٍ مخالفة لحدودها" % (riwaya, p["file"]))
            for n in want:
                if hashlib.sha256(z.read(n)).hexdigest() != hashlib.sha256(open(os.path.join(d, n), "rb").read()).hexdigest():
                    raise SystemExit("❌ [%s] %s/%s بايتاتها تخالف العاديّة" % (riwaya, p["file"], n))
            seen += want
    if seen != names:
        raise SystemExit("❌ [%s] الحزم لا تغطّي 1..604 بلا تداخل" % riwaya)
    items = [(os.path.join(out, riwaya, p["file"]), "mushaf_juz/%s/%s" % (riwaya, p["file"]), "application/zip")
             for p in idx["packs"]]
    # الفهرس آخراً: لا يُنشر فهرسٌ يشير إلى حزمٍ لم تُرفع.
    res = upload_all(items, dry_run)
    idx_item = [(os.path.join(out, riwaya, "index.json"), "mushaf_juz/%s/index.json" % riwaya, "application/json")]
    r2 = upload_all(idx_item, dry_run)
    return res[0] + r2[0], res[1] + r2[1], res[2] + r2[2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--riwaya", default="all", help="hafs|warsh|qalun|all")
    ap.add_argument("--kind", required=True, choices=("hd", "juz", "avif"))
    ap.add_argument("--quality", type=int, default=70)
    ap.add_argument("--dry-run", default="true")
    ap.add_argument("--work", default=os.environ.get("RUNNER_TEMP") or "/tmp/mushaf_assets")
    a = ap.parse_args()
    dry = str(a.dry_run).lower() in ("1", "true", "yes")
    which = list(RIWAYAT) if a.riwaya == "all" else [a.riwaya]
    bad = [r for r in which if r not in RIWAYAT]
    if bad:
        raise SystemExit("رواية مجهولة: %s" % bad)
    sys.path.insert(0, HERE)
    summary = []
    for r in which:
        work = os.path.join(a.work, "w_" + r + "_" + a.kind)
        os.makedirs(work, exist_ok=True)
        try:
            res = (build_hd(r, a.quality, work, dry) if a.kind == "hd" else
                   build_avif(r, work, dry) if a.kind == "avif" else build_juz(r, work, dry))
        finally:
            shutil.rmtree(work, ignore_errors=True)   # يوفّر القرص؛ والمخرجات رُفعت أو سقطت التشغيلة
        summary.append((r, a.kind) + res)
    print("== الخلاصة (dry_run=%s) ==" % dry)
    for r, k, up, sk, tot in summary:
        if dry:
            print("%s %s: جاهز للرفع %d ملفاً · %.1f م.ب (لم يُرفع شيء)" % (r, k, sk, tot / 1048576))
        else:
            print("%s %s: رُفع %d · متخطّى %d · %.1f م.ب" % (r, k, up, sk, tot / 1048576))


if __name__ == "__main__":
    main()
