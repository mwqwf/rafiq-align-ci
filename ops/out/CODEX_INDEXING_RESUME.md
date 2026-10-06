# مصحفك: نقطة الاستئناف — 2026-10-05، 23:12 UTC

أمر المالك: أكمل الفهرسة وافحص أوائل السور وأواخرها ووسطها، ثم أعد التحقق. لا تنتظر قراراً روتينياً. النطاق فهرسة القرآن فقط؛ لا تغيير للنص أو الرواية أو الصوت، ولا إضعاف للحراس أو خفض العتبات.

## ما أُنجز فعلياً الآن

**ثمانية مرشحات رُفعت إلى timings-staging، وقُرئت بايتاتها بعد الرفع وتطابقت بصماتها كاملة. الإنتاج لم يتغير بهذا العمل بعد.**
المصدر النهائي لكل مفتاح وبصمته64 وبصمة أصله وبصمة المرشح المحلي:
[ codex-final-staged-hashes-20261005.json ](codex-final-staged-hashes-20261005.json).
جميعها manualQaOnly=true؛ لا يطلق لها keepalive/restore/ctc_driver مسارات QA التقليدية ذات cache-save/artifacts.

| القارئ | السور | استرجاع مداخل | بصمة staging المختصرة |
|---|---|---:|---|
| peshawa |63|2|aa1473cd11f6|
| s_sadeiq |42|53|927e8bbeb319|
| noah |3،4|376|944dfdfa68b7|
| nufais |25،41،42،82|0|31106cbe8bab|
| rakbawi_qalun |13،26|0|3d8dc7c9e31f|
| derini_warsh |11،14،23،83|0|fd3b23b00bde|
| zahrani |6|0|b962a19c6bec|
| f_khamery |2،6|0|d58b78bf4e63|

الجملة **431 مدخلاً مسترجعاً في الاختبار**، لا تحسبها استرجاعاً منشوراً قبل الترقية الفعلية.
حُفظ كل مدخل خارج السور المختارة كما هو، وفُحصت الهوية وبصمات المصادر والبنية. آخر6 مرشحات وأدلتها الكاملة وبناء same-source متعدد السور نُشرت في eb281e911cc10650f55472151676a9307d6bcf58.
دليل15 بناء صوتي و6 مرشحات: codex-index-history-handoff-20261005.json. سجل كل مرحلة: ops/out/20261005_codex_2240_stage_<reciter>.txt؛ بيشةوا/سلمان في2238_stage_*.

## القياس الجاري: لا تكرر الأوامر

الدورة الأولى كشفت خطأ في ReadOnlyClient: منع generate_presigned_url لقراءة مرآة الصوت، فتفشل عينات قبل القياس. أصلح 7deccf52348b872dcd1a76d45d2a1cbe13ed1265 الإذن المحدود get_object/GET فقط، وأضاف رفض حفظ sample.errors كشاهد رسمي؛36اختباراً نجحت. كل عمليات الكتابة الأخرى ممنوعة. لا تُستعمل الأحكام القديمة الناقصة.
الدورات الجديدة من أوامر2310_qa_readfix، مرتبطة ببصمة المرشح النهائية وأصله:
- peshawa: 37384805644
- s_sadeiq: 37384824323
- noah: 37384787972
- nufais: 37384796841
- rakbawi_qalun: 37384814483
- derini_warsh: 37384770337
- zahrani: 37384833213
- f_khamery: 37384779422
بيشةوا بدأ واجتاز census11/11 عند22:50؛ باقيه مستمر. البقية تنتظر انتهاء الدورة الأولى لنفس المفتاح. لا إعادة إطلاق.
review يشترط openers/census/rs1..4 وheard من نفسrun_id+commit وبعدstaging، بلاerrors، ثم الحارس الأصلي. review قراءة فقط؛ ليس ترقية. يبقى إثبات النهايات المستقل مطلوباً.
النسخة المكررة37383836839 طلبت أداة محدودة إلغاءها قبل البدء؛ سببهاcheckout قديم. أصلح b622334e checkout أمرالوكيل إلىmain الحالي. لا تلغِ أعمالاً أخرى.
الفحوص العامة القياسية restore-only بلاartifacts/cache-save.

## الفحص المستقل للأواخر والتشخيص

pilot المنافقون63 الأول37361389628 فشل قبل تنزيل الصوت بسبب غياب نموذج Quran من cache؛ measuredWindowCount=0، لا حكم جودة منه.
أضفنا تنزيل النموذج القرآني المؤقت الصريح، مثبت revision وSHA الوزن، خارجcache ويُحذف بعد القياس. generic منcache الموجود فقط. لا fallback صامت.
التشغيل الثاني **37383250194/job112010210703** اكتمل:22نافذة مقيسة،errors=[]،**صفر آيات معتمدة من11**؛ الثقة/السياق لم يجتازا الحارس. لا تكرر المدخل نفسه ولا تخفض العتبات. التقرير الكامل codex-peshawa-pilot-37383250194.json،SHA3247788b04216cb02bdf958f5fca0ce05a893b07c76eebd0b3bead44ec1a8cae. اختلاف واضح عند63:10/11 مع تكرار10؛ العام يضع11داخل التكرار، القرآني عند264.7ث، والمرشح266.091ث. نجاحcensus/heard لا يثبت نهايتها.
مصدر بيشةوا:
https://download.quranicaudio.com/quran/peshawa_qadir_al-kurdi/mp3/063.mp3
SHA bbfc9570680b5172ad15e417ce0ef5b8aaf8d15e16ec6f12fe46ea1752243301.
المرشح v2 SHA00fbc75a874d45f80600ccf8f1f7bfe774aae5bffaba89cad3f37eb381997aee. آخرآية63:11 منخفضة الثقة.092، لا تعتمدها بمجرد وجودها.

تشخيص سعد الحر95ث: سور45 نافذة0–25 و28 نافذة620–690؛ كل قناةL/R أصلية وكل نموذج مستقل، بلا نص مُلقَّن أو forced alignment.
التشغيل37383258535 فشل في models بسبب واجهة HTTPCheckedResponse.getcode الناقصة، قبل قياس الصوت. صُحح السبب مع اختبار تكامل حقيقي بين helper والغلاف؛24 اختباراً نجحت.
التشغيل **37383735447/job112011804909** نجح:16قطعة كاملة،147.382ث؛ فك القناتين سليم ولا إلغاء طور. س28 نافذة620–690 تضم كلمات يمكن نسبتها إلى44/45، لذلك عدم المحاذاة السابق ليس دليلاً على غياب44. التفريغ مليء بالأخطاء وليس نصاً مرجعياً ولا شهادة حضور/حدود. تقريرالملخص codex-saad-free-asr-summary-20261005.json؛كل19envelope كاملة lossless في codex-saad-free-asr-37383735447-complete.json.gz.

## ملاحظات جودة لا يجوز إخفاؤها

نوح: س3/4 الرسميتان مثبتتان ب200/200 و176/176 مراسي. البناء كامل من أصل واحدb14ed7f3… دون سلسلة آباء محليين. 3:200 ثقة.222؛4:176 ثقة0 ونهايتها عند آخر الصوت، و67آية من السورتين LOW. يجب قياس هذه المواضع مستقلاً. لا يحوّل نجاح البناء هذه القيم إلى نجاح توقيت.
سلمان42: البناء53/53،5LOW،24ملاحظةnarrow محفوظة. الأصل القديم لم يجتز الفك الصارم؛ صمت كلتا القناتين أو إلغاءL/R **غير مثبت**.
النفيس25:10 يمتد63ث مع تكرار محتمل؛ يحتاج فحصاً مستقلاً. النهايات المقترحة في كثير من الأبنية تعتمد مرساة+800ms؛ لا يُعد ذلك وحده شاهد نهاية مستقل.
الانحرافات القديمة مثبتة فيcodex-unmodified-sample-findings-20261005.json؛ المقارنة بنفس نموذج البناء ليست اختباراً مستقلاً.

## آخر حالة عامة مثبتة قبل هذه المرشحات

