#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ناقلُ أوامرِ الوكيل السحابيّ — يُنفَّذ داخل العدّاء بصلاحيّاته لا بصلاحيّات الوكيل.

**المشكلةُ التي يحلّها (مقيسةٌ لا مظنونة):** جلسةُ كلود السحابيّة تقرأ جيت هَب
ولا تملك `workflow_dispatch` (‏`403`)، ولا تملك اعتمادَ الدلو. فكانت عاجزةً عن
ثلاثةِ أشياءَ هي صُلبُ العمل: **إطلاقُ محاذاة · القياسُ من الدلو · الترقية**.

**الحلّ:** الوكيلُ يكتب أمراً في `ops/commands/<اسم>.json` ويدفعه، فيستيقظ
`agent_cmd.yml` وينفّذه **بصلاحيّاته هو** ثمّ يُعيد الجواب إلى `ops/out/`.
⭐ **فالصلاحيةُ تبقى حيث هي، والأمرُ يُنقل إليها** — ولا يُسلَّم الوكيلُ سرّاً.

## صيغةُ الأمر
```json
{"action": "dispatch", "workflow": "realign_surah.yml",
 "inputs": {"parent": "timings/hafs/x.jz", "surahs": "6", "skip_ms": "7840",
            "url_template": "https://…/{s:03d}.mp3", "reciter_id": "x",
            "riwaya": "hafs", "reason": "…"}}

{"action": "tool", "tool": "index_qa/run.py", "args": ["--struct-only", "timings-staging/…jz"]}
{"action": "tool", "tool": "ci_fleet/restore_loop.py", "args": ["scan", "--limit", "3"]}
{"action": "state"}                      ← جردٌ كاملٌ من الدلو إلى ops/out/state.json
```

⛔ **وقائمةُ المسموح مغلقة** (‏`ALLOWED_*`): أمرٌ خارجَها يُردّ ويُكتب سببُ ردّه.
⛔ **ولا شيءَ هنا يمسّ العتبات ولا الحُرّاس** — `promote.py` يحكم بحُرّاسه كما هو.
⛔ **والأمرُ المنفَّذُ يُنقل إلى `ops/commands/done/`** فلا يُعاد تنفيذُه عند كلّ دفعة.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import traceback
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
CMD_DIR = ROOT / "ops" / "commands"
OUT_DIR = ROOT / "ops" / "out"
DONE_DIR = CMD_DIR / "done"

