# -*- coding: utf-8 -*-
"""اختبارات D-025 الإلزامية + كاتب TimingIndex بصيغة 4.2 المجمَّدة.

HIGH يدخل تلقائياً · MED موسوم · LOW لا يُشحن (قائمة استثناءات).
"""
import hashlib
import time

AYAH_COUNTS = {"KUFI": 6236, "MADANI": 6214}
# عدّ آي كل سورة بالعدّ الكوفي — **مرجعٌ خارج الفهرس**. وهذا شرطُ صحّة حارس
# الاكتمال: الآية المفقودة **تسقط من الفهرس رأساً ولا تُكتب مدخلاً فارغاً**
# (قياس github-8e على 1158 آية: صفرُ مدخلٍ بـ`startMs=None`)، فأيّ فحصٍ يمرّ
# على المدخلات الموجودة وحدها يرى فهرساً سليماً وفيه مئات الآيات غائبة —
# وهو حال `m_sayed_warsh` المنشور: 5906 مدخلاً بلا خللٍ ظاهر و330 آية بلا مدخل.
SURAH_AYAHS = [
    7, 286, 200, 176, 120, 165, 206, 75, 129, 109, 123, 111, 43, 52, 99, 128,
    111, 110, 98, 135, 112, 78, 118, 64, 77, 227, 93, 88, 69, 60, 34, 30, 73,
    54, 45, 83, 182, 88, 75, 85, 54, 53, 89, 59, 37, 35, 38, 29, 18, 45, 60,
    49, 62, 55, 78, 96, 29, 22, 24, 13, 14, 11, 11, 18, 12, 12, 30, 52, 52, 44,
    28, 28, 20, 56, 40, 31, 50, 40, 46, 42, 29, 19, 36, 25, 22, 17, 19, 26, 30,
    20, 15, 21, 11, 8, 8, 19, 5, 8, 8, 11, 11, 8, 3, 9, 5, 4, 7, 3, 6, 3, 5, 4,
    5, 6]
assert sum(SURAH_AYAHS) == AYAH_COUNTS["KUFI"] and len(SURAH_AYAHS) == 114


def band(conf):
    return "HIGH" if conf >= 0.75 else ("MED" if conf >= 0.45 else "LOW")