المسح37350720371 عند17:52:08Z:180فهرساً،9ناقصة،1315آية غائبة،1121165مدخلاً. تطابق العام/الدلو/manifest/التجميد180/180؛ ليس إثباتاً لكل توقيت.
completion-v2 قرأ180/180 و655حزمة،errors=[]؛6982مقارنة بدء خارج1.5ث،872150بدءاً غير مقيس، ولا شاهد نهاية صالح على البصمات المنشورة في ذلك المسح. هذه فجوة إثبات لا عدد نهايات معطوبة.
النواقص:3siri7=206؛nasser6=165؛noah3/4=376؛peshawa63=2؛s_sadeiq42=53؛saad22/28/45=203؛shamrani79=46؛akri4/24=210؛iraoui41=54.
أعد الجرد بعد اعتماد أي مرشح، ثم قارِن الأحكام على البصمات المنشورة الجديدة. لا تستعمل تقريرأكتوبر2 الذي ادعى الاكتمال.

## مصادر لم تُحل بعد

- ناصر6 Way2 يطابق الأصل بايتاً؛ probe68/165،الذيل69–165 لم يثبت. لا إعادة بناء لنفس الملف كمصدر بديل.
- سعد هو سعد المقرن لا الغامدي؛ Way2س22/28/45 تطابق الأصل بايتاً. probes74/78،85/88،36/37 ليست دليلاً قاطعاً على غياب الآيات؛ نتابع التفريغ الحر.
- الشمراني79 Way2 probe42/46؛11/15/17/18 غير مثبتة،لا مرشح كامل.
- العسيري مداد73330/73348 صوت سليم~1160ث،عنوان «ما تيسر»؛ تغطية7:123–159 غير مقيسة.163992 رفضه decoder.
- الإيراوي ورش Archive480أثمان: H_481..488 و491..498 غير مقيسة؛ يمنع توليد/دمج الصوت. صفحةe-quran تشير إلىmp3quran القديم فلا تعد مصدراً مستقلاً. صفحةZekr/mushaf/6100 تذكر41مدتها20:58؛ رابطها الفعلي يحتاج استخراجاً ومقارنة.
- العكري Way2 سجلmarwan-alakri صفحةهويةقالون،روابط4/24 لم تُستخرج بواسطةwebclick (InternalError)؛ سجلmrwan-al-akry024 معروف مبتور،لا تكرره.
الأدلة: codex-source-candidates-round2-20261005.json وmetadata-batch1/2/3. فشل أحد مصادر دفعة لا يمحو قياسات الآخرين.

## الإصلاحات والتشغيل

stage_transform تحققHEAD+GET وبايتات+SHA64،ويطبعSTAGE_RESULT؛21اختباراً نجحت. خطأ نقل نصي في نشر8b50 منع محاولتين قبلأيPUT،وصحح ببصمة Gitblob a6fd4ab2d3702c8524c9acc863703bd240f52d56 فيb2bf70e. إعادةالرفع2238 نجحت. **أي نقلملف مستقبلي يجب مطابقته ببصمةGit blob؛لا تقبل نصtool مقتطعاً.**
فشلkeepalive-contract37383143113 كان لأن اختباراً يعد كلexcept=2،بينما حارسmanualQA أضافexcept ثالثاً يؤجل المرشح. يجري إصلاح الاختبار ليميز حارسي الدفعة اللذينraise عن حارس المرشح الذيcontinue،دون تغييرruntime؛18اختباراً محلياً نجحت.
مهارة github-actions-cost-control سارية: لا إنفاق جديد أو cache-save/artifacts. تدقيق17:48:18cache/10033325306B و4745artifact/140067941B؛ الحصة المشتركة غير معلومة.
Claude ظل نشطاً حتى21:52 علىclaude/finish-indexing-dscfok،وقد يعمل علىالمروش5/40/85 وموجةfixT. لا تكرر/تلغ أعماله. س70للمروش لم تُعالج فيمجموعتنا.
البيئة المحلية بلاHTTP/أسرار؛لا تتحايل. GitHubconnectors وActions العامة المخولة مسارالتنفيذ.
agent_cmd قديلغيqueuedrun عندpush جديد لكنالأوامر تبقى حتىتُنفذ؛لا تفترض فقدها.
متابعةChatGPT6aaad3d05d108191b8f561114e898ced لم يثبتتنفيذها(next_run_time=null،run_now404). لا تعدبعمل خلفي غيرمثبت. تشغيلGitHub أعلاه فعلي.

**المهمة غير مكتملة. التالي: اقرأ نتائجالفحوص، أصلح أسبابالرفض الحقيقية، أثبتالأواخر، ثمترقَّ بالحراس الأصلية وأعدالجرد. لاشهادة100%.**

## تحديث22:59

استخراجpublisher_link_inventory نجح للصفحات الثلاث: روابط العكري الصحيحة marwan-alakri/qalun-an-nafi/{s}.mp3 (بلاpadding)، والإيراوي https://cdns1.zekr.online/quran/6100/41/80.mp3. الدليل codex-publisher-link-inventory-20261005.json. أُعد أمر2320_metadata_publisher_sources لقياس4/24/41؛ لا تعتمد هوية/اكتمال من الرابط وحده.
keepalive-contract اللاحق اجتاز11contract ثم فشلimport qa_dispatch_guard عندتشغيلrestore_loop كحزمة. إصلاحrelative/script import اجتاز24restore tests محلياً و--help كبرنامج؛ لا تغييرحراس. إصلاحاختبارexcept السابق منشور وصحيح.

## تحديث23:12 — لا تعتمد مرشح بيشةوا القديم

مرشحaa1473cd اجتازكل7فحوص37384805644،لكنreview رفضتشخيصاً قديماً. تحديثdiagnosis37386228895 نجح1/1 (ALIGNMENT_FAILED:5). **لا أعدreview القديم**: التشخيصالحر37386012711 نجح20قطعة/23envelope في119.08ث،وكشفمؤشراتاقتطاع63:11:كلمةولن تبدأإطاراتها265212ms،والنونالأخيرة281932ms،بعدنهاية279139.النموذجالقرآنيبقناتيهقرأالكلمةالأخيرةكاملة؛العامأخطأ/أسقطالنون،فلاشهـادةاتفاقنموذجين.
المرشحv3 المحليef312d31cb8047ea440240c32ea9f41921bf842ae3f348af7e0d58da9b90d8e0 يقترحبدء11=264706منمحاذاةQuranالتشخيصيةونهاية282300(آخرإطار282052مقرب+200ms)،ويمدد10حتىبدء11الجديد.فقطمدخلان تغيرتحدودهما؛الثقةLOWباقية،الشاهدالثنائيرافضباقٍ،qualityClaim=false.كل6234مدخلآخرحُفظ،البنية6236/6236/114/114ولاfatal.أمر2350_stage_peshawa_tail_v3 يرفعmanual-onlyويعيدقراءةSHAالفعلية؛لا تستخدمSHAالمحليلتشغيلQA.ملفاتالدليلcodex-peshawa-tail-{free-asr-37386012711,correction-20261005}.jsonوالbundleكاملgz.لميتغيرالإنتاج.
مصادرالناشرين:metadata37386119862 نجحبعدتصحيحمعرّفاتالمصادرالمكررة(التشغيلالأوللميقسأيصوت).Akri4 SHA c515961b952027b1ecaf505ca0d3fe2bc11aada58b3c7c022b806e45d238c6e1،PCM4833.097125ثبفكسليم.بناء176آيةجاري37386801366،logs-onlyبلاR2.العكري24الجديد766.902875ثفقط،لا دليلأنهأصلحالذيل.الإيراويZekr41:المدةالمعلنة1258.488لكنPCM316.8375فقطبلاخطأdecoder؛لاتعتمدمدةالحاويةكتغطية.الدليلالكاملمحفوظcodex-publisher-metadata-37386119862.json.

