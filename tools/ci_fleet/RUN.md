# `RUN.md` — الأوامر بالترتيب، تُنفَّذ حرفياً

> كتبها `rafiq-store` للمشرف، 2026-09-02. الشجرة الجاهزة: **`C:/Users/slxc/Documents/GitHub/rafiq-align-ci`**
> (‏1971 ملفاً · 8.7م.ب · حارس التسرّب أخضر).
>
> ⛔ **قبل كل شيء:** إنشاء مستودعٍ عام ورفعُ سرٍّ وتشغيلُ حوسبةٍ خارجية أفعالٌ
> خارجية لا تُتخذ إلا بإذن المالك النافذ. هذا الملف يصف **كيف** لا **متى**.
>
> Git Bash. وإن ظهرت مشكلة تحويل مسارات: `export MSYS_NO_PATHCONV=1`.

## 0) التحقق من التفويض

```bash
gh auth status
```
يجب أن يظهر حساب `mwqwf` وصلاحيتا `repo` و`workflow`. إن نقصت `workflow` فلن
يُقبل دفع ملف داخل `.github/workflows/`:
```bash
gh auth refresh -h github.com -s workflow
```

## 1) إنشاء المستودع العام والدفع

```bash
cd /c/Users/slxc/Documents/GitHub/rafiq-align-ci
git init -b main
git add -A
git commit -m "rafiq-align-ci: عدة فهرسة المحاذاة لتشغيلها على عدّائي GitHub"
gh repo create mwqwf/rafiq-align-ci --public --source=. --remote=origin --push
```

تحقّق أن الـworkflow ظهر (التشغيل اليدوي لا يُتاح إلا بعد وجوده على الفرع الافتراضي):
```bash
gh workflow list --repo mwqwf/rafiq-align-ci
```

## 2) السرّ الوحيد

```bash
gh secret set R2_CREDENTIALS_JSON \
  --repo mwqwf/rafiq-align-ci \
  < /c/Users/slxc/Documents/GitHub/QuranRafiq/secure/r2_credentials.json
gh secret list --repo mwqwf/rafiq-align-ci
```
⛔ **من ملفٍ عبر stdin لا كقيمةٍ في سطر الأمر** — سطر الأمر يبقى في تاريخ الصدفة.
و`gh secret list` يعرض الاسم والتاريخ فقط، لا القيمة (وهذا هو التحقق المطلوب).

## 3) ⛔ تشغيلة الاختبار أولاً — مهمة واحدة لا عشرون

```bash
gh workflow run align.yml --repo mwqwf/rafiq-align-ci \
  -f smoke=true -f smoke_surahs=108 -f jobs_per_runner=4
```
(‏`smoke_reciter` اتركه فارغاً فيأخذ أول سطر من `reciters_ci.tsv`، أو حدّده بمعرّفه.)

المتابعة:
```bash
gh run list  --repo mwqwf/rafiq-align-ci --limit 5
gh run watch --repo mwqwf/rafiq-align-ci   # يتابع آخر تشغيل حتى ينتهي
```
وعند الفشل — السجل الكامل لا الملخّص:
```bash
gh run view --repo mwqwf/rafiq-align-ci --log-failed
```

### ما يُقرأ في سجل الـsmoke قبل الإذن بالتعميم (أربعة أسطر بعينها)

| السطر المنتظر | معناه |
|---|---|
| `✅ refine مستورَد — الصقل حيّ` | ⛔ **الأهم**: غيابه يعني فهارس جيلٍ أول تخرج «مكتملة» في الظاهر |
| `النموذج: 43 م.ب` | الاعتماد صحيح والدلو مقروء |
| `🔒 حارس الرفع: …` | الحارس عمل ولم يُتخطَّ |
| `⬆️ رُفع timings-staging/…` | السلسلة كاملة حتى R2 |

ولا يُعمَّم إن ظهر أيٌّ من: `No module named 'refine'` · `SIGILL` ·
`Error opening input files` · `🛑 رُفض الرفع`.

## 4) التشغيل الكامل (بعد نجاح الـsmoke وحده)

```bash
gh workflow run align.yml --repo mwqwf/rafiq-align-ci \
  -f smoke=false -f shards=20 -f jobs_per_runner=4
```
- الشرائح 0..19 تقتسم **51 قارئاً** في `reciters_ci.tsv` بقاعدة `i % 20` — أي 2–3
  قراء لكل شريحة. (النصف الثاني، 50 قارئاً، لجبهة Cloud Run في `reciters_gcp.tsv`.)
- **الاستئناف:** إن قُتلت شريحة على سقف الست ساعات، أعد **الأمر نفسه**؛ الكاش
  يعيد `tools/alignment/work` و`batch_run.py` لا يعيد سورةً لها `json`.
- `concurrency.group: rafiq-align` يمنع تشغيلين متداخلين على الحساب نفسه.

المخرَج: `timings-staging/{riwaya}/{reciterId}.jz` على R2. ⛔ **لا ترقية إلى
`timings/` من هنا** — قرارُ github-b9 بعد مقارنته بالمنشور.

