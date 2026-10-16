# تدريب «مصحفك-1» على GCE (L4×2) بسقف إنفاق

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