## تحديث 23:27 UTC — الحالة الحالية المرجعية
- بيشةوا v3 رُفع وتحقق GET كامل: timings-staging/hafs/peshawa.ca0edef5.jz، SHA ca0edef5fdef1f4a6bcf404c805d1be10e295cb36c76db87d959670a82b9675e. يحل محل aa1473cd. QA الجديد 37387403700: المطالع والإحصاء وrs1..4 نجحت، heard جارٍ. لا إنتاج تغيّر.
- تشخيص v3 المنفصل 37387414024 نجح قياساً: كل البدايات 264701–264840ms، لكن نهاية النموذج العام 279027–279047 مقابل القرآني 282050–282070؛ الأخير متسق مع النون الأخيرة في التفريغ الحر. لا تزعم اتفاق نموذجين ولا اجتياز الشاهد المستقل السابق. الأدلة codex-peshawa-v3-tail-dual-{37387414024,summary-20261005}.json.
- فحص نهايات 16 سورة معدّلة مستقل بلا نص مرجعي: 37388055996، jobs 112026264562 (group0)،112026264424 (group1)،112026264115 (group2). الخطة codex-final-verse-free-asr-plan-20261005.json. اجمع كل FINAL_VERSE_FREE_ASR envelopes وتحقق SHA قبل التحليل. لا تعِد التشغيل لمجرد الانتظار.
- سلمان QA 37384824323: جميع القياسات السبعة نجحت؛ review 112026613615 رفض تشخيص كتالوج ببصمة قديمة. أمر 2370_sadeiq_diagnosis يحدث التشخيص؛ بعد نجاحه أعد review وحده بنفس run/commit، لا تعِد قياس الصوت.
- QA الباقي جارٍ/منتظر: noah37384787972،nufais37384796841،rakbawi37384814483،derini37384770337،zahrani37384833213،khamery37384779422. لا ازدواج.
- بناء العكري4 37386801366/job112021946483 ما زال جارياً. لا تعِد بناءه؛ استخرج CTC_ALIGNMENT_RESULT بعد اكتماله وافحص176 آية قبل الترشيح.
- استخراج روابط العيراوي نجح: codex-iraoui-publisher-links-20261005.json. أمر2370_iraoui_metadata يقيس Way2 explicit Azraq /041.mp3 وMidad resources/ar/recitations/47272/457952/041.mp3. Zekr السابق 316.8375ث فقط، لا تعدّه كاملاً.
- أصلح import restore_loop؛ keepalive-contract37385643866 و37385900425 نجحا. أداة rerun_peshawa_review.py المحلية غير المنشورة خاصة بالنسخة القديمة: لا تستخدمها.
- المهمة غير مكتملة؛ 100% غير مثبتة. لم تُرقَّ أي نسخة من هذه المجموعة بعد.

## تحديث 23:42 UTC — اعتماد فعلي ثم تدقيق
- **اعتمد بيشةوا v3 فعلياً** عبر promote_verified_transform، وأعيد التجميد على ca0edef5fdef1f4a6bcf404c805d1be10e295cb36c76db87d959670a82b9675e. العام والدلو وmanifest والتجميد متطابقة؛ 6236 مدخلاً. أمر2380_adopt_peshawa_v3 rc=0. تحفظ الثقة LOW واختلاف النموذج العام؛ لا شهادة جودة100%.
- الجرد بعد الاعتماد: ops/out/full-audit-codex-after-peshawa-20261005.{json,md} عند23:36:13. 180/180 هوية وبنية،1121167 مدخلاً،1313 غائبة. **6 آيات مستحيلة المدة تحتاج إصلاحاً**: balilah69:50،darweez53:57،tblawi7:24،koshi_warsh11:118،m_abdulkareem_warsh21:48،noah_warsh54:17. أوامر2410 تصدر أصولها وsaad/shamrani ببصمات الجرد دون تغيير.
- دفعة النهايات37388055996 نجحت قياساً:16مصدرًا،60صف نموذج/قناة،105envelope،errors[]. محفوظة بالكامل في codex-final-verse-free-asr-37388055996-complete.json.gz SHA ed849b75af2fb1a5d0b0231096439a9cb08c6ec585a3fcfedd6fdba4e551d9b3؛ الملخص codex-final-verse-free-asr-summary-20261005.json.
- **لا تعتمد النسخ الحالية من derini_warsh / f_khamery / zahrani**: إطارات الحرف الأخير بعد نهاية المقترح فيderini11/23/83 وkhamery6؛ Zahrani6 يكرر العبارة الأخيرة بعد5033038ms. يلزم تصحيح الحدود ثم QA جديد على SHA الجديد.
- تشخيص النهايات الخمس الأول37389442910 أكمل فك المصادر وتفريغ الزهراني إلى EOF، ثم فشل لغيابctc_segmentation قبل أي محاذاة؛0قياس قسري. الدليل المحلي codex-tail-clipping-partial-37389442910.json،لا تعده نجاحاً شاملاً. أصلحت dependencies وأمر2400_tail_clipping_dependencies_fixed يطلق قياساً جديداً؛ لا ازدواج بعد هذا الإصلاح.
- فحوص سلمان37384824323 كاملة ناجحة لكنreview رفض تشخيصاً قديماً. تحديثdiagnosis37388689142 نجح. محاولةreview-only2390 فشلت تنزيلlogs عبرgh قبل أيrerun. أصلحت الأداة لتستعمل شاهداً مثبت SHA قرأناه منGitHubconnector، مع مراجعة الحالة الحالية والـcommit والـjob والـdiagnosis؛ أمر2400_sadeiq_review_with_recorded_failure معلق/جارٍ.
- أمر2400_source_quran_recovery يطلق3تشخيصات منفصلة علىShamrani79/Saad28/Saad45 بالنموذج القرآني المثبت float32؛ يتضمن تفريغاً حرّاً لـShamrani28..70ث. لا نشر من محاذاة قسرية وحدها؛ نماذج العام السابقة ضعيفة ولا تثبت غياب الآيات.
- Iraoui مصادر جديدة:37388681174،Way2 explicitAzraq PCM316.908ث (SHA dd438f762595d6e072b9f87d2f68ed0238e423b9d6f3e15978c5c4c12b4217e9) ناقص أيضاً؛ Midad403. لا تتجاوز403 ولا تكرر نفس المصدر المبتور. التقرير codex-iraoui-source-metadata-37388681174.json.
- بناءAkri4 37386801366/job112021946483 ما زال جارياً، بدأ القياس23:10:47؛ انتظره دون تكرار.
- QA Noah/Nufais/Rakbawi جارٍ وبعض قياساتheard طويلة؛ IDs في التحديث السابق. فجوة الثقة الشاملة باقية؛ لا تقل اكتمل100%.