## 5) الإيقاف والتنظيف

```bash
gh run cancel --repo mwqwf/rafiq-align-ci <RUN_ID>
gh cache delete --all --repo mwqwf/rafiq-align-ci      # كاش الثنائي والعمل الجزئي
```
وبانتهاء الدفعة **يُحذف المستودع** (مستودع حوسبة مؤقت):
`gh repo delete mwqwf/rafiq-align-ci` — ⛔ بإذن المالك، ولا شيء فيه غير منسوخ من `QuranRafiq`.

---

## سقوف الحساب المجاني — بمصادرها (فُحصت 2026-09-02)

| البند | القيمة | المصدر |
|---|---|---|
| عتاد `ubuntu-latest` في مستودع **عام** | **4 vCPU · 16 GB RAM · 14 GB قرص** | [github-hosted-runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners) |
| عتاده في مستودع **خاص** | 2 vCPU · 8 GB · 14 GB | المصدر نفسه |
| دقائق Actions في المستودعات العامة | **مجانية على العدّائين القياسيين** (بلا حدّ دقائق) | [usage-limits-billing-and-administration](https://docs.github.com/en/actions/concepts/overview/usage-limits-billing-and-administration) |
| **التزامن على خطة Free** | **20 مهمة** (‏Pro 40 · Team 60 · Enterprise 500) | [limits](https://docs.github.com/en/actions/reference/limits) |
| مهلة المهمة الواحدة | **6 ساعات** | المصدر نفسه |
| أقصى مهام مصفوفة في التشغيل الواحد | 256 | المصدر نفسه |
| مهلة التشغيل الكامل | 35 يوماً | المصدر نفسه |

**نتيجتان تخصّان قرارنا:**
1. ‏**20 هو السقف لا اختياراً** — طلبُ 21 شريحة لا يزيد التوازي بل يصطفّ.
   ومهمة `prepare` نفسها مهمة تُحتسب، لكنها تنتهي في ثوانٍ قبل بدء المصفوفة.
2. **العام يعطي ضعف العتاد** (‏4 vCPU مقابل 2) — وهذا سببٌ تقنيٌّ إضافي لكون
   المستودع عاماً، فوق كونه شرطاً لمجانية الدقائق. ولذلك **`jobs_per_runner=4`**
   (قياس github-8e ‏`37eea00`: العمليات تغلب الخيوط ×2.9 ⇒ عمليةٌ لكل نواة).
   ⚠️ **وهذا مشروطٌ بـ`-t 1`** لكل عملية، وإلّا فكل واحدة تفتح خيوطها الافتراضية
   الأربعة فتزدحم 16 خيطاً على 4 نوى — انظر §المعلَّق أدناه.

⚠️ **سياسة الاستعمال:** تمنع GitHub استعمال العدّائين المجانيين لأغراض لا صلة
لها بالمستودع. عملُنا **فهرسة أصولٍ في المستودع نفسه** فهو في صميم غرضه،
**والمالك فوّض نصاً** (قرار المشرف github-f4، 2026-09-02) — يُدوَّن هنا ويُمضى.

---

## ⛔ معلَّقٌ على قرار صاحب العدة: `-ac 512` و`-t 1`

قياس github-8e (‏`37eea00`) أثبت أن **`-ac 512` يبتر تفريغ المقاطع فوق 10ث**
(‏44.9% فوق 20ث)، والمطلوب حذفه واستعمال `-t 1`. **ولا مقبض لأيٍّ منهما:**

- `-ac 512` **مكتوبٌ حرفياً** في `tools/alignment/transcribe.py:52` داخل قائمة
  الأمر، بلا متغيّر بيئة ولا معامل.
- `-t` **غير ممرَّر أصلاً** ⇒ `whisper-cli` يأخذ افتراضه (4 خيوط). فرضُ `-t 1`
  يقتضي إضافة العلم في الموضع نفسه.

فالتعديل في **ملك جبهة الخوادم (github-b9)**، وموضعه `QuranRafiq/main` كي ترثه
الجبهات الثلاث معاً؛ ولا يُعدَّل من هنا (نسخةٌ متفرّعة تعني محرّكين في فهرسٍ واحد).

**وقبل التعديل يُوزَن أثرٌ لا يُهمَل:** `-ac 512` هو **تسريعٌ مقيس 1.92×**
(تعليق السطر نفسه)، **ومعايرة D-025 وبواباتُ الثقة HIGH/MED/LOW ضُبطت به**. فحذفه
يُبطئ الأسطول إلى النصف تقريباً **ويغيّر سلوك المحرّك في منتصف الدفعة**، فتخرج
فهارس staging بمحرّكٍ غير الذي أنتج المنشور. القرار لصاحب العدة والمشرف، لا لعدّاء.

**وحتى يُحسم:** `jobs_per_runner=4` مطبَّق، و`-ac 512` باقٍ كما هو في العدة.