# ⛔ سيرُ العملِ المسموحُ إطلاقُه — والثقيلُ كلُّه هنا فلا حاجةَ إلى غيره.
ALLOWED_WF = {"align.yml", "realign_surah.yml", "openers.yml", "audio_qa.yml",
              "basmala.yml", "restore.yml", "keepalive.yml", "mirror_reciter.yml",
              "reciter_probe.yml", "free_candidate_probe.yml", "probe_ayah.yml", "diagnosis.yml", "timing_ingest.yml",
              # ⛔ **أُضيف 2026-09-14 (‏D-442 · مناوبةُ المحرك):** `bench-selftest.yml` يشغّل
              #    اختباراتِ عدّة القياس وحُرّاسَها (‏دقيقةٌ واحدة · بايثون وحدَه · لا محاكيَ ولا
              #    شبكةَ ثقيلة). وأُضيف لأنّ زنادَه بالدفع **توقّف عن الاشتعال** على دفعاتٍ
              #    تمسّ مساراتِه وهو `active` (‏أربعُ محاولاتٍ بأدلّتها في `ops/out/BLOCKED.md`)،
              #    و`workflow_dispatch` المباشر يردّ **403** على بيانة الوكيل ⇒ فالبابُ المفتوح
              #    هو هذا الأمرُ نفسُه. ⚖️ وهو **مسارُ قراءةٍ وفحصٍ لا يكتب شيئاً** (‏`permissions:
              #    contents: read`) فإدخالُه لا يُضعف حارساً ولا يفتح باباً للكتابة.
              "bench-selftest.yml", "package-catalog-cloud.yml",
              # ⛔ **أُضيف 2026-09-14 (مناوبةُ الفهرسة):** `align_split.yml` يقسم القارئَ
              #    الواحدَ على عدّة عدّائين ثمّ يجمع. أُدخل لأنّ العلّةَ التي يعالجها مقيسةٌ
              #    (الموجة 34813198468: أربعُ شرائحَ انتهت في ثانيتين واثنتان تجاوزتا
              #    ساعتين وأربعين) ⇒ زمنُ الموجة أطولُ شريحةٍ لا مجموعُ العمل.
              # ⚖️ **ولا يُضعف حارساً**: شوطُ الجزء لا يستدعي `stage_upload.py` بحال،
              #    والرفعُ كلُّه في العدّاء الخاتم على مسار «المصحف الكامل 1-114»
              #    بحرّاسه كاملةً (114/114 · refine_probe · حارسُ الرفع · PARTIAL_MIN).
              "align_split.yml",
              # ⛔⛔ **أُضيف 2026-09-20 بقياسٍ من سجلّ التشغيلة 35514028223**
              #    (‏`yahya` س102، والخمسُ الأخرياتُ مثلُها حرفاً):
              #      «VAD: 1 فترة صمت · مقطع 1/2 [0.0-28.0ث]: ذهاكم التكاثر …
              #       تفريغ: 2 مقطعاً، 14 كلمة · آيات بلا حدود: [3, 6, 8]»
              #    ⇒ القارئُ يقرأ التكاثرَ **في نفَسٍ واحدٍ بلا سكتات**، فلا
              #    يجد محرّكُ VAD حدوداً يقسم عليها. **وليست علّةَ تخطٍّ**:
              #    التخطّي عمل، والبسملةُ أُزيحت، والصوتُ نُزّل سليماً.
              # ⛔ وقد أُعيدت هذه السورُ الخمسُ في **ثلاث دوراتٍ متتالية**
              #    بالمُدخَل نفسِه ⇒ ثمانيَ عشرةَ تشغيلةً ضاعت. والقاعدةُ نصّاً:
              #    **لا تكرارَ اختبارٍ سقط بلا مُدخَلٍ مختلفٍ بسببٍ مقيسٍ مكتوب.**
              # ⭐ و`ctc_align` هو المُدخَلُ المختلف: محاذاةٌ قسريّةٌ لا تحتاج
              #    سكتةً لتجد حدَّ الآية، وقد كسرت من قبلُ قرّاءً ردَّهم المحرّكُ
              #    القديم. وله `probe_surahs` = **سبرٌ بلا رفع** ⇒ يُقاس أوّلاً
              #    بلا أن يمسَّ المسرحَ ولا الدلوَ ولا حارساً.
              # ⚖️ مجّانيّ: مستودعٌ عامّ وعدّاءُ `ubuntu-latest` القياسيّ.
              "ctc_align.yml"}
