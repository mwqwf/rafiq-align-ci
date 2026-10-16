# تدريب «مصحفك-1» (L4×2) بسقف إنفاق — Vertex AI افتراضياً وGCE بديلاً

لا Kaggle في السير ولا في الجهاز. المصادقة OIDC بلا مفاتيح، ومن `main` فقط. المشروع `black-network-509205-h7`.
المرحلة تجهّزها خطوةٌ أخرى على R2 تحت `models/mushafak1/stage/` (manifest + ckpt + code + d2delta)، وأجزاء d1 تُقرأ من r2.dev العامّ.

## الأفعال (Actions ▸ `gcp-train` ▸ Run workflow ▸ `action`)
- `launch`: يتطلّب `expect_step`. يرفض إن وُجد جهازٌ قائم أو بلغ الدفترُ السقف. يولّد روابط R2 موقّعة (7 أيام) ويمرّرها في metadata، وينشئ الجهاز (SPOT افتراضياً، `STOP` عند القطع).
  المدخلات: `budget_usd` (270) و`rate_usd_per_hour` (فارغ = 1.81 لـspot أو 2.01 عند الطلب، أي السعر ×1.15) و`spot` و`zone` و`machine_type`.
- `status`: حالة الجهاز + آخر `vm_status.json` + الساعات والكلفة التراكمية (أرقام فقط).
- `export`: ينسخ `last.pt,best.pt,run.json,status.json` من `gs://<project>-mushafak1/m1/` إلى R2 `models/mushafak1/stage-out/<step>/`.
- `teardown`: يطلب مزامنةً أخيرة، ثم export، ثم يحذف الأجهزة والأقراص واللقطات والصور والعناوين والدلو، ويطبع جرداً (instances · disks · snapshots · images · addresses · buckets · artifact repos · secrets · scheduler jobs) ويفشل إن لم يكن كلُّه صفراً.
- `watch` (يعمل كلَّ 30 دقيقة تلقائياً): إن لم يوجد `gs://…/active` يخرج. جهازٌ متوقّف والتدريب لم ينتهِ والكلفة دون السقف ⇒ `start`. انتهى أو بلغ السقف ⇒ يؤكّد الحذف ويزيل `active`.

## على الجهاز (`train_startup.sh`)
أول إقلاع: ينزّل المرحلة (sha256) وينسخها إلى `gs://…/stage/` ثم أجزاء d1 + الجزء 16 في مجلد واحد. الإقلاعات التالية لا تعيد ما على القرص. يستأنف من الأحدث خطوةً: المحلية ثم GCS ثم stage.
كلَّ 5 دقائق: يزامن `state/ckpt/m1` إلى `gs://…/m1/` ويضيف دقائق التشغيل إلى `ledger.json` ويحسب الكلفة. عند السقف أو انتهاء التدريب أو `stop_request`: مزامنة أخيرة ثم `done` ثم حذفُ الجهاز وقرصه ذاتياً.
ثلاثة إخفاقات متتالية تنهي الحملة. الكلفة المحسوبة تشمل ساعات التشغيل فقط (القرص يُغطّيه هامش 15%).

## الاستئناف على Kaggle من stage-out
نزّل `models/mushafak1/stage-out/<step>/` من R2 وارفعه مجموعةً بتخطيط `state/ckpt/m1/{last.pt,best.pt,run.json,status.json}`، ثم شغّل `cloud_run.py --local-state … --expect-step <step>` على الدفتر. الرقم `<step>` حدٌّ أدنى للخطوة الفعلية. لا تشغّل Kaggle والجهاز معاً.

## مسار Vertex AI (الافتراضيّ `backend=vertex`)
رُفضت حصةُ GPU لأجهزة GCE وقُبلت حصةُ Vertex (CustomModelTrainingL4GPUsPerProjectPerRegion=2 والمتقطّعة PreemptibleL4=2 في us-central1). مسارُ GCE أعلاه باقٍ بلا حذف (`backend=gce`).
- `launch`: يكتب في الدلو الخاصّ `gs://<project>-mushafak1/run/` ثلاثةَ ملفات: `config.json` و`stage_urls.json` (روابط R2 الموقّعة) و`vertex_train.sh`، ثم ينشئ CustomJob (`g2-standard-24` · `NVIDIA_L4`×2 · قرص 200 غ.ب · `strategy=SPOT` افتراضياً · الحساب `mushafak-ci` · وسم `app=mushafak1`). يرفض إن وُجدت مهمة PENDING/QUEUED/RUNNING بالوسم نفسه. المهلة = الساعات الباقية + 0.25 س بحدّ 24 س.
- الصورة: `us-docker.pkg.dev/vertex-ai/training/pytorch-gpu.2-4.py310:latest` (أحدث وسمٍ GPU لـPyTorch في السجلّ؛ py310 · CUDA 12.x). النقطةُ دُرّبت بـtorch 2.10.0+cu128 فيُثبَّت داخل المهمة `torch==2.10.0` من فهرس cu128 (`torch_pin` في config.json).
- الكلفة الموثوقة تُحسب من API: مجموع (endTime أو الآن − startTime) لمهام الوسم منذ `campaign_start` × السعر، والمعتمد هو الأكبر من هذا ودفترِ النبضات داخل المهمة. السعر الافتراضيّ ×1.15: عند الطلب 2.65 (صفحة أسعار Vertex: 2.30138 لـg2-standard-24 شاملاً GPU)، وspot 2.15 تقديرٌ متحفّظ (سعرُ Compute Engine Spot + رسم إدارة Vertex؛ لم يُؤكَّد رقمُه رسمياً).
- `watch` (كل 30 د): بلا `active` يخرج. `done` أو بلوغ السقف ⇒ يلغي المهام النشطة ويزيل `active`. بلا مهمة نشطة ⇒ يطلق مهمةً تستأنف (3 مهام FAILED متتالية بلا تقدّم خطوة ⇒ `done=failed_final`). مهمة RUNNING لم تُحدَّث `vm_status.json` منذ 60 د ⇒ تُلغى وتُحسب إخفاقاً.
- `status`: حالة آخر مهمة وعددها والكلفة (API/الدفتر/المعتمدة) وآخر `vm_status`. `teardown`: `stop_request` وانتظارٌ حتى 14 د ثم إلغاء النشط ثم export فحذفُ الدلو، والجردُ يضيف `vertex_active_jobs` و`vertex_endpoints` و`vertex_models`.
- داخل المهمة (`vertex_train.sh`): لا metadata ولا حذف ذاتيّ؛ يكتب `done` عند finished/budget_stop/stop_request/failed_final، ويخرج 0 عند قطع spot أو SIGTERM بلا `done` ليعيد watch الإطلاق.
