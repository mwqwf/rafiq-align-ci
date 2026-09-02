# -*- coding: utf-8 -*-
"""جرد مرآة الصوت على R2 — الأرقام الثلاثة لكل قارئ من الدلو نفسه لا من السجل.

يُشغَّل **على الخادم** (الدلو محليّ هناك) فلا يمرّ 18 ألف كائن بخط المالك:
    set -a; source /root/.r2env; set +a; python3 audit_report.py > R2_ASSETS_AUDIT.md
"""
import collections, json, os, sys, time
import boto3

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
B = os.environ["R2_BUCKET"]
s3 = boto3.client("s3", endpoint_url=os.environ["R2_ENDPOINT"],
                  aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
                  aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
                  region_name="auto")
pg = s3.get_paginator("list_objects_v2")

per, quarantine = collections.defaultdict(lambda: [0, 0]), 0
for page in pg.paginate(Bucket=B, Prefix="audio/"):
    for o in page.get("Contents", []):
        k = o["Key"].split("/")
        if len(k) >= 4:
            if k[1] == "_quarantine":
                quarantine += 1
            else:
                per[(k[1], k[2])][0] += 1
                per[(k[1], k[2])][1] += o["Size"]

rows = []
for r in ("qalun", "warsh", "hafs", "shuba", "douri", "sousi"):
    try:
        d = json.loads(s3.get_object(Bucket=B, Key=f"audio/{r}/manifest.json")["Body"].read())
    except Exception:
        continue
    for e in d.get("reciters", []):
        f, b = per.get((r, e["id"]), [0, 0])
        sample = (e.get("perFile") or [{}])[0].get("sha256") or e.get("sha256Sample") or "—"
        rows.append((r, e["id"], e.get("mode"), f, b, sample, e.get("ayahCounting"),
                     e.get("countingGate"), e.get("usableForClips"),
                     e.get("timingIndexShaMatch", "—"),
                     e.get("indexEntries"), e.get("indexCoverage"),
                     e.get("indexSurahs"), e.get("refineVersion"),
                     e.get("durationMismatchAtSource"),
                     bool(e.get("contentShift"))))

timings = [k["Key"] for page in pg.paginate(Bucket=B, Prefix="timings/")
           for k in page.get("Contents", []) if k["Key"].endswith(".jz")]

P = print
P("# جرد أصول R2 — مرآة الصوت\n")
P(f"> آخر تحديث: {time.strftime('%Y-%m-%d %H:%M')} · بقلم rafiq-mirror (github-12) · "
  "الحقيقة من الدلو لا من السجل (يُولَّد بـ`tools/cloud/audit_report.py` على الخادم).\n")
P("""## القاعدة الحاكمة للقراءة

**وضع السور: 114/114 دليل اكتمال لا دليل صحة عدّ.** الملف يحوي السورة كلها فلا
موضع فيه لاختبار الترقيم؛ فالمرآة تشهد أن الملفات حضرت كاملةً غير مبتورة، ولا
تشهد أن عدّ آيها كوفي. وصحة العدّ في هذا الوضع يثبتها **الفهرس** (`ayahCounting`
مبنيّ على نص الرواية الكوفي 6236 خانة) لا المرآة — ولذلك يُكتب في المانيفست
`countingGate: SKIPPED_SURAH_MODE` صراحةً كي لا يُقرأ الاكتمال شهادةَ عدّ.

**وقراء آية-بآية: بوابة العدّ الثمانية إلزامية.** ثماني آيات يفترق عندها الكوفي
عن سواه (‏101:11 · 107:7 · 74:56 · 75:40 · 79:46 · 55:78 · 57:29 · 73:20):
حضور ملفها يشهد بالكوفي وغيابه يشهد بعدّ آخر. وربط عدّ غير كوفي بمعرفاتنا
يُسمع الحافظ آيةً ويقرأ غيرها **صامتاً بلا خطأ ظاهر** (‏D-025) — فيحفظ خطأً وهو
مطمئن. وقد وقع فعلاً في `abdul_basit_warsh` فحُجر.

**نسخ بايتي حرفي (‏D-012):** لا إعادة ترميز ولا معالجة. كل ملف يُتحقق من
‏Content-Length قبل رفعه، ثم تُقارن بصمته بـ`audioSha256` في الفهرس.
""")
P("## الأرقام الثلاثة لكل قارئ (ملفات · بايتات · بصمة عيّنة)\n")
P("| الرواية | القارئ | الوضع | ملفات | بايتات | بصمة عيّنة | العدّ | قصاصات "
  "| مطابقة الفهرس | تغطية الفهرس | الجيل | عيوب |")