# ⛔ والأدواتُ المسموحةُ كلُّها **قارئةٌ أو محكومةٌ بحُرّاسها** — لا صدفةَ فيها.
# ⛔ و`certify_catalog.py` منها (‏أُضيف 2026-09-13 ‏19:0xZ بقياس): الكتالوجُ
#    `catalog/reciters.json` هو ما **يقرؤه التطبيق**، وحقلاه `ayahCoverage`
#    و`ayahCertified` لا يتحرّكان إلا به. وقِيس أنّ بصمتَه بقيت
#    `a6b98a08a789` (‏77,432 بايتاً) **خمساً وعشرين ساعة** — أي أنّ ليلةَ
#    استرجاع الـ310 آية لم تصل إلى المستخدم أصلاً، **لأنّ لا بابَ سحابيّاً
#    كان يفتحه**. وهو محكومٌ بحُرّاسه (يُسقط التوليد كلَّه إن شُهد لمن لا حكمَ
#    لبصمته، ولا يمسّ غير الحقلين)، فإدخالُه لا يُضعف حارساً.
ALLOWED_TOOLS = {"index_qa/run.py", "index_qa/triage.py", "index_qa/promote.py",
                 "index_qa/certify_catalog.py",
                 "index_qa/bucket_watch.py", "index_qa/drop_surah.py",
                 "index_qa/low_coverage_scan.py", "index_qa/dup_sha_sweep.py",
                 "index_qa/duration_profile.py", "index_qa/reciter_evidence.py",
                 "index_qa/dump_state.py", "index_qa/material_probe.py",
                 "index_qa/_debug_state_for.py", "index_qa/_debug_openers_for.py",
                 "ci_fleet/restore_loop.py", "ci_fleet/status_page.py",
                 # ⛔ **أُضيف 2026-09-19:** اختبارُ حارسِ «بصمات الصوت n/114».
                 #    وأُدخل لأنّ قاعدةَ `CLAUDE.md` (بند 2) توجب اختبارَ أيّ
                 #    تعديلٍ على حارسٍ **نصّاً قبل استعماله** — والحارسُ يعمل على
                 #    العدّاء لا هنا، فاختبارُه حيث يعمل شرطُ صحّةٍ لا زينة.
                 # ⚖️ وهو **قارئٌ محض**: يبني فهارسَ وهميّةً في الذاكرة ويقارن
                 #    مخرَجَ `structural`، لا يمسّ الدلوَ ولا يكتب بايتاً واحداً.
                 "index_qa/test_sha_count_declared_drop.py",
                 # ⛔ **أُضيف 2026-09-19:** قياسُ البسملة من فهرس القارئ نفسِه.
                 #    والقاعدةُ في `CLAUDE.md` تأمر به منذ مدّة لكنّها كانت
                 #    **وصيّةً بلا أداة**، والسُّلَّمُ البديل (`basmala.yml`) سقفُه
                 #    3000م.ث فيكذب على مَن بسملتُه أطول (husary_douri 10160م.ث).
                 # ⚖️ وهو **قارئٌ محض**: يقرأ الفهرسَ ويطبع وسيطاً، لا يكتب شيئاً.
                 "index_qa/basmala_from_index.py",
                 # ⛔ **أُضيف 2026-09-20 (شكوى المالك):** تدقيقُ الكتالوج بعينِ
                 #    المستخدم — أسماءٌ لاتينيّةٌ تُعرض للقارئ العربيّ، وقرّاءٌ
                 #    لا يُشغَّل عندهم شيء. وحُرّاسُنا كلُّها تسأل «أصحيحٌ
                 #    التوقيت؟» ولا تسأل «أيصلح هذا للعرض والتشغيل؟».
                 # ⚖️ قارئٌ محض: يقرأ catalog/reciters.json ويعدّ العطب، لا يكتب.
                 "index_qa/catalog_audit.py",
                 # ⛔ **أُضيف 2026-09-20:** كاشفُ **المرشَّح اليتيم** — ناجٍ
                 #    بنيويّاً بلا بوّابةٍ صوتيّة. ووُلد من عطبٍ مقيس: فهرسُ
                 #    `a_binaoun.3987d0e4` نجا 09-15 وبقي خمسةَ أيّامٍ منسيّاً
                 #    بينما المنشورُ عند المستخدم 2246/6236 مدخلاً ⇒ 3924 آيةً
                 #    جاهزةً محجوبة. ولا حلقةَ كانت تسأل «أيُّ ناجٍ بلا بوّابة؟».
                 # ⚖️ قارئٌ محض: يسرد `timings-staging/` و`state/` ويطبع قائمةَ
                 #    عملٍ، لا يكتب بايتاً ولا يُطلق تشغيلةً ولا يُجيز ترقية.
                 "index_qa/orphan_candidates.py",
                 "index_qa/verdict_probe.py",
                 "index_qa/test_declared_sha_fatal.py",
                 "ci_fleet/repo_parity.py"}
MAX_OUT = 200_000            # حرفاً — جوابٌ أطولُ يُقصّ ويُعلَن قصُّه


def run(cmd, **kw):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=str(ROOT), **kw)
    return p.returncode, (p.stdout or "") + (("\n[stderr]\n" + p.stderr) if p.stderr else "")