## تحديث 2026-10-06 00:08 UTC — المرجع الأحدث، يتقدم على الحالات السابقة
- اعتمدت ثلاث نسخ فعلياً مع تطابق العام والدلو وmanifest والتجميد: peshawa ca0edef5fdef1f4a6bcf404c805d1be10e295cb36c76db87d959670a82b9675e، s_sadeiq 927e8bbeb319abb25d47930f588410d9bc41c87dc68ee63486ea2ad11acfde34، rakbawi_qalun 3d8dc7c9e31f3579939f7607efbc38ae142aec17900025b49fa3320ec71c09fc. أوامر2380_adopt_peshawa_v3 و2420_adopt_s_sadeiq و2420_adopt_rakbawi_qalun rc=0. استُرجعت55آية فعلياً من هذه المجموعة. آخرجرد1313نقصاً كان قبل سلمان؛ يلزم جرد جديد ولا تستعمله كحالة حالية.
- أصلحنا خمس نهايات بالدليل الحر/fullEOF: derini11:123→3058000،23:118→1688400،83:36→311500؛khamery6:165→2665900؛zahrani6:165→5044600ms. القياس37389928059 كامل53envelope/40محاذاة/4تفريغ،errors[]. ملفات codex-tail-clipping-37389928059.json و-complete.json.gz. لا ادعاء اتفاق نموذجين في الزهراني ولا إخفاء الثقة المنخفضة بالخُميري.
- المرشحات الجديدة مع readback/manualQaOnly: timings-staging/warsh/derini_warsh.cb38c0c1.jz SHA cb38c0c1fd0b7f96e87cadb60142f2a47cafb89354897f7ae4a9028670ae3bba؛ timings-staging/hafs/zahrani.6a5b3f68.jz SHA 6a5b3f68e7d5e7c63598c0668e60c62e7cdba8bf95e7c5a464881bfc414b514f؛ timings-staging/hafs/f_khamery.41ff45fa.jz SHA 41ff45fab5c6d86e11666f412959badba691c340dc89f01af772b4a08185431a. التفاصيل codex-refined-tail-staged-hashes-20261005.json. QA فعلية بالتوالي37391361008 /37391377124 /37391369081؛ لا تكرر.
- تأكد إلغاء QA النسخ المستبدلة37384770337/37384833213/37384779422. لا تعتمد SHA القديم. بقية الأجزاء المكتملة محفوظة.
- Noah37384787972 ما زالheardجارياً والبقيةناجحة. Nufais37384796841 كلQAناجح بما فيهreview112035560699، لكن **لا ترقيه قبل فحص25:10 (63ث)** من دفعة التشخيص التالية.
- تشخيص7مدد37391351958: darweez112036925927 وكوشي112036926191 وبليلة112036926257 اكتملت؛ m_abdulkareem112036926022/noah_warsh112036926298/nufais112036926175 جارية. طبلاوي112036926105 فشل strict container probe قبل أيقياس؛ لا تتجاوز الحارس، ابحث مصدرسليم. التقرير codex-112036926105-verified.json.
- الدرويش53:57 **ليس مجرد حدقصير**: التفريغ الحر321..335ث يقرأ53:35–37 بينما الفهرس ينسب56–58؛ سياقالمحاذاةالمفروض غير صالح، لا تصلحه بهذه الأرقام. يستلزم محاذاةالسورة/المقطع الموسّع والتحقق من المصدر. الكوشي11:118 اتفق النموذجان/القناتان على2320730..2334791 وقرآه التفريغالحر؛ تعديلبدء118 ونهاية117 ممكن بعد حفظالدليل وحراسالسياق. بليلة69:49 يبدأقبلنافذة448؛ كرر بسياق أوسع مبرر، لا تعتمد صف49المفروضconf0.
- بناءالعكري4 الجديد37386801366/job112021946483 **اكتمل لكنه ليس مرشحاً صالحاً**:176صفاً،48LOW؛4:140 heard=false/conf0 ومدتها9087ms لـ133حرفاً (3932623..3941710). نفسالفجوةالمعروفة لمتُحل. التقرير الكامل المثبت SHA87c28910f566758791e7af5696cfebc5d7bb3e4b927f0f93b424928e410ac98a فيcodex-112021946483-verified.json. لا تكرر نفسالمصدر،لا ترقي.
- قياساتQuran37389920485 الثلاث مكتملة ومحفوظة: codex-source-quran-{saad28,saad45,shamrani79}-37389920485.json. الشمراني79 بقيت11/15/17/19/46 قصيرةو8LOW؛ ليسمرشحاًكاملاً. سعد45 آخرآيتينconf0،سعد28س44أصبحت معقولة642440..651252 لكن15LOWبالسورة؛ المحاذاةالضعيفةلا تثبتغيابالنص ولا تصلحللترقيةوحدها.
- جميعالتشغيلات العامةقياسية restore-only بلا cache-save/artifacts. المهمة **غير مكتملة**. تابع النتائج/تصحيحالجذور/المصادر ثمالحراسالأصليةوالجرد؛لا شهادة100%.

## Verified continuation — 2026-10-06 00:35 UTC
This section supersedes older status above. Work is NOT complete.
- Five production adoptions verified bucket/public/manifest/frozen: peshawa ca0edef5fdef1f4a6bcf404c805d1be10e295cb36c76db87d959670a82b9675e; s_sadeiq 927e8bbeb319abb25d47930f588410d9bc41c87dc68ee63486ea2ad11acfde34; rakbawi_qalun 3d8dc7c9e31f3579939f7607efbc38ae142aec17900025b49fa3320ec71c09fc; nufais 31106cbe8babd4d506b5e5ccf0c75980e7652ec60791f259fb30ae2c4078b43c; noah 944dfdfa68b7af5bd7ecad949edb6abd38c4dfba94bbce8763761711cdddf4b4. Preserve LOW confidence; no perfect-accuracy claim.
- Full production audit at 00:22:04Z: full-audit-codex-after-five-adoptions-20261006.json/.md; 180/180 identity/structure/gap checks, 1,121,596 entries, 884 missing (431 restored), 6 impossible-short, 439 very-short, 3085 duration outliers, 114 extreme-long across33 indexes, zero stale mirrors. Missing: 3siri206, nasser165, saad203, shamrani46, akri210, iraoui54. These counts do not prove acoustic completeness.
- Active final-SHA QA: derini_warsh stage cb38c0c1, run37391361008; f_khamery41ff45fa run37391369081; zahrani6a5b3f68 run37391377124. Older stages fd3b23b0/d58b78bf/b962a19c were superseded/cancelled: DO NOT promote.
- Context repairs staged, not adopted: koshi_warsh db629f87eb79a0aca87c547ebc5856f08174e263be41591a4a984e4a616fa9d1 run37392955274 (11:117end/118start2320730); m_abdulkareem_warsh e3279a0914c45bc72ef6c24ed02ff3196ce3e3664936c352bc85ce60bcd31323 run37392963302 (21:48 at639760..650789). All original gates still required.
- Darweez53 whole-surah build37392369649 recovered62/62 after proving old middle/tail mislabeled. Stage249d793b5981505494ee1e4a120df5a2d2593ef0a99276ef09052c940fb010f1, parentd14fedebbae69f2e29b83d5c081e72214d532fa4a6efb4d094252a9e98a57342; QA37394065900 active. Boundary diagnostic37393561427 completed: free opening first consonants after candidate starts; final62 spoken end486340 within candidate end487157. Raw evidence and reports preserved in this commit. No adoption yet.
- Balilah: actual prior stage26fcdd889052efeb863782dc31b8c9d41db19b33f9908da855e076226e759ca2 exported and verified. Surah69 recovered onto current parentf1b40abe72f4f85bd41cc87166f2cf8785960c1e267f09816b99532851812207, final52 end470164 was clipped; two native free Quran paths end final consonant472152 and forced end472276, new end472500 below decoded EOF473887.375. Verse26 start275598 retained: four context paths start275618 and free first waw276112. Old +1.6s heard rejection retained; NOT bypassed, new float32 heard/full QA mandatory. Local candidatef8f51b82ab0bb58a42c23c466fc5cd259b09c5e5b5876bf44b7856963a9574be, 52 changed entries, no population change, original structural/index gates passed. Stage command0060 queued in same commit.
- Expanded diagnosis37392377734 proves noah_warsh54 source jumps15 to18 in both independent free models; forced16/17 conf0. Do not fabricate intervals; find complete recording. Akri4 new source still cannot align140; Akri24 and Iraoui41 remain truncated.
- Independent Whisper architecture diagnostic37394073433/job112045743599 SUCCESS,5 native windows, no prompt/canonical text. Complete envelopes independently hash verified and preserved. Free transcripts noisy and token timestamps approximately uniform, some segment ends beyond cropped input; NOT boundary witnesses. Saad45 does recognize final العزيز الحكيم; previous forced conf0 cannot establish absence. Saad28 partial44; Shamrani partial11/16/19. Further targeted diagnosis required, no adoption.
- Tblawi alternative Way2 uppercase007.MP3 metadata37393574696: SHAec1ccc7f0f052e500eb173757d0ead4503071db2fbe9ce501c20fb156b0ca361, strict healthy mono16k10841.868sec (~3h). Identity/Surah coverage not established; bounded head/tail free diagnosis before full processing. Original audio failed strict probe; do NOT bypass.
- No new cache saves/artifacts/model uploads. Public standard CPU only. Follow-up automation is not a verified unattended agent; do not promise days of background AI.

## 2026-10-06 01:06 UTC — continuing, NOT complete
- Seven production adoptions confirmed: peshawa, s_sadeiq, rakbawi_qalun, nufais, noah, zahrani (6a5b3f68...), derini_warsh (cb38c0c1...). Derini command 20261006_codex_0105_adopt_derini confirms bucket/public/manifest/frozen. Pooled upper 3.76%; rs4 disagreement 5.0% retained.
- Latest full audit still 884 missing entries; no 100% claim. Package catalog audit 0090 found six adopted package hashes stale; production files alone do not prove offline app delivery. Existing package workflow has artifact/new snapshot storage and must not be dispatched unchanged. Preserve certified catalog and ID-removal gates.
- f_khamery 37391369081 census still running; all other checks passed. Darweez replacement stage timings-staging/hafs/darweez.47ef82a5.jz SHA47ef82a5541a9e71e6e25fd83c8608020512f5c9f8ce7583ce9801bbc234140e uses measured decoded EOF487131ms; full QA37396095612 underway. Superseded run37394065900 canceled through guarded command0095; never promote old249d stage.
- Koshi db629f87 and MAb e3279a09 rejected by heard QA. New context diagnostics37395546994/37395853329 completed and show additional genuine start errors; original rejection remains. Verified local raw bundle SHA bfcba41a35343a69709510858aa49b0899a01ba17f71eee3f1452911045d2ca3, reports cefb8f1d30cae7276120f2e6d6bd6e8286ab85f87ff47394d2c237afe6978d7b (publication pending).
- Balilah097eb5a0 rejected at69:26 again. New native PCM pause diagnostic measures quiet midpoint independently of QA threshold; no timing changed by probe, no models/cache/artifacts/R2 writes. Never nudge merely to pass.
- Saad22 full Quran diagnostic37396596654/112053959165 completed:78 entries,24 LOW,43/70 conf0; forced coverage alone not proof. Source bytes match original. Saad28 tail context37396603183/112053981792 completed; free Quran recognizes final phrase with errors; endpoints need measurement before recovery. Saad45 tail36/37 present in independent contexts; Sham79 last46 present, interior8–20 still needs repair.
- Tblawi long alternate007.MP3 strict-decodes10841.868s and head/tail recognize Araf1/206. Reciter/recording identity and full indexing remain unverified; no adoption.

