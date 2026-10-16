# استئنافُ تدريب «مصحفك-1» على GCE (بطاقة L4)

يستأنف الشوطَ نفسَه الذي كان على Kaggle (الأمرُ نفسُه `cloud_run.py --local-state …` بوسائطه نفسِها) على جهاز Google Compute Engine من رصيد Google Cloud.

## الإطلاق
Actions ▸ `gcp-train` ▸ Run workflow، بالمدخلات: `project_id` و`project_number` و`resume_kernel` (افتراضيّ `cloudenarymarwano/mushafak1-m1-b`) و`expect_step` (51571) و`max_hours` (11) و`spot` و`zone`.
السيرُ يرفض الإطلاقَ إن كان `m1-a` أو `m1-b` على Kaggle RUNNING/QUEUED، أو كان الجهاز `mushafak1-train` قائماً، ثمّ ينشئ الدلوَ `gs://<project>-mushafak1` والجهازَ وينتهي في دقائق.
المتابعة: `gs://<project>-mushafak1/m1/status.json` (المرحلة · الخطوة · PER · ساعات الاستهلاك) و`gcloud compute instances get-serial-port-output mushafak1-train`.

## كيف يعمل الجهاز (`train_startup.sh`)
1. ينزّل الشيفرةَ من مجموعة `mushafak1-code` ومخرَجَ دفتر الاستئناف ونسخَ البيانات (`mushafak1-d1-a/b` و`mushafak1-d2-delta`) من Kaggle، ويتحقّق من أحجام الأجزاء.
2. يختار نقطةَ الاستئناف: الأكبر خطوةً بين مخرَج Kaggle وقرص الجهاز والدلو. وإن كانت دون `expect_step` سقط قبل أيّ تدريب (لا بدءَ من الصفر).
3. يزامن مجلّدَ الحالة إلى `gs://<project>-mushafak1/m1/state/` كلَّ 5 دقائق وعند النهاية.
4. عند الانتهاء (نجاحاً أو إخفاقاً) ينشر `status.json` ويطفئ الجهازَ. وفوقه مهلةٌ صلبة في السكربت و`--max-run-duration` على الجهاز.
5. قطعُ الجهاز المتقطّع: `gcloud compute instances start mushafak1-train` فيستأنف من الدلو. وعدّادُ الساعات تراكميٌّ عبر القطع فلا يتجاوز `max_hours`.

## الاستئناف بعده على Kaggle
النقطةُ الحاكمة: `gs://<project>-mushafak1/m1/state/ckpt/m1/{last.pt,best.pt,run.json,train.log}`.
نزّلها (`gcloud storage cp -r`) وارفعها كمجموعة Kaggle خاصّة أو ضعها في مخرَج دفترٍ، ثم أطلق بـ`--resume-from` و`--expect-step <خطوة status.json>` كما في `docs/ops/MUSHAFAK1_TRAINING.md` على فرع التدريب. لا تستأنف على Kaggle من مخرَج دفترٍ أقدم من خطوة الدلو.

## ⛔ قاعدة: لا منصّتان على نقطة واحدة
لا يعمل Kaggle وGCE على الدرجة نفسِها معاً: شغّل واحداً، وانتظر `finished` في `status.json` (أو إطفاءَ الجهاز)، ثمّ انقل النقطة. بعد الانتهاء احذف الجهاز (`gcloud compute instances delete mushafak1-train`) فالقرص (200 غ.ب) يُحاسَب وهو متوقّف.

## ملاحظات مهمّة
- بطاقةٌ واحدة بدل T4×2: الدفعةُ لكلّ خطوة تنصف (200 ث بدل 400 ث) وجدولُ التعلّم يُحسب بـ`خطوات × دفعة × عدد البطاقات`، فيتغيّر منحنى التدريب عمّا كان. للمطابقة اختر `machine_type=g2-standard-24` (L4×2، يعمل DDP كما في الدفتر).
- يلزم حصّةُ GPU لـL4 في المنطقة (والمتقطّعة لها حصّةٌ منفصلة). وحسابُ `mushafak-ci` يحتاج أدوار: إدارة جهاز Compute، ومشرف التخزين، و`iam.serviceAccountUser` على نفسه.
- مفتاح Kaggle يُخزَّن في metadata الجهاز (مقروءٌ لمن يملك `compute.instances.get`)؛ يُحذف مع الجهاز.