def do_dispatch(c):
    wf = c.get("workflow", "")
    if wf not in ALLOWED_WF:
        return 2, f"⛔ سيرُ عملٍ غيرُ مسموح: {wf!r}\nوالمسموح: {sorted(ALLOWED_WF)}"
    # ⛔⛔ **يُرشَّح المُدخَلُ بجواب GitHub نفسِه لا بتحليلِ ملفّ** (‏2026-09-14):
    #    العلّةُ أنّ `CLAUDE.md` يأمر بتمرير `reason` مع كلّ إطلاق و**بعضُ** سيور العمل
    #    تُعلنه وبعضُها لا ⇒ `HTTP 422: Unexpected inputs provided: ["reason"]` (وقع مرّتين).
    # ⛔ **وعلاجي الأوّلُ كان أسوأَ من العطب**: حلّلتُ الملفَّ بـPyYAML، **وهي غيرُ مثبَّتةٍ
    #    في بيئة العدّاء** ⇒ `No module named 'yaml'` فسقط كلُّ إطلاقٍ فاشلاً **مغلقاً**.
    #    ⭐ والدرس: *حارسٌ يعتمد على ما لا يضمن وجودَه يصير هو العطب* — ومَن أضاف اعتماداً
    #    جديداً في مسارٍ حرجٍ فليسأل أوّلاً: **أهو موجودٌ حيث يعمل؟**
    # ⇒ **فلا تحليلَ ولا اعتماد**: يُجرَّب الإطلاقُ، فإن ردّ 422 مسمّياً المُدخَلاتِ غيرَ
    #    المُعلَنة أُسقطت **بأسمائها من الرسالة نفسِها** وأُعيد **مرّةً واحدة**. والمصدرُ
    #    هو GitHub لا ظنُّنا، ولا يحتاج شيئاً مثبَّتاً.
    given = dict(c.get("inputs") or {})

    def _fire(inp):
        a = ["gh", "workflow", "run", wf]
        for k, v in inp.items():
            a += ["-f", f"{k}={v}"]
        return run(a)

    rc, out = _fire(given)
    if rc != 0 and "Unexpected inputs provided" in out:
        bad = re.findall(r'"([^"]+)"', out[out.index("Unexpected inputs provided"):])
        dropped = {k: given.pop(k) for k in bad if k in given}
        if dropped:
            rc, out2 = _fire(given)
            out = ("ℹ️ مُدخَلاتٌ لا يُعلنها " + wf + " فأُسقطت وأُعيد الإطلاق:\n"
                   + "".join(f"   · {k} = {v}\n" for k, v in dropped.items()) + out2)
    return rc, out


def do_tool(c):
    tool = c.get("tool", "")
    if tool not in ALLOWED_TOOLS:
        return 2, f"⛔ أداةٌ غيرُ مسموحة: {tool!r}\nوالمسموح: {sorted(ALLOWED_TOOLS)}"
    args = [x if isinstance(x, str) else str(x) for x in (c.get("args") or [])]
    return run([sys.executable, str(ROOT / "tools" / tool), *args])