## 2026-10-06 01:19 UTC — new measured results, work ongoing
- Source context evidence bundle/reports from37395546994+37395853329 now PUBLIC (hashes above). Warsh v2 stages: koshi_warsh.1f0f0a30.jz SHA1f0f0a30bc7c4fc46f5b161d52cfa9153afaedd9612f4752f32dc1fdb8b9352a, fullQA37398041993; m_abdulkareem_warsh.fbf2b799.jz SHAfbf2b7997b428c6b45e858f11aecf681337dfbd5f2e69f57a65c43e275bb939c, fullQA37398048723. Never adopt old rejected stages.
- Saad all203 missing rows recovered in LOCAL+STAGED candidate, NOT adopted. stage timings-staging/hafs/saad.b208a747.jz SHAb208a7472e4ead42b9af8b0f1186c558acb332da18ca097da49e401773897c2b parent8e9f8131711748d617a6339a1d1ab5a511959bf4eb396700d9d4fdf724a747c0; full QA command0140 queued. Same original audio bytes; ctc_quran_surah_splice22,28,45. Preserve LOW incl22:43/70 and45:36/37. Final decoded EOF22=1046909,28=1321038,45=381048ms. All raw evidence public. Partial125 builder was correctly blocked by inherited OTHER gap guard; complete203 candidate passes unchanged guard. No gate modification.
- Darweez47ef82a5 all7 audio checks passed. Review112058410909 failed only stale catalog diagnosis. Diagnosis37398121497 success; guarded review-only retry0135 queued with immutable failure witness. No audio tests repeated.
- Public reconciliation37398245187/112059264805: all180 manifest hashes match actual public bytes;120 package declarations stale. Four previously package-certified readers now uncertified in reciter catalog:3siri,nasser_almajed,akri_qalun,saad. Original ID-removal guard blocks dropping such packages; DO NOT bypass guard/fabricate certificates. packages/catalog.json SHAc3ebbb44023da60a4c17573b1ee323c6ebe166517cea2295469fbf09e3434ca5. Report ops/out/source-report-112059264805.json. This supersedes the earlier six-row spot check.
- Balilah native pause probe37397631039 failed honestly: no contiguous120ms quiet interval meets RMS-50/peak-40dBFS. Report SHA7ee765fc75c4d03c76b00e4b5c6b0fa13bde225d99fd145c89ad461b223ee4d4 public. Do not relax silence/QA thresholds or shift boundary to pass.
- Shamrani79 interior new context37397731207/112057601088 still conf0 for10/11/15–19 with words missing in free paths. Tail46 present does not establish full source. No candidate/adoption; seek different full source.
- Alkabbah500375 already probed0930 with0 audio links; new bounded dynamic-link extraction inspects public script/API hints (different extraction, not duplicate audio probe). Quranpedia recitation356/surah79 is new publisher lead. No bypass of403/429.

## Continuation 2026-10-06 01:46 UTC — eight adopted, new opener defects measured
- Darweez adoption is CONFIRMED: production SHA 47ef82a5541a9e71e6e25fd83c8608020512f5c9f8ce7583ce9801bbc234140e; output 0150_adopt_darweez_eof. Total verified production adoptions = eight, not 100% completion.
- Full audit 0165 / full-audit-codex-after-eight-adoptions-20261006.json: 180/180 identity/structure, 1,121,596 entries, 884 missing; five impossible-duration entries remain. No claim all audio is correct.
- Saad recovery 203 rows remains staged, QA 37398622156; heard/census still running, other five passed.
- Koshi v2 QA 37398041993 still heard/census. MAb v2 QA 37398048723 completed seven measurements BUT review 112065430460 FAILED: rs1 10/200=5%, others 2/200,1/200,4/200; pooled17/800=2.125%, dissent5% exceeds twice pooled and original D-109 refuses. Do NOT rerun unchanged samples or weaken gate. rs1 defects:11:22,16:9,18:90,23:52,23:79,69:47,78:33,90:5,90:11,90:19. Read pending 0240_mab_rs1_dissent output for full report.
- Khamery QA37391369081 census112037065245 still running; no cancellation.
- Complete fourteen opener diagnostics run37399039017 all measurements succeeded. 142 original envelopes saved SHA-verified in ops/out/codex-short-openers-37399039017-complete.json.gz SHA cb3fdc970c6edd70869d2b95ae5e9160096c06600726b8c96cce39480bacd2ee; full reports SHA d7f32ae6737470c6fefc78115cd70f2dca3606e40659edcf90f32cd3488d575f. Published commit757980524f949518fac4e6604b86c1c40143b458. Not all fourteen are simple timing repairs.
- First opener batch staged/readback verified, original confidence retained, QA active:
  - a_alhazmi77 stage timings-staging/hafs/a_alhazmi.d7db9b14.jz SHA d7db9b148c9b1c4c91ad51b613eecf9fe1caf3d41c46d665a46bda0e6ff2fa95 parent64b9c22bf0f97ee087421a604620a755f3d2e0645285f630f3956af4d26d5c41 QA37400472678.
  - a_alqrafi108/113 stage timings-staging/hafs/a_alqrafi.3e2c3d79.jz SHA3e2c3d79aeeb28cf188f7a861c34cd074d6ae400df54580a13b215aea65d22cf parent49ccfc5e38ae71207f3d5e36d32193288126b69c497194964c17b192ae69fbcd QA37400479163. Kawthar final end13051ms exact floor decoded208817frames, both free transcripts full final verse.
  - arkani77 stage timings-staging/hafs/arkani.e91e80ef.jz SHAe91e80ef87105440227bf7adf7bccedfd559738f23dc7b16424065c41b9e65b9 parentdb61739dc864ec243f104fd04461560856a27c0e5da18ef5f0b92e65bac7bea0 QA37400486584.
  Builder tools/index_qa/build_short_opener_repairs.py; proof codex-opener-first-four-repairs-20261006.json. Only first3 bounds changed, unrelated entries unchanged.