P("|---|---|---|---:|---:|---|---|---|---|---:|---|---|")
for (r, i, m, f, b, sh, ac, cg, uc, sm, ie, ic, isu, rv, dm,
     cs) in sorted(rows, key=lambda x: (x[11] is None, x[11] or 0)):
    cov = "—" if ic is None else f"{ic:.0%} ({ie}) · سور {isu}/114"
    flags = []
    for d in (dm or []):
        flags.append(f"مدة س{d['surah']} ({d['ratio']}×)")
    if cs:
        flags.append("**انزياح محتوى**")
    P(f"| {r} | `{i}` | {m} | {f} | {b:,} | `{sh[:16]}…` | {ac} | "
      f"{'✅' if uc else '⛔'} | {sm} | {cov} | {rv or '—'} | "
      f"{' · '.join(flags) if flags else '—'} |")
P(f"\n**المجموع الممرأى:** {sum(x[3] for x in rows):,} ملفاً · "
  f"{sum(x[4] for x in rows)/1e9:.1f} ج.ب · **فهارس مرفوعة:** {len(timings)}.\n")
covs = [x[11] for x in rows if x[11] is not None]
if covs:
    covs.sort()
    P(f"""**تغطية الفهرس — الحقيقة المكشوفة:** الوسيط **{covs[len(covs)//2]:.0%}** ·
الأدنى {covs[0]:.0%} · الأعلى {covs[-1]:.0%}. الحقل **واصفٌ لا مانع**: الصوت
سليم بايتياً في الحالات كلها وينفع للتشغيل بالسورة كاملة مهما كانت التغطية،
فالحجب خسارة بلا مقابل — والعتبة قرار المستهلك لا المرآة. وأنّ قارئاً بلغ
{covs[-1]:.0%} برهانٌ أن الانخفاض عيبٌ يُعالَج لا حدٌّ طبيعي يُسلَّم به.
""")
P("""### كيف تُقرأ أعمدة هذا الجدول

**لا يُقرأ عمودٌ شهادةً على ما لم يفحصه** — وهي خلاصة الليلة كلها:
- **مطابقة الفهرس** تشهد أن الفهرس والصوت متسقان، **لا أن أيّهما صحيح**:
  ثلاث سور مبتورة عند المصدر تحمل `MATCH` لأن الفهرس بُني على البتر نفسه.
- **العدّ** في وضع السور `SKIPPED_SURAH_MODE`: بوابته معطَّلة أصلاً هناك.
- **تغطية الفهرس** نسبة الآي التي لها توقيت — واصفةٌ لا مانعة.
- **الجيل**: `unknown` فهرسٌ سابقٌ للحقل (لا نعلم)، و`none` وصفةٌ جديدة جرت
  بصقلٍ صفر (قياسٌ وقع). والخلط بينهما ادّعاءُ قياسٍ لم يقع.
- **عيوب**: «مدة س‏N» عيبُ ملفٍ واحد ⇒ يُحجب **بالسورة**؛ و«انزياح محتوى»
  عيبُ نظام تسمية مجهول المدى ⇒ يُحجب **بالقارئ**.

**وثغرة معلَنة مفتوحة:** سورةٌ سليمة الطول محتواها سورةٌ أخرى **من طولها**
لا يكشفها حارسٌ عندنا اليوم — حارس المدة يفحص الطول لا المحتوى، ومسبار
المطالع سقط في الاختبار (‏8 إنذارات كاذبة من 114 على قارئ سليم) فلم يُشحن.

""")
P(f"""## المحجر `audio/_quarantine/`

{quarantine:,} ملفاً — **لا يُكتب فيه أبداً.** المحجر مقبرة لا مستودع عمل: ما دخله
دخله لسبب، والكتابة فيه تُحييه. والحارس برمجيّ لا عرفيّ: كل كتابة في الدلو تمرّ
بـ`guard_key()` في `mirror_follower.py` فيرفع استثناءً على أي مفتاح فيه
`_quarantine`، و`mirror_worker.py` يخرج بمثله قبل أي تنزيل.

نزيله اليوم: `abdul_basit_warsh` — أسماء ملفاته كوفية ومحتواها بعدّ آخر (‏6213
آية، و48 سورة تخالف الكوفي). التفصيل في
`audio/warsh/_abdul_basit_warsh_WARNING.json`.

## مطابقة الفهرس — كيف يُقرأ الحكم

`timingIndexShaMatch` تقارن بصمة كل ملف ممرأى بما سجّله الفهرس وقت توقيته،
**والبوابة لكل سورة لا للقارئ جملةً**: سورة مخالفة لا تُسقط أخواتها المطابقة،
فالحرمان بقدر العيب لا أوسع منه (`clipsOkBySurah` / `clipsBlockedBySurah`).

**حالة قائمة — `husary_qalun` سورة البقرة:** بصمة الفهرس `8849376f…` ومرآتنا
`b2dcd5e4…`؛ وأُعيد تنزيلها من المصدر نفسه (‏2026-09-01) فجاءت `b2dcd5e4…`.
أي أن **مرآتنا مطابقة لما يخدمه المصدر اليوم، والفهرس هو المُوقَّت على بايتات لم
تعد موجودة**. العلاج إعادة فهرسة البقرة وحدها (نطاق الأسطول لا المرآة)، وحتى
ذلك تبقى قصاصاتها ممنوعة و113 سورة سليمة.
""")