def check_surah(entries, ref_char_counts, total_ms):
    """فحوص D-025 على مستوى سورة واحدة. يعيد قائمة مخالفات نصية."""
    issues = []
    n = len(entries)
    missing = [e["ayahIdx"] for e in entries if e["startMs"] is None]
    if missing:
        issues.append(f"آيات بلا حدود: {[m+1 for m in missing]}")
    good = [e for e in entries if e["startMs"] is not None]
    # رتابة تصاعدية + لا تداخل
    for a, b in zip(good, good[1:]):
        if b["startMs"] < a["startMs"]:
            issues.append(f"كسر الرتابة عند آية {b['ayahIdx']+1}")
        if b["startMs"] < a["endMs"] - 50:
            issues.append(f"تداخل بين {a['ayahIdx']+1} و{b['ayahIdx']+1}")
    # تغطية: فجوة > 4ث داخل السورة مريبة (سكتة/صمت طويل يوسم)
    for a, b in zip(good, good[1:]):
        if b["startMs"] - a["endMs"] > 4000:
            issues.append(f"فجوة {round((b['startMs']-a['endMs'])/1000,1)}ث بعد آية {a['ayahIdx']+1}")
    # معقولية المدة قياساً بعدد الحروف (انحدار خطي بسيط على آيات السورة نفسها)
    if len(good) >= 5:
        rates = []
        for e in good:
            ch = ref_char_counts[e["ayahIdx"]]
            if ch > 0:
                rates.append((e["endMs"] - e["startMs"]) / ch)
        med = sorted(rates)[len(rates) // 2]
        for e in good:
            ch = ref_char_counts[e["ayahIdx"]]
            dur = e["endMs"] - e["startMs"]
            if ch > 3 and med > 0 and not (0.35 * med * ch <= dur <= 3.0 * med * ch):
                issues.append(f"مدة شاذة لآية {e['ayahIdx']+1}: {dur}م.ث لـ{ch} حرفاً")
                # آية-1 المسنودة بعزل تمهيد مدتها مقبولة (≥1.2ث) لا تُذبح بالإحصاء
                if not (e["ayahIdx"] == 0 and e.get("snapped") and dur >= 1200):
                    e["conf"] = min(e["conf"], 0.44)  # ينزلها LOW/MED
    if good and good[-1]["endMs"] > total_ms + 500:
        issues.append("نهاية آخر آية تتجاوز مدة الملف")
    return issues


REFINE_VERSION = "v2.1"
try:                                       # نسخة كاشف الصمت — من مصدرها لا نسخاً
    from vad import VAD_VERSION
except Exception:                          # noqa: BLE001
    VAD_VERSION = None


def make_timing_index(riwaya, reciter_id, source_kind, counting, per_surah,
                      engine_version="align-0.2", strip_low=False, vad_rel=None):
    """per_surah: {surah_no: {"fileRef":…, "sha256":…, "entries":[…]}} بفهرس كوفي.

    ⛔ تحوّل 2026-09-02: **LOW لا تُسقط بعد اليوم** (قرار المشرف بعد قياس 8e).
    كان المجمِّع يحذفها، فيرى حارس التغطية «غياباً» ليس غياباً: رُفض `a_majed`
    بـ«غياب 256» و**256 = 68 مفقودة + 188 LOW بالضبط** — أي أن ثلثي «الضائع»
    حدودٌ موجودة أسقطناها بسياسة. و`waleed_qalun` رُفض بـ93 منها 66 LOW و27
    غياباً حقيقياً (0.4%). فتبقى LOW مدخلاً موسوماً (المستهلك لا يشغّلها
    منفردة، وتصلح للتظليل المتصل)، والغياب يُحسب على المفقود وحده.

    عقد v2 (اتفاق مستهلك 2026-09-01):
    وكل مدخل جارُه التالي غائب لحظة البناء يحمل endApprox:true (نهايته امتداد
    مقطعي لا حداً ملصوقاً — لا يصلح تشغيلاً منفرداً)، والترويسة exactEnds:true.
    """
    entries, shas = [], []
    refined_count = 0
    med_targeted = 0
    refine_stats = {}
    present = set()                     # (سورة، رقم الآية) لكل مدخلٍ شُحن
    for sn in sorted(per_surah):
        d = per_surah[sn]
        if d.get("sha256"):
            shas.append(d["sha256"])
        surah_entries = d["entries"]
        n = len(surah_entries)
        shipped = set()
        # ⛔ **LOW تُشحن موسومةً ولا تُسقط** (قرار المشرف github-f4 ‏2026-09-02).
        # كان إسقاطها يجعل الحدَّ المقيسَ **آيةً غائبة** في نظر حارس الاكتمال،
        # فيُحجب فهرسٌ مكتمل: `waleed_qalun` ‏6143 مدخلاً و**66 LOW مُسقطة**
        # و27 بلا محاذاة فقط — فيقرأ الحارس 93 غياباً وحقيقتُه 27. والفرق في
        # **العلاج** لا في العدد: الغياب يوجب إعادة فهرسة، وLOW يوجب قراراً
        # عند المستهلك (يتجاهلها في المنفرد ويقبلها تقريباً في المتصل — D-057).
        # و`strip_low` يبقى في التوقيع للتوافق **ولا أثر له**، كيلا ينكسر
        # مُستدعٍ ولا يعود الإسقاط من بابٍ خلفي.
        for e in surah_entries:
            if e["startMs"] is None:
                continue
            # ⛔ **المدخل المقلوب أو الصفريّ لا يُشحن** (قرار المشرف github-f4
            # بعد رصد github-7e في `waleed_qalun`: مدّتان صفريتان 23:89 و26:210،
            # ومدخلان `end < start` في 26:48 و26:144). هذا **عطبُ تشغيلٍ لا
            # ثقةٌ منخفضة**: مدخلٌ نهايتُه قبل بدايته لا يُشغَّل أصلاً، وإبقاؤه
            # LOW يجعل العطب يبدو «قراراً عند المستهلك» وهو ليس كذلك. فيُسقط
            # ويُعدّ **غياباً بسبب `invalid`** — يُرى في التصنيف ولا يُبتلع.
            if e.get("endMs") is None or e["endMs"] <= e["startMs"]:
                continue
            shipped.add(e["ayahIdx"])
        for e in surah_entries:
            if e["ayahIdx"] not in shipped:
                continue
            row = {
                "ayahId": f"{sn}:{e['ayahIdx']+1}",
                "fileRef": d["fileRef"],
                "startMs": e["startMs"], "endMs": e["endMs"],
                "conf": e["conf"], "confBand": band(e["conf"]),
            }
            # endApprox يصف حقيقة النهاية لا حضور الجار (تدقيق مستهلك 09-01):
            # جار مفقود كلياً ⇒ النهاية امتداد قد ينزف فوقه ⇒ توسم.
            # جار LOW ملصوق (end == start جاره) ⇒ النهاية ترث ثقة LOW ⇒ توسم.
            # جار LOW غير ملصوق ⇒ النهاية قياس ذاتي لكلمات الآية نفسها ⇒ لا توسم.
            if not (e.get("snapped") or e.get("refined")):
                row["startApprox"] = True  # بداية غير مسنودة لصمت — عقد v2.1
            # ⚠️ درس 2026-09-02 (‏github-1e): آثار الصقل كانت تُقرأ هنا ثم تُجرَّد
            # من المخرج، و`engineVersion` يبقى `align-0.2` في الجيلين — فلا يستطيع
            # مدقّقٌ فرز Gen-1 عن Gen-2 آلياً. وقد كلّفنا ذلك ساعاتٍ الليلة: كان
            # الأسطول يفهرس بلا صقل ولا شيء في المخرج يقول ذلك.
            # **المقام قبل البسط:** `refinedCount` وحده بسطٌ بلا مقام — «17 حدّاً
            # صُقل» لا معنى له حتى يُعرف من كم. والمقام **لا يُشتقّ من MED
            # الباقي في الفهرس**: المصقول يخرج من MED بالترقية فيخرج من مقامه،
            # وقد أعطى ذلك فعلاً نسبة **124%** لأحد القرّاء (قياس github-b9).
            # فالمقام هنا **ما دخل الصقل فعلاً**: كل مدخل خرج منه أثرٌ — إمّا
            # `refined` أو `refineSrc` بسبب الإخفاق. وهما يُعدّان على **نفس**
            # مجموعة المداخل المشحونة كي تكون النسبة نسبةَ شيءٍ واحد.
            src = e.get("refineSrc")
            if src or e.get("refined"):
                med_targeted += 1
            # وسبب الإخفاق يُحفظ مجمّعاً لا يُطرح: «728 مستهدفاً · 17 مصقولاً ·
            # 606 بلا مرساة» هو ما كشف أن الصقل لا يعمل على ورش أصلاً (‏7e).
            # فيُعدّ كل `refineSrc` لا المصقول وحده، ويصير مجموع القيم =
            # `medTargeted` و`token-snap` = `refinedCount` — تحقّقٌ ذاتيّ.
            if src:
                refine_stats[src] = refine_stats.get(src, 0) + 1
            if e.get("refined"):
                row["refined"] = True
                refined_count += 1
            nxt = e["ayahIdx"] + 1
            if nxt < n and nxt not in shipped:
                nxt_e = next((x for x in surah_entries if x["ayahIdx"] == nxt), None)
                if nxt_e is None or nxt_e["startMs"] is None:
                    row["endApprox"] = True
                elif e["endMs"] == nxt_e["startMs"]:
                    row["endApprox"] = True
            entries.append(row)
            present.add((sn, e["ayahIdx"] + 1))
    # ⛔ **حارس الاكتمال: لكل آية مدخلٌ أو وسمُ غيابٍ بسببه** (أمر المشرف
    # github-f4، 2026-09-02 — بعد أن وجد github-8e في `m_sayed_warsh` المنشور
    # 79 مدخلاً حيث تُعيد الوصفةُ 83: آياتٌ بلا توقيت أصلاً يعبرها حارس الرفع).
    #
    # والغياب **يُصنَّف لا يُعدّ فقط**، لأنّ رقمين متقاربين قد يخفيان علّتين
    # مختلفتين (قياس github-7d: `dokali` 380 و`tareq` 576، ونصيب «الذيل
    # المبتور» في الثاني خمسة أضعاف). والأصناف هنا ما تعرفه هذه الدالّة يقيناً:
    #   • `surah-absent`  السورة لم تُعالَج أصلاً — **فشل جلبٍ لا فشل محاذاة**،
    #     تُعالَج بإعادة الجلب فتُفرز وحدها (تنبيه 7d: صنفٌ مختلف نوعاً لا درجة).
    #   • `no-align`      مدخلٌ بلا `startMs` (محاذاةٌ لم تُنتج حدّاً).
    #   • `invalid`       مدخلٌ نهايتُه ≤ بدايته — عطبُ تشغيلٍ لا ثقةٌ منخفضة.
    #   • `swallowed`     السورة عولجت ولا أثر للآية إطلاقاً — بصمة الابتلاع.
    # وتشخيصُ السبب الأدقّ (فجوة داخلية · بسملة مبتلعة · ذيل مبتور) عند 7d،
    # ولا يُعاد بناؤه هنا: `tools/qa_coverage/diag.py` هو مكانه.
    missing, by_reason = [], {}
    if counting == "KUFI":
        for sn, total in enumerate(SURAH_AYAHS, start=1):
            d = per_surah.get(sn)
            for ayah in range(1, total + 1):
                if (sn, ayah) in present:
                    continue
                if d is None:
                    reason = "surah-absent"
                else:
                    e = next((x for x in d["entries"]
                              if x.get("ayahIdx") == ayah - 1), None)
                    if e is None:
                        reason = "swallowed"
                    elif e.get("startMs") is None:
                        reason = "no-align"
                    else:
                        reason = "invalid"
                missing.append(f"{sn}:{ayah}")
                by_reason[reason] = by_reason.get(reason, 0) + 1
        # عقدٌ ذاتيّ التحقّق: المشحون + المفقود = عدد آي المصحف بالضبط.
        assert len(entries) + len(missing) == AYAH_COUNTS["KUFI"], (
            f"اختلال الحارس: {len(entries)} مدخلاً + {len(missing)} مفقودة "
            f"≠ {AYAH_COUNTS['KUFI']}")

    # عدّ المداخل منخفضة الثقة — **حقلٌ مستقلّ لا يُخلط بالغياب**: هذه آياتٌ
    # لها حدودٌ مقيسة وثقتُها دون العتبة، وتلك آياتٌ بلا حدٍّ أصلاً.
    low_count = sum(1 for row in entries if row["confBand"] == "LOW")

    # **وسمُ ندرة السكتات `sparsePauses` — من الترويسة نفسها بلا صوتٍ ولا
    # خادم** (مواصفة github-7d، `docs/qa/ACCEPTANCE_GATE.md`): حين يعجز الصقل
    # عن إيجاد **سكتة** حول الحدّ مرّةً بعد مرّة، فالتلاوة موصولةٌ قليلةُ
    # الوقفات في مواضع القطع. المقيس: `a_majed` حصّةُ «لا صمت» من إخفاقه
    # **46.1%** وMED ‏89.1%؛ والحصري **22.2%** وMED ‏6.5%.
    #
    # 🐞 **وكان اسمه `noisyRecording` فسقط الاسم بالقياس ولم يسقط الحساب:**
    # سُحب قياسُ «أرضية الضجيج» الذي سُمّي به — فـ`a_majed` **ليس ضاجّاً**
    # (أهدأ نافذة فيه 0.001 من مستوى الكلام)، وإنما أقلّ من 5% من إطاراته
    # هادئة فوقع المئينُ الخامس على **كلامٍ لا على صمت**؛ والشاهد القاطع أن
    # الرقم على **القارئ نفسه** يتغيّر ×34 بتغيّر السورة (يس 0.204 · الإخلاص
    # 0.006). فالاسم كان **يدّعي علّةً مكذَّبة**، ويوجّه العلاج إلى تنقية الصوت
    # وعلّتُه في مواضع القطع. ⇒ **لا تسمِّ ما لم تقس**، والوصف يُقدَّم على
    # الادّعاء. والحساب نفسه لم يتغيّر حرفاً — بل صار أقوى، لأنه يقيس **عجز
    # الأداة عن إيجاد الصمت حيث وقع فعلاً** ولا يمرّ بمقدِّرٍ إحصائي يخدعه
    # توزيع الطاقة.
    #
    # ⛔ **والمقام من جنس البسط:** النسبة تُحسب على **مجموع أسباب الإخفاق** لا
    # على `medTargeted` — فالأسباب عدُّ **محاولات** (الحدّ يُجرَّب بانزلاقات
    # فيُعدّ سببه مرّةً لكل محاولة) و`medTargeted` عدُّ **حدود**، وقسمة أحدهما
    # على الآخر قسمةُ شيءٍ على غير جنسه (تصحيح github-8e).
    #
    # ⛔ **والمقام قبل النسبة:** دون 200 محاولة يبقى الوسم **`null` لا
    # `false`** — «لا نعلم» غير «ليس ضاجّاً»، وهي العلّة التي كادت ترفض أنظف
    # فهارسنا (‏`husary_warsh` مقامه 54).
    #
    # ⚠️ ومُعايَرٌ على حالاتٍ معدودة: يُكتب ويُوسَّع قياسه، ولا يُبنى عليه
    # حجبٌ نهائي وحده. وهو **لا يُرخي عتبةً ولا يُسقط شرطاً** — الموسوم
    # يُؤجَّل حتى العتبة المتكيّفة، وفائدته توفيرُ تدقيقٍ صوتيّ على ما سيُعاد.
    # ويُجاوره حقلٌ من مصدرٍ آخر يقيس السبب في التسجيل (كثافة السكتات في
    # الدقيقة عند github-8e: ‏0.3 مقابل 9.3) — فلا يكون أحدهما حَكَماً وحده.
    # وشاهدٌ على أنه يمسك ما لا يمسكه عدّاد التغطية: `deban_qalun` تغطيته
    # 98.8% ونسبة `no-silence:no-anchor` عنده 1.17 وHIGH ‏9.2% فقط.
    # **نسخة كاشف الصمت: تُسرد ولا تُختار** (طلب github-b9 ‏2026-09-02). نُشرت
    # `adaptive-2` أثناء بناء فهارس جارية، فبُنيت سورُها الأولى بـ`adaptive-1`
    # وما بعدها بالثانية — والفهرس **مختلطٌ بالضرورة**. فقيمةٌ واحدة في
    # الترويسة **تكذب على ثماني سور منه**، وهي عين العلّة التي تجنّبناها في
    # `refineVersion`. ولذلك تُعدّ السور بكل نسخة.
    #
    # وكذلك العتبة: تُحسب **لكل سورة** والمقياس يتغيّر ×34 بين سور القارئ
    # الواحد، فيُكتب **مداها** لا رقمٌ واحد. وإن لم يمرّر المسار إلا وسيطاً
    # واحداً كُتب وسيطاً وحده، وبقي الطرفان `null` — «لا نعلم» لا صفر.
    vad_versions, vad_rels = {}, []
    for _sn, d in per_surah.items():
        version = d.get("vadVersion")
        if version:
            vad_versions[version] = vad_versions.get(version, 0) + 1
        rel = d.get("vadRel")
        if isinstance(rel, (int, float)):
            vad_rels.append(float(rel))
    vad_rels.sort()
    if vad_rels:
        rel_block = {"min": vad_rels[0], "median": vad_rels[len(vad_rels) // 2],
                     "max": vad_rels[-1], "surahs": len(vad_rels)}
    elif vad_rel is not None:
        rel_block = {"min": None, "median": vad_rel, "max": None, "surahs": None}
    else:
        rel_block = None

    skips = sum(v for k, v in refine_stats.items() if k.startswith("skip:"))
    no_silence = refine_stats.get("skip:no-silence", 0)
    no_anchor = refine_stats.get("skip:no-anchor", 0)

    cover = {}
    if counting == "KUFI":
        # ⚠️ **الحارس الذي يسقط لا يمرّر:** إن تعذّر قياس التغطية فالفهرس لا
        # يُبنى — فهرسٌ بلا قياسِ اكتمالٍ هو بالضبط ما مرّ علينا الليلة.
        import os as _os
        import sys as _sys
        _sys.path.insert(0, _os.path.join(
            _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "cloud"))
        from coverage_guard import assess as _assess       # noqa: PLC0415
        cover = _assess({"riwaya": riwaya, "entries": entries})
        assert cover["count"] == len(missing), (
            f"اختلاف عدّ الغياب: الحارس {cover['count']} والتصنيف {len(missing)}")

    return {
        "schema": 1, "riwaya": riwaya, "reciterId": reciter_id,
        "sourceKind": source_kind, "ayahCounting": counting,
        "ayahCount": AYAH_COUNTS[counting],
        "method": "ASR_ALIGN", "engineVersion": engine_version,
        # **فرزُ الجيلين آلياً — وبقيمة صريحة لا بعدم:** كانت `null` عند غياب
        # الصقل، و`null` والحقلُ الغائب يُقرآن سواءً في أكثر المستهلكات، فيختلط
        # **«قيس فلم يُصقل»** بـ**«لا نعلم»**. والقيمة الصريحة تُعلن جهلها.
        # (اتفاق github-b9 وgithub-7e وrafiq-mushaf، 2026-09-02.)
        "refineVersion": (REFINE_VERSION if refined_count else "none"),
        # ⚠️ **`refinedCount/medTargeted` معدّل نجاح المحاولة لا صحّة النتيجة**
        # (تحفّظ github-7e، 2026-09-02): قد يُصقل حدٌّ فيبقى خاطئاً، وقد يُترك
        # حدٌّ سليمٌ بلا صقل. والصحّة لا يقولها إلا القياس الصوتي — وقد قيس
        # فهرسٌ تغطيته 94.7% فكان أسوأ ما قيس. فالنسبة **تشخيصٌ للمحرك لا
        # معيار قبولٍ للفهرس**، ولا تُبنى عليها ترقية.
        "refinedCount": refined_count,
        "medTargeted": med_targeted,
        "refineStats": refine_stats,
        "lowCount": low_count,
        # نسخة كاشف الصمت وقيمتُه المحسوبة لهذا القارئ — والقيمة تُمرَّر من
        # المسار (‏`vad_rel`)؛ فإن لم تُمرَّر كُتبت `null`: «لا نعلم» لا صفر.
        # ⛔ لا `vadVersion` مفردة: `versions` عدُّ السور بكل نسخة، فإن غابت
        # بيانات السور كُتب `null` — ولا يُفترض أن الفهرس كلّه بنسخة الجهاز.
        "vad": {"versions": vad_versions or None, "rel": rel_block,
                "writerVersion": VAD_VERSION},
        "noSilenceShare": (round(no_silence / skips, 3) if skips >= 200 else None),
        "noSilenceToAnchor": (round(no_silence / no_anchor, 2)
                              if no_anchor >= 100 else None),
        "sparsePauses": (skips >= 200 and no_silence / skips >= 0.40
                           if skips >= 200 else None),
        # **وسمُ الغياب صريحٌ دائماً** ولو كان صفراً: الحقل الغائب يُقرأ «لا
        # نعلم»، والحقل الذي يقول صفراً يقول «قيس فلم يغب شيء».
        #
        # و`medianLen`/`biasedShort` **من دالّة الحارس نفسها**
        # (`tools/cloud/coverage_guard.assess`) لا من حسابٍ ثانٍ هنا — فالمنطق
        # واحدٌ في موضعين لا نسختان تتباعدان، والترويسة تحمل **الأرقام التي
        # يحكم بها الحارس** لا أرقاماً تشبهها. ومعناها (قياس github-8e):
        # الغياب المنحاز إلى القصر بصمةُ **ابتلاعٍ في المحاذاة** لا صمتٍ عارض
        # (‏`m_sayed_warsh` وسيط الغائب 4 كلمات مقابل 10 للمصحف)، وغيابٌ غير
        # منحاز علّتُه أخرى (‏`basit_warsh` وسيط 10 مقابل 10).
        "missing": {"count": len(missing), "byReason": by_reason,
                    "medianLen": cover.get("medianLen"),
                    "medianLenAll": cover.get("medianLenAll"),
                    "biasedShort": cover.get("biasedShort"),
                    "ids": missing},
        "exactEnds": True,
        "generatedAt": int(time.time() * 1000),
        "audioSha256": shas, "notes": "",
        "entries": entries,
    }


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