- Second opener batch builder tools/index_qa/build_short_opener_repairs_second_batch.py, local index gates and structural pass; commands0240_stage_opener_* pending or executing. hatem54 only FIRST START moved to2964 (one row); connected ambiguous next boundaries retained. mukhtar_haj37 first3 rows measured; rabbani_warsh56/102 first3 each measured. All original conf preserved. Read resulting STAGE_RESULT, then dispatch exact-SHA free-post-stage-quality.
- Full source recovery diagnostic after severe multi-verse displacement: mrifai84 initial37400016387 failed BEFORE audio/model inference (float/over70sec window). Fixed source window to integer[0,65] without changing shared70sec limit. New run37400755423 active, job112067177768.
- Benkirane77/51 and Yousef107 initial37400390272 ALL failed before inference on invalid sample window. New inputs integer[0,65],[0,65],[0,36] and full-source CTC alignment, run37400824039 active. Jobs112067390253/341/240. Do NOT repeat old runs. Full alignment alone won't prove completeness; tail/context followups still necessary.
- Two further source-content issues found in opener batch: obk1 free both models starts الحمد لله رب العالمين; no basmala recognized, forced1:1 conf0. shaykhna_qalun27 source SHA f328d0b1eef8dfea3a88ed0833dd81e1b69eaabe4b2d7e43aff4108e90e8355f begins27:56 فما كان جواب قومه..., not27:1; all forcedfirst3 nearly0. No repair candidates created for these sources.
- NoahWarsh54 full-surah drop STAGED ONLY using existing drop_surah after verified missing16/17, reasonSOURCE_TRUNCATED: timings-staging/warsh/noah_warsh.b99262ae.jz SHA b99262ae6b1b13592a29025d3cfc9760029a2e0c13769768808459e5f3f51437 parent17191c80f66c87db6f31f8bea091ab8f2e526083e8e4bc6a318aefe42b44a029. Entries6181,missing55; structural report codex-noah-warsh54-drop-struct-20261006.json no fatal. QA37400592474 correctly FAILED plan: free-post-stage guard supports non-dropping stage_transform candidates only (manual-free-only metadata, entry inclusion). DO NOT weaken this guard or repeatedly dispatch incompatible workflow. Need established guarded drop path / dedicated strictly source-proven whole-drop QA. Production unchanged.
- Shamrani Midad stereo context37399245406 failed HTTP403. Do NOT bypass or retry same refusal. Metadata previously healthy does not establish current access or completeness. Quranpedia source resolves to original mp3quran source; Alkabbah500375 archive n2-mp-3_20230516nnnnnn is already known truncatedAkri24, not a new lead.
- Package report source-report-112059264805.json:120/180 stale package SHA/bytes, all180manifest/public agree;4 previously packaged IDs currently uncertified. Existing certified_only/id_diff gates still apply; no package publication yet.
- Financial constraints unchanged: public standard runner, restore-only existing cache, no artifacts/cache-save/audio uploads/new paid resources. All new source probes bounded CPU/temporary disk. The [skip ci] markers on initial0180/0185/0190 commits skipped dispatcher; corrected via whitespace-only update to EXISTING pending0180 command at0831e809, no duplicate commands. Use ordinary commit messages for intended free dispatcher, [skip ci] only evidence-only updates.

### Second opener batch staged and read-back verified
- hatem: timings-staging/hafs/hatem.29a2011a.jz SHA 29a2011ab36f3439dafaca34bf0a9a81dec1221205c1e24ea7b997c034a35f17; parent 5d7e73699ae633807bd57ecb60ea235f503318fdacf8c13bd3b81132eb10f85e. QA command0250_qa_opener_hatem.
- mukhtar_haj: timings-staging/hafs/mukhtar_haj.23c82612.jz SHA 23c82612a4ed9ff243a92b949aee1b856cf60b7b79dd45661108fb37d738ae15; parent a01f926802dc95b0ae76ea74ac5f9b5521b1b94d5a7977e3c0fdb6f7bd5d25d1. QA command0250_qa_opener_mukhtar_haj.
- rabbani_warsh: timings-staging/warsh/rabbani_warsh.f5ac191d.jz SHA f5ac191dff105512c2d131fc81aa70a1de857a04331dbbfb1c1ce460e1cd9dc0; parent d9534de9ed7aed07154a5784f2cefc5b7fef16981061bf9e4c3f9bc22a44b2aa. QA command0250_qa_opener_rabbani_warsh.


## Continuation 2026-10-06 ~02:13 UTC — ten confirmed production adoptions, NOT complete
- Koshi ninth adoption0290 confirmed: production1f0f0a30bc7c4fc46f5b161d52cfa9153afaedd9612f4752f32dc1fdb8b9352a; manifest/frozen/public readbacks verified. Final QA37398041993 review112069666615 passed.
- Khamery tenth adoption0350 confirmed: production41ff45fab5c6d86e11666f412959badba691c340dc89f01af772b4a08185431a. QA37391369081 seven measurements passed. Initial review112070621144 rejected stale catalog diagnosis (NOT bad audio); refreshed via37402319573, reran ONLY review using GitHub job rerun, review112072836899 passed. Adoption readbacks verified.
- New independent full audit after ten command0370 queued. Last full audit after eight had884missing; no missing recovery adopted since.
- MAb fbf2b799 REJECTED pooled gate: rs1=10/200 vs2,1,4 other salts; do not weaken/resample unchanged. Ten target contexts run37401794572 active; initial37401302973 failed before inference missing parent, retry includes verified parent binary. New measured-context-<job>-<part>.json evidence local, six contexts saved; remaining90:11/5/19 and78:33 pending collection. 69:46..48 shows broader tail displacement; do not create overlapping local patch.
- Saad b208a747 REJECTED heard37398622156/job112060548380:22:27,52,62;28:21,67;45only15/37 measured. Five native contexts completed37401685509, local measured-context files; models DISAGREE at22:27 and28:21;22:52/62 agree later than heard anchors. Do not force boundary to gate or fabricate confidence.
- a_alhazmi d7db9b14 REJECTED heard37400472678:77tails up to29s, sampled67tails up to41s. Hatem29a2011a REJECTED54:54/55 by5.95/10.62s plus sampled82:13 by1.83s; complete report local hatem-failure-5.json SHA811f271ce61e9011765c56132540072e2281a58fc1c0190b60af64e2b293fe4c.
- CORRECTION: Hazmi public codex-hazmi-67/77-heardmap files are HEARD-ONLY: entries=[]; heardMap complete. They are NOT full timing payloads and cannot be spliced. Initial0280Hazmi diagnostics failed before inference on false full-entry assumption; strict diagnostic loader now validates heard-only anchors and pinned rejection. Corrected native contexts37402708217 active, no production/index guard altered.
- Rabbani f5ac191d rs1 failed incomplete decode windows96:19,77:50,96:18 — NOT bad scored fraction; do not save partial witness. Others ongoing. Qrafi/Arkani heard+5checks passed; census still active. Mukhtar heard/census still active.
- Full Quran recovery Mريفai84 andYousef107 plus native tail contexts completed. Builder tools/index_qa/build_mrifai_yousef_repairs.py preserves ALL original confidence/metadata and changes23/7 timing rows; fixed verified decoded EOF151066/35683ms. Local structural/index/census inclusion gates passed. Evidence raw tail bundle af38059d7859854d60f0f0a1222c68f078216e8af7f2cdb2e04b91f2e74d3476 public.
- Mريفai stage timings-staging/hafs/mrifai.ef3855a4.jz SHAef3855a4a89f313631f3ee4f735cafaf99d160ee566475f37d795fff16c54b1c parent58adaf7636a7a58294889ccbf1e4318640a686020ab83b035066b2bc8c15059f; QA37402814303 active.
- Yousef stage timings-staging/hafs/yousef.d3bfe80b.jz SHAd3bfe80bf476a85f6961bdcb4c3748aa63c8061cd0a222a55fd0efc52dfeb7a3 parenta3d44fd95cdc47e6cb183a788d94ff287380f7de8306e0e0bc40267a09be3c72; QA37402820508 active. Neither adopted yet.
- Benkirane51/77 fullQ recovery completed but last9/5 rows compressed/LOW; reports public codex-benkirane51/77-recovery-20261006.json. Contexts initial37402500749 failed before inference because plan/script pin wasn't updated together; fixed and locally validated all six new/changed loader paths. Corrected run37402807010 active (51middle+tail,77tail). No candidate yet.
- Source context plan now39sources SHA f519e846b5ffa129ee17118815001f82d732c42573f8e36ae570a916df143340, script IDS/count/hash matched. Profile benkirane-tails and hazmi-tails added; all publicstandardCPU/manual-only/restore-only/noartifacts.
- New publisher inventory command0360: Midad149104 (Shaykhna/QalunNaml lead) and URL-encoded Tilawa NoahWarsh page; bounded HTML only, pending result. No403bypass.
- NoahWarsh54 drop b99262ae remains STAGED ONLY, non-dropping post-stage guard rightly rejects. Need original intentional-drop path with explicit source evidence, do not weaken guard. Package catalog120stale still unresolved; no package upload.
- Everything remains free-only, existing bounded index/state writes only; no paidcache/artifacts/audio/modeluploads. Check outputs before repeating commands. No100% claim.