def do_state(c):
    """جردٌ كاملٌ من الدلو — به يرى الوكيلُ ما لا يصله اعتمادُه."""
    sys.path.insert(0, str(ROOT / "tools" / "index_qa"))
    from run import s3, fetch_index                                   # noqa: E402
    cl, b = s3()
    pub, per = {}, {}
    for pg in cl.get_paginator("list_objects_v2").paginate(Bucket=b, Prefix="timings/"):
        for o in pg.get("Contents", []):
            k = o["Key"]
            if k.endswith(".jz") and k.count("/") == 2:
                riw = k.split("/")[1]
                pub[(riw, k.split("/")[2][:-3])] = o["Size"]
                per[riw] = per.get(riw, 0) + 1
    cat = json.loads(cl.get_object(Bucket=b, Key="catalog/reciters.json")["Body"].read())
    # ⭐ الهدفُ يعدّ قرّاءَ الفهرس وحدَهم: قارئُ «الآية» صوتُه ملفٌّ لكلّ آيةٍ فلا فهرسَ له
    #    ولا يدخل في 162/180 — وكان غيابُ هذا التفصيل يُوهم أنّ قرّاءً سقطوا (سؤالُ المالك 05:40Z).
    catalog_total = sum(len(r.get("reciters", [])) for r in cat["riwayat"])
    ayah_mode = [f'{r.get("id") or r.get("riwaya")}/{rc.get("id")}'
                 for r in cat["riwayat"] for rc in r.get("reciters", [])
                 if rc.get("mode") == "ayah"]
    total = catalog_total - len(ayah_mode)
    gaps = {}
    for (riw, rid) in sorted(pub):
        try:
            idx, _ = fetch_index(f"timings/{riw}/{rid}.jz")
        except Exception:                                             # noqa: BLE001
            continue
        srs = {int(e["ayahId"].split(":")[0]) for e in idx["entries"]}
        miss = [s for s in range(1, 115) if s not in srs]
        if miss or len(idx["entries"]) < 6236:
            tr = idx.get("transform") or {}
            gaps[f"{riw}/{rid}"] = {"entries": len(idx["entries"]),
                                    "missingSurahs": miss,
                                    "reasonCode": tr.get("reasonCode")}
    # ⭐⭐ **الباقي يُسمَّى بالاسم لا يُعَدّ فحسب** (‏2026-09-14): «المنشور 162/180» رقمٌ
    #    لا يقول **مَن** الثمانيةَ عشر، فظُنَّ مراراً أنّ موجةَ `reciters_gen1_fix10.tsv`
    #    ترفعه — وهي **استبدالُ جيلٍ لقرّاءَ منشورين سلفاً** (‏`aamer` و`hafz` وغيرُهما في
    #    `timings/` أصلاً) فلا ترفع العدَّ بحقّ. ⇒ فالقائمةُ تُشتقّ **بالطرح من الدلو**
    #    كما يأمر `CLAUDE.md`، وتُكتب هنا حتى لا تُخمَّن مرّةً أخرى.
    missing = sorted(
        f'{r.get("id") or r.get("riwaya")}/{rc.get("id")}'
        for r in cat["riwayat"] for rc in r.get("reciters", [])
        if rc.get("mode") != "ayah"
        and ((r.get("id") or r.get("riwaya")), rc.get("id")) not in pub
    )
    st = {"published": len(pub), "target": total,
          "missingCount": len(missing), "missingIds": missing,
          "catalogTotal": catalog_total,
          "ayahModeExcluded": len(ayah_mode), "ayahModeIds": ayah_mode,
          "byRiwaya": per, "indexesWithGaps": gaps}
    (OUT_DIR / "state.json").write_text(
        json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    _miss = ("\n⛔ **الباقي بالاسم** (" + str(len(missing)) + "): "
             + ("، ".join(missing) if missing else "لا شيء — اكتمل الهدف"))
    return 0, (f"المنشور {len(pub)}/{total}{_miss}\n"
               f"(الكتالوج {catalog_total} قارئاً · "
               f"منهم {len(ayah_mode)} بوضع الآية لا فهرسَ لهم) · {per}\n"
               f"فهارسُ فيها نقص: {len(gaps)} — التفصيلُ في ops/out/state.json")


HANDLERS = {"dispatch": do_dispatch, "tool": do_tool, "state": do_state}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DONE_DIR.mkdir(parents=True, exist_ok=True)
    cmds = sorted(p for p in CMD_DIR.glob("*.json"))
    if not cmds:
        print("لا أمرَ جديد."); return
    for f in cmds:
        name = f.stem
        print(f"\n══ أمر: {name}")
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
            h = HANDLERS.get(c.get("action"))
            if not h:
                rc, out = 2, (f"⛔ فعلٌ غيرُ معروف: {c.get('action')!r} — "
                              f"والمعروف: {sorted(HANDLERS)}")
            else:
                rc, out = h(c)
        except Exception:                                             # noqa: BLE001
            rc, out = 3, "⛔ تعذّر تنفيذُ الأمر:\n" + traceback.format_exc()
        if len(out) > MAX_OUT:
            out = out[:MAX_OUT] + f"\n… [قُصّ الجواب عند {MAX_OUT} حرفاً]"
        print(out[:4000])
        (OUT_DIR / f"{name}.txt").write_text(
            f"# rc={rc}\n{out}", encoding="utf-8")
        # ⛔ يُنقل المنفَّذُ فلا يُعاد تنفيذُه عند كلّ دفعةٍ تالية
        f.replace(DONE_DIR / f.name)
        # ⛔⛔ **ويُدفع الجوابُ الآن لا في آخر الشوط** (عطبٌ مقيسٌ 2026-09-20):
        #    كان الدفعُ خطوةً أخيرةً وحدَها، فإذا بلغ الشوطُ `timeout-minutes`
        #    أُلغي **قبلها** ⇒ **ضاعت أجوبةُ الأوامر كلِّها** ولو كانت قد
        #    نُفّذت فعلاً وكتبت في الدلو. وقع اليومَ على الشوط 35528235170:
        #    ترقيتان نُفّذتا ولا أثرَ لجوابهما، فلا يُعرف أتمّتا أم لا إلا
        #    بجردٍ جديدٍ من الدلو. ⇒ **الجوابُ يُحفظ بعد كلّ أمر**، فالسقفُ
        #    يقطع ما لم يُنفَّذ بعدُ ولا يمحو ما نُفِّذ.
        # ⚖️ وهو آمنٌ: نفسُ الإيداع بمسارٍ صريح، ونفسُ علاج التعارض `-X ours`
        #    الموصوف في `agent_cmd.yml`؛ وفشلُ الدفع **لا يوقف بقيّةَ الأوامر**
        #    لأنّ الخطوةَ الأخيرة تبقى شبكةَ أمانٍ لما لم يُدفع.
        _push_answer(name)
    print("\n⇒ تمّت الأوامر.")


def _push_answer(name: str) -> None:
    """يُودع جوابَ أمرٍ واحدٍ ويدفعه فوراً — بمسارٍ صريحٍ ولا `-A`."""
    import subprocess
    paths = ["ops/out", "ops/commands"]
    try:
        subprocess.run(["git", "config", "user.name", "rafiq-agent-cmd"],
                       cwd=ROOT, check=False)
        subprocess.run(["git", "config", "user.email", "actions@github.com"],
                       cwd=ROOT, check=False)
        # ⛔ **عطبٌ التقطه الاختبار:** `git add a b` يسقط كلُّه إن غاب أحدُ
        #    المسارَين (`pathspec … did not match`) **فلا يُدفع شيء**. والمسارُ
        #    `ops/commands` قد يخلو فعلاً بعد نقل آخر أمرٍ إلى `done/`.
        #    ⇒ كلُّ مسارٍ على حدةٍ، وغيابُ أحدِها لا يُبطل الآخر.
        live = [p for p in paths if (ROOT / p).exists()]
        for p in live:
            subprocess.run(["git", "add", "--", p], cwd=ROOT, check=False)
        if not live or subprocess.run(["git", "diff", "--cached", "--quiet"],
                                      cwd=ROOT).returncode == 0:
            return                                     # لا جديدَ يُدفع
        # ⛔ وبالمسارات **الحاضرةِ** وحدَها هنا أيضاً: `commit -- a b` يسقط
        #    كسقوط `add` سواءً بسواء، وهو موضعُ العطب الذي أخفاه الأوّل.
        subprocess.run(["git", "commit", "-m", f"ops: جوابُ الأمر {name}",
                        "--", *live], cwd=ROOT, check=False)
        if subprocess.run(["git", "push", "origin", "HEAD:main"],
                          cwd=ROOT).returncode != 0:
            subprocess.run(["git", "fetch", "origin", "main", "--quiet"],
                           cwd=ROOT, check=False)
            # ⛔ لا `rebase` على هذه الشجرة المشتركة — `CLAUDE.md` نصّاً.
            subprocess.run(["git", "merge", "-X", "ours", "--no-edit",
                            "origin/main"], cwd=ROOT, check=False)
            subprocess.run(["git", "push", "origin", "HEAD:main"],
                           cwd=ROOT, check=False)
    except Exception as ex:                                       # noqa: BLE001
        # ⛔ لا يُوقف فشلُ الدفع بقيّةَ الأوامر: الخطوةُ الأخيرة شبكةُ أمان.
        print(f"⚠️ تعذّر دفعُ جواب {name} الآن (يبقى للخطوة الأخيرة): {ex}")


if __name__ == "__main__":
    main()
