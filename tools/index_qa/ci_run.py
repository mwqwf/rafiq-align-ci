#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تدقيقُ فهرسٍ واحد في بيئةٍ عابرة (‏GitHub Actions · Cloud Run · أي حاوية).

    python tools/index_qa/ci_run.py --key timings-staging/warsh/x.abcd1234.jz
    python tools/index_qa/ci_run.py --key ... --clusters 20 --per-cluster 10

**لماذا ملفٌّ منفصل عن `run.py`:** ‏`run.py` أداةُ مشغّلٍ تفاعلية (تطبع جدولاً،
وتقرأ حالةً محلية، وتتصل بخادم الفهرسة عبر SSH). وهذه **وظيفةٌ عابرة**: لا
حالة على القرص، ولا SSH، ولا خادم — تأخذ مفتاحاً، وتُخرج حكماً إلى الدلو،
وتموت. ⇒ **منطق الحكم مستورَدٌ من `run.py` ولا يُعاد كتابته** (مصدرٌ واحد
للقاعدة)، والمختلف هو الغلاف وحده.

**ما تكتبه:** ‏`state/<key>.json` على الدلو — نفس بنية `state/` المحلية
وفيها ما تقرؤه بوابة الترقية: `verdict` · `sha256` · `severeRate` ·
`ciLow`/`ciHigh` · `fatal` · العيّنة بشواهدها.

⛔ **حدودها هي حدود `run.py` نفسها** (ليست أذناً · لا تفصل ما دون ~0.3ث ·
لا بلاغ إلا بشاهدٍ نصّي بعد تمريرين)، وتُطبع مع كل مخرج.

**البيئة المطلوبة:** ‏`pywhispercpp` · `soundfile` · `numpy` · `boto3`،
وأسرار R2 في متغيّرات البيئة (‏`R2_ENDPOINT` · `R2_ACCESS_KEY_ID` ·
`R2_SECRET_ACCESS_KEY` · `R2_BUCKET`). ⛔ **ولا مفتاح في المستودع بحال.**
والنموذج يُنزَّل مرّةً من `models/whisper-tiny-ar-quran/ggml-q8_0.bin` على
الدلو — **وهو النموذج نفسه** الذي قِيست به كل أرقام الليلة، فلا تتغيّر آلة
القياس (اختُبرت المطابقة: تفريغان متطابقان حرفاً بحرف، وثالثٌ بفرق مسافةٍ
يمحوها التطبيع قبل الحكم).
"""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _s3_from_env():
    """أسرار R2 من البيئة — وتفشل بوضوحٍ مسمّيةً الناقص."""
    import boto3
    need = ["R2_ENDPOINT", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"]
    missing = [k for k in need if not os.environ.get(k)]
    if missing:
        raise SystemExit("ينقص من البيئة: " + " · ".join(missing))
    return boto3.client("s3", endpoint_url=os.environ["R2_ENDPOINT"],
                        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
                        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
                        region_name="auto"), os.environ["R2_BUCKET"]


def main():
    ap = argparse.ArgumentParser(description="تدقيق فهرس واحد في بيئة عابرة")
    ap.add_argument("--key", required=True, help="مفتاح الفهرس على الدلو")
    ap.add_argument("--expect-sha", help="ارفض إن لم يطابق المحتوى هذه البصمة")
    ap.add_argument("--clusters", type=int, default=20)
    ap.add_argument("--per-cluster", type=int, default=10)
    ap.add_argument("--band", choices=["HIGH", "MED"])
    ap.add_argument("--refined", choices=["yes", "no"])
    ap.add_argument("--out-prefix", default="state",
                    help="بادئة كتابة الأحكام على الدلو")
    ap.add_argument("--dry-run", action="store_true", help="لا يكتب إلى الدلو")
    a = ap.parse_args()

    import run as R
    # الأسرار من البيئة لا من ملفٍّ في المستودع — والوظيفة العابرة لا قرص لها.
    cl, bucket = _s3_from_env()
    R.s3 = lambda: (cl, bucket)

    # النموذج من الدلو مرّةً واحدة (البيئة العابرة تبدأ فارغة).
    model = Path(os.environ.get("QA_MODEL", "/tmp/ggml-q8.bin"))
    if not model.exists() or model.stat().st_size < 1_000_000:
        model.parent.mkdir(parents=True, exist_ok=True)
        cl.download_file(bucket, "models/whisper-tiny-ar-quran/ggml-q8_0.bin", str(model))
    R.LOCAL_MODEL = model
    R.LOCAL_CACHE = Path(os.environ.get("QA_CACHE", "/tmp/qa_audio"))

    # النصّ المرجعي من الدلو إن لم يكن المستودع كاملاً في البيئة.
    if not (R.ASSETS / "text_hafs.jz").exists():
        R.ASSETS.mkdir(parents=True, exist_ok=True)
        for riwaya in ("hafs", "qalun", "warsh", "douri", "sousi", "shuba"):
            dst = R.ASSETS / f"text_{riwaya}.jz"
            if not dst.exists():
                try:
                    cl.download_file(bucket, f"quran-text/text_{riwaya}.jz", str(dst))
                except Exception:
                    pass          # يُبلَّغ لاحقاً بغياب النصّ لا هنا

    args = argparse.Namespace(
        struct_only=False, allow_unmarked=True, local=True, rejudge=False,
        clusters=a.clusters, per_cluster=a.per_cluster, band=a.band,
        refined=a.refined, long_seg=False, batch=48, threads=1,
        host=None, expect_sha=a.expect_sha)

    t0 = time.time()
    rep = R.audit(a.key, args)
    rep["ciEngine"] = "pywhispercpp/ggml-q8 (tiny-ar-quran)"
    rep["elapsedSec"] = round(time.time() - t0)
    R.show(rep)

    body = json.dumps(rep, ensure_ascii=False, indent=1).encode("utf-8")
    suffix = ((f".band-{a.band}" if a.band else "")
              + (f".refined-{a.refined}" if a.refined else ""))
    out = f"{a.out_prefix}/{a.key.replace('/', '_')}{suffix}.json"
    if a.dry_run:
        print(f"\n(تجربة جافّة — لم يُكتب) {out}")
    else:
        cl.put_object(Bucket=bucket, Key=out, Body=body,
                      ContentType="application/json; charset=utf-8")
        print(f"\n✅ كُتب الحكم: {out}  ({len(body)} بايت · {rep['elapsedSec']}ث)")

    # الخروج غير الصفري يجعل الوظيفة تُخفق على المرفوض — فيُرى في اللوحة.
    sys.exit(1 if rep["verdict"].startswith("مرفوض") else 0)


if __name__ == "__main__":
    main()