## Continuation ~02:31 UTC — native-tail batch and exact-SHA follow-ups
- Production still10confirmed adoptions. Audit full-audit-codex-after-ten-adoptions-20261006.json completed:180identity/structure pass;1,121,596entries;884missing;4impossibleShort;3081durationOutliers;436veryShort;140silenceGaps. No100%.
- Qrafi all7measurements37400479163 passed; review112075691863 rejected STALE diagnosis only. Refreshed diagnosis37404158088 success; reran original reviewjob at~02:30 (read jobs filter=all for new review result, then adopt only if success).
- Mrifai all7measurements37402814303 passed; review112077942613 rejected STALE diagnosis only. Refresh command0500_mrifai_refresh_diagnosis queued; wait success then rerun only original review, no repeated audio.
- Yousef37402820508 heard+5 passed,census stillactive. Arkani37400486584 census stillactive. Do not cancel slow census.
- Hazmi native diagnostics37402708217 completed3contexts; real starts67:23..30 and77:43..50 consistent across4measurements. Builder build_hazmi_native_tail_repairs.py repairs21rows including earlier opener, preserving original confidence. Initial0400stage rejected missingcanonicalTextChanged=false in model provenance; v2fixed truthfulmetadata only. STAGED7498fa1e5a270e8263d93e19aaaadc963769879cd84f6eea0e2ea39add73fc96 at timings-staging/hafs/a_alhazmi.7498fa1e.jz, parent64b9c22bf0f97ee087421a604620a755f3d2e0645285f630f3956af4d26d5c41. Localda4c26adaa9a104a7c4c5d6d2cb78a40f10d8074abd2800b3e7e206211af7a98. QA37403895659 active. Raw native bundleb2f49d13fb91aaa4b5d9ade4b7ff37ee3f3431b65a19e64a7715565ba739b9ef.
- Benkirane native contexts37402807010 all3passed. Builder build_benkirane_measured_repairs.py repairs92rows in51/77 from fullQ source alignment + measured tails, original confidence preserved. Native51:56 overlappingcontexts differ430ms (documented, fullQArequired); choose earliestmeasuredQstart402489. STAGED0036ef1598e1bf8329e066e00c938941b6774c631b9f8378b91fb24d4d65965b at timings-staging/warsh/benkirane_warsh.0036ef15.jz parentf98bc7b302a415e1755ac319cb900f546ac25d3229d8a77e6014b4fe46fae300. QA37403886936 active. Local20f6052e322bc3dc50a61c34fb2a07f86b1999563119fd533219679602b8e834. Bundle5359e95e8537b707fca31841d7bb8aca1e3f3478fd08152d32e921940dcff6a1.
- Expanded parent-pinned diagnostic37403263010 all5success: Rabbani77/96 EOF, Hatem54/82, MAb69tail. Script47sources now with strict pinned-parent branch, diagnostics only. NewMAbadjacent contexts37403983730 (90:4..8 and10..14success,78:32..36stillactive). ExistingMAb10contexts37401794572 allsuccess.
- Rabbani native EOF proves77ends265483ms,96ends90646ms (old265508/90671 overactualPCM25ms). Keep run.py _eof_pad_ok strict! Builder build_rabbani_decoded_eof.py repairs2ends + previous6openerrows; native96:15partialcontext deliberately unchanged. STAGEDb63e9f0efa8eaa0ae0eccb6988d7759ea136b582539f476b21efeaabf0b4d2b0 at timings-staging/warsh/rabbani_warsh.b63e9f0e.jz parentd9534de9ed7aed07154a5784f2cefc5b7fef16981061bf9e4c3f9bc22a44b2aa. QA37403991096 active. Local5e9547a6890985ab372a377e2fd39c21acf1d2b04f41ab3ff618fa3cd879f292. Bundle8500798e28b8aea136d88c3f288f633a776b1dc91d315993ac1c93067c480df7.
- Hatem54tail native measured52start374019,53start379265,54start385591,55start392778 andEOF401737; builderbuild_hatem_tail_repair.py changes6rows includingearlieropener. STAGED3cdfac1a56023efdb56350f5440f1c18b42e8dc08ae2f10984b9c011fd2609d0 at timings-staging/hafs/hatem.3cdfac1a.jz parent5d7e73699ae633807bd57ecb60ea235f503318fdacf8c13bd3b81132eb10f85e. QAcommand0490_qa_hatem_tail dispatched/pendingoutput. Local3642fbb136a56442ab0b77d7b3104e442b5bc4e7298d3e72d7068f6478a0c7ad. Hatem82:13 nativeQ63202/generic63523..63543 vsparent63093 andheard64924 disagreement; leaveunchanged, do not force boundary toward gate. Rawbundle8014c224db28529f662d9d1131d5df7f262dba8a9817c2e4bb0cef1b5311c970.
- Mukhtarfirst-onlycandidate23c82612 rejectedheard112068109339:37:19,25,84,153,163,166 (max163−4.3s). Full logs in store mukhtarHeardFailure; reportSHA badb9ea2e85acfc90336a744f0cc5375266045ccceac33e72c13fd6cdb3a914d. Not adopted; census stillrunning.
- MAb full69tail provencompressed beyond earlier3versecontext:45=283501,46=287233,47=291986,48=297938,49=303392,50=310756,51=316218,52=320661,EOF331206. Need v3 combining21v2 + stable rs1 repairs and tail69; preserveconfidence. 23:79 targetstart861160 butfinalcontext80speechends877622>parent80end877266; do not blindly shift81withoutmeasurement. 90expandedcontexts nowbound adjacent starts,78contextpending.
- Completed local native envelope files measured-context-<job>-<i>.json SHAchecked. Public partialbundle codex-rejected-contexts-partial-20261006.json.gz includes13reports197parts, SHA88e55971704976b32b292facf7c02ead86e8a9a9a642994e67abe992ceb32f5e. Subsequent2MAbfinal+3Hazmi+3Benkirane+5expanded+2MAbadjacent collected locally; relevantbatchbundles publicexceptremainingMAb.
- ShaykhnaMidadNaml publisher149104 yielded fra1.digitaloceanspaces.com/media.midad.com/resources/ar/recitations/47178/458330/027.mp3. Metadata37403176102/job112074730460 gotHTTP403: no retry/bypass. Tilawa URLencoding worked butlinks SAME known NoahWarsh archive, no newsource.
- Rechecked existing automation6aaad3d05d108191b8f561114e898ced: wasdisabled; userresumeauthorized re-enabled same task02:26UTC, updateconfirmedis_enabled=true BUTnext_run_time=null still. No newduplicateautomation; no unattended execution guarantee.
- No newagents; no paidresources/cache-save/artifacts/audio uploads; original quality gates intact.


## 2026-10-06 02:52 UTC continuation — fourteen adoptions, work incomplete

- Confirmed 0510 Qrafi and 0550 Mrifai, plus 0580 Yousef/Arkani production readbacks (manifest/public/frozen all verified). Fourteen distinct repaired production indexes now adopted; no 100% claim. Yousef SHA d3bfe80bf476a85f6961bdcb4c3748aa63c8061cd0a222a55fd0efc52dfeb7a3; Arkani e91e80ef87105440227bf7adf7bccedfd559738f23dc7b16424065c41b9e65b9. Their original final-SHA reviews passed (112080421082 /112080418595).
- Hazmi QA37403895659 heard+five checks passed, census still running. MAb v3 QA37404955181 rs1..4+openers passed, heard/census running. Hatem QA37404237192 rs1..4+openers passed, heard/census running. Do not promote before original full review acceptance.
- Rabbani QA37403991096 rejected: heard96:7 +2.3s; census56:96 decoded EOF576001ms versus stored576026ms causes two incomplete windows. New native contexts56:92..96 /96:5..10 queued by0600. No gate changes or rerun to hide failures.
- Benkirane QA37403886936 rejected77:27. New context37405223677/job112081180079 measured Quran start116072ms vs generic121596ms, parent/candidate116073ms. Model disagreement remains; do not force timing to heard gate. All13 original context envelopes SHA-verified locally.
- Mukhtar six contexts37404856619 passed, all78 original envelopes SHA-verified. Native starts support genuine repairs; adjacent37:20 ending disagrees with parent, so0600 also measures37:20..22 before producing final candidate.
- Dedicated noah_source_gap_quality.py and tests published8a290ed231b32a49a4e6bf9bfba3a2e717de7145. Only immutable b99262ae6b1b13592a29025d3cfc9760029a2e0c13769768808459e5f3f51437 on parent17191c80f66c87db6f31f8bea091ab8f2e526083e8e4bc6a318aefe42b44a029 is allowed; every6181 surviving row proven byte-equivalent in content, all55 Qamar rows removed per owner middle-gap instruction. General non-dropping guard unchanged. Mutation tests pass. Dedicated free QA37405972254 plan passed; seven original audio checks started. No production drop yet; existing non-dropping adopter is unsuitable. Any eventual adoption must retain all original quality gates and explicitly bound authorized shrink reason.
- Source diagnostics plan now57 sources, commit581985a6987bf4adc9504bded1f5003b919d8293.0600 profile final-rejections = rabbani56_tail,rabbani96_5_10,mukhtar37_20_22. Strict parent/source binding locally validated before dispatch.
- Public/free standard runners only; restore existing caches, no artifacts/cache-save/new audio/model storage. Source884 missing and catalog blockers remain. Scheduled automation next_run_time was null despite re-enable; unattended resumption NOT verified.


## 2026-10-06 03:10 UTC — continued source recovery and revised candidates

- Fourteen adoptions still confirmed. New full-audit-codex-after-fourteen-adoptions-20261006.json:180 identity/structure/gap-contract pass;1,121,596 entries,884 missing;4 impossibleShort,429 veryShort,3074 durationOutliers,114 extremeLong. This is NOT an audio completeness certificate.0670 completion_audit --live currently queued/running to reassess actual start/end evidence after production changes.
- Mukhtar revised stage timings-staging/hafs/mukhtar_haj.7fd5be19.jz SHA7fd5be19ce4a65969e90d1111c342c99b62da4dbc8d147f4a0e7f3c49b132933; parenta01f926802dc95b0ae76ea74ac5f9b5521b1b94d5a7977e3c0fdb6f7bd5d25d1.28 rows changed, original confidence. Full QA37407043331 active. Adjacent37:20..22 context37406073805/job112083830200 resolved prior forced end into21; all models now agree. Builderbuild_mukhtar_rabbani_final_repairs.py, public original envelopes preserved.
- Rabbani revised stage timings-staging/warsh/rabbani_warsh.9769ff3e.jz SHA9769ff3e9af0b03fdc4b4064b14b47cf21003e8475b26a3abdd27559b2e20903; parentd9534de9ed7aed07154a5784f2cefc5b7fef16981061bf9e4c3f9bc22a44b2aa.11 rows changed. Full QA37407050313 active.56:96 EOF576001=floor9,216,017PCMframes.96:6/7 boundary28126ms from both Quran native ends of6, bracketed after final free Quran character28.092 and before generic first hamza28.232. Later Quran7 start29.277 was not chosen because it might omit hamza. Model disagreement explicitly documented; original LOW retained; no heard/quality threshold changes. Old rejected reportcodex-rabbani-heard-rejection-37403991096.json retained.
- Benkirane77 remains unresolved: generic free ASR contains repeated partial77:27 phrase (first wajalna116.572s, second122.092s), Quran free collapses repetition; old candidate's116073ms preserves first. Do NOT move it late merely to pass heard gate. Separate51-only candidate changes50 rows and leaves77 exactly as parent. Staged timings-staging/warsh/benkirane_warsh.4f3ed339.jz SHA4f3ed339d7fdeb254c2fcea460864c9d191e32809a645a5a9e8bdd8e06f3110a; parentf98bc7b302a415e1755ac319cb900f546ac25d3229d8a77e6014b4fe46fae300.0680 QA command queued. Combined old0036ef15 remains rejected. All native/free evidence and original heard rejection public.
- NEW promising Tablawi Araf publisher source: https://www.nquran.com/ar/view/10716 -> https://www.nquran.com/audiof/quran/mohd_muh_tablawee/007.mp3. Metadata37406467384/job112085041049 success:35,032,209 bytes, SHA76b0d10dbb33d90cdbb98e71786653a497dbe73f7af704bf2297848ce1fbc547, PCM70,049,542frames16k =4378.096375s; stereo/native clean, no >15s silence. Duration closely matches old4377.920 end, unlike earlier3h mujawwad alternate. Publisher declares same reader/Hafs/murattal but identity/coverage NOT certified. Full Quran alignment37406959272/job112086539095 active; one-source bounds exact35,032,209bytes and<4400s, generic shared limits unchanged. Metadata publiccodex-tblawi-nquran-metadata-37406467384.json SHA222a0abcea6e4ac6444eac886a4bcf00ca24a590f9cd3e6d883e04ee86002ed2.0680 separate native head1..3[0,70],middle23..26[360,430],tail204..206[4320,4379] diagnostics queued. source_context plan60sources, strict metadata SHA branch, commit1b7796bff3e6b14d59a8ecb6abd13d5e153a1af5.
- NEW Shatri Fatiha publisher lead https://www.nquran.com/ar/view/3870;0690 metadata probe queued for public download link. Current obk1 source basmala remains unverified/missing; no replacement adopted.
- NoahWarsh54 exact-gap QA37405972254 heard/openers/rs1..4 passed; census pending. New dedicatedadopt_noah_source_gap.py published as PREPARATION ONLY, not allowlisted/dispatched. It pins original QA run37405972254/commitc33da11fc39f71bb3ee159d9c66373130635cd93 plus exact candidate/parent/source-evidence, all original gates/read-only preview/refreeze/readbacks. Provenance mutations and fail-before-unfreeze tested locally. Never invoke before original full review passes.
- MAbv3 QA37404955181 census+openers+rs1..4 passed, heard still running. Hatem QA37404237192 heard+openers+rs1..4 passed,census running. Hazmi QA37403895659 heard+openers+rs1..4 passed,census running. Refresh stale diagnosis only if original review needs it; do not treat finished individual jobs as a completed review.
- Existing hourly automation6aaad3d05d108191b8f561114e898ced still enabled but next_run_time null and last_run_time2026-10-05T18:49:45 at03:06; scheduled03:00UTC run not verified. Do not promise unattended AI continuation. Existing actual GitHub QA runs continue independently.


## 2026-10-06 03:21 UTC — independent source contexts preserved

- Production remains fourteen verified adoptions. Completion audit after fourteen is finished, ready=false, errors=[]:180 indexes,884 missing,859472 unmeasured starts,7791 start deviations. All1121596 ends lack accepted current-SHA independentWindowCtc evidence; this is an evidence gap, NOT a claim that all ends are wrong. Report: completion-codex-after-fourteen-20261006-summary.json. No completeness claim.
- Tablawi new source native contexts37407533559 all succeeded. Jobs112088317067(head),112088317206(middle),112088317200(tail);51 complete envelopes SHA/length verified. Public reports codex-tblawi-new-contexts-20261006.json SHA b1654d32b184481a0a5f85547704ec7a5db5eaf7e00118c75e0b2aa47c1e694c; complete raw gzip e44e069daaf9c555384ab12c9ab705d599903dc3ffe9d510cb0d028c6cc4fe87. Free generic+Quran support head1..3,middle23..26,tail204..206 including final yasjudun. Native Quran starts7:23=362602,24=378896,25=392188,26=401455;tail204=4337771,205=4348037,206=4364388. Full recovery37406959272 still running. No source replacement/candidate adoption yet; full coverage and source identity gates remain.
- Obk publisher download probe37407618713/job112088588689 failed with invalid URL during redirect before audio measurement. No access denial. Publisher file parameter decodes to audiof/quran/Sh_ shatri/001.mp3;0700 probes corresponding public path with space correctly percent-encoded. Do not modify URL validator, bypass access denial, or infer basmala presence without measured audio.
- Hazmi/Hatem/NoahWarsh drop awaiting census;MAbv3 awaiting heard;Mukhtar/Rabbani awaiting heard+census;Benkirane51-only awaiting remaining checks. No original review complete for these candidates as of this checkpoint.
- Noah drop candidate has legacy missing.note about pre-completeness provenance while actual missing.byReason correctly declares source_truncated55 and transform has measured reason. Do not silently edit immutable candidate or reuse QA for changed bytes. This metadata issue remains to resolve before final completeness reporting.
- Recent commits0e77e089f87eeb279309aa7f86023e9a2e2a9ed3 stores source evidence [skip ci];09a5fd1a0fba51b09be4d6ca88d50fd1645bdc07 dispatches0700. Public standard CPU/no artifact/cache-save/audio uploads. Existing hourly automation still has unverified next run; actual GitHub runs are independent.
