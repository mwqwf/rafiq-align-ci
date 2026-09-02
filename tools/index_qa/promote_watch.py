#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""راصدُ الترقية — يشغّل `promote.py` كل عشر دقائق على أحكام `state/` الجديدة.

    python tools/index_qa/promote_watch.py                # يرصد وينفّذ
    python tools/index_qa/promote_watch.py --once --dry   # دورةٌ واحدة عرضاً

**ما يفعله:** يقرأ الأحكام المكتوبة، فيمرّ منها ما استوفى بوابة `promote.py`
كاملةً (حكمٌ «مقبول» ببصمةٍ تطابق الكائن الحيّ وعيّنةٍ صوتية وبلا نطاقٍ مفرد،
والفهرس نفسه بأثر صقلٍ ووسمِ اكتمالٍ دون العتبة وبلا انحياز إلى القصر، والهدف
غير مجمَّد) — فيُرقّى ويُجمَّد ويُسجَّل في `PROMOTIONS.md`.

⛔ **لا يخترع حكماً ولا يخفّف شرطاً:** كل البوابة في `promote.py` وحدها،
والراصد **لا يملك عتبةً خاصة به** — فما يمرّ منه هو ما يمرّ من التشغيل اليدوي
حرفاً بحرف. وهذا مقصود: راصدٌ بعتباتٍ خاصة يصير باباً ثانياً للإنتاج.

**الحالة في `work/state.json`** — المفاتيح المرقّاة ببصماتها. فإعادة تشغيل
الراصد لا تعيد ترقيةً وقعت (درس راصد ab)، ولا يُعاد رفعُ ما هو مرفوع. والحالة
**تُكتب بعد الترقية لا قبلها**، فانقطاعُ الكهرباء لا يترك ترقيةً «مسجَّلة ولم
تقع»؛ وإن وقعت ولم تُسجَّل ردّها التجميد في الدورة التالية بلا ضرر.

⚠️ **البلاغات:** لا يستطيع سكربتٌ إرسال رسائل الجلسات، فيكتب الراصد كل ترقية
سطراً في `work/notify.jsonl` **ويتركها للجلسة** لتنقلها إلى 7e و7d و82. فلا
يُظنّ أنها أُرسلت لمجرّد وقوع الترقية — الملفّ هو البريد، والنقل فعلٌ بشريّ.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import sys
import time
import traceback
from contextlib import redirect_stdout
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                 # noqa: BLE001
        pass

NL = chr(10)
HERE = Path(__file__).resolve().parent
WORK = HERE / "work"
STATE = WORK / "state.json"
NOTIFY = WORK / "notify.jsonl"
sys.path.insert(0, str(HERE))
import promote                                                       # noqa: E402


def load_state():
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:                             # noqa: BLE001
            pass
    return {"promoted": {}, "cycles": 0, "startedAt": None}


def save_state(state):
    WORK.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(STATE)


def candidates(cl, bucket, frozen, state):
    """المرشّحون الذين لم يُرقَّوا بهذه البصمة من قبل — والبوابة بوابةُ promote."""
    out = []
    holds = promote.held()
    everywhere = list(promote.reports()) + promote.bucket_reports(cl, bucket)
    ci_reports = promote.ci_map(everywhere)
    for _name, rep in promote.latest_sampled(everywhere):
        target, why = promote.gate(rep, frozen, "", holds, None, ci_reports)
        if why:
            continue
        seen = state["promoted"].get(target)
        if seen == rep.get("sha256"):
            continue                                   # رُقّي بهذه البصمة سلفاً
        out.append((rep, target))
    return out


def cycle(state, dry):
    """دورةٌ واحدة — تُرجع (عدد المرشّحين، عدد ما رُقّي، النصّ المطبوع).

    وقائمة التجميد تُقرأ **من الدلو** لا من المرآة المحلية (D-075): المرآة
    تتقادم، والراصد يعمل بلا عينٍ عليها.
    """
    cl, bucket = promote.s3()
    frozen, _text, _etag = promote.load_frozen(cl, bucket)
    picks = candidates(cl, bucket, frozen, state)
    if not picks:
        return 0, 0, ""
    argv = sys.argv
    done = 0
    buf = io.StringIO()
    for rep, target in picks:
        sys.argv = ["promote.py", "--only", rep["key"]] + ([] if dry else ["--yes"])
        try:
            with redirect_stdout(buf):
                promote.main()
        except SystemExit as ex:                       # الأداة تقف وتُبلّغ
            buf.write(f"\n⛔ توقّفت الأداة: {ex}\n")
        except Exception:                              # noqa: BLE001
            buf.write("\n⛔ خطأ غير متوقّع:\n" + traceback.format_exc())
        finally:
            sys.argv = argv
        text = buf.getvalue()
        if not dry and f"🧊 جُمّد: {target}" in text:
            state["promoted"][target] = rep["sha256"]
            done += 1
            with NOTIFY.open("a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "target": target, "src": rep["key"], "sha256": rep["sha256"],
                    "severeRate": rep.get("severeRate"),
                    "for": ["github-7e", "github-7d", "github-82"],
                }, ensure_ascii=False) + "\n")
    return len(picks), done, buf.getvalue()


STAGING_PREFIX = os.environ.get("R2_STAGING_PREFIX", "timings-staging/")
# **اللقطات الجزئية ليست مرشّحات:** `partial_snapshot.py` يكتب لقطةً كل عشرين
# سورة للاستئناف والمعاينة، فمفتاحُها `<id>.partial<N>.<sha8>.jz`. وردُّها
# «بنقص التغطية» رفضٌ صحيحُ الحساب **خاطئُ المعنى** — يملأ اللوحة بإنذارٍ
# متوقَّع، والإنذار المتوقَّع يدرّب قارئه على تجاهل الصادق.
PARTIAL = re.compile(r"\.partial\d+\.[0-9a-f]{6,}\.jz$")
# ⛔ ولا يُبنى نسبٌ على ميتاداتا الكائن: حقل `source` يقول «github-actions»
# حتى لما أنتجه Cloud Run (تنبيه المشرف) — فالمصدر يُعرف من المفتاح والترويسة.
# بادئةُ أحكام الصوت على الدلو — يكتبها `tools/index_qa/ci_run.py` عند
# github-7e باسم `qa-state/<المفتاح وقد استُبدل «/» بـ«_»>.json` وببنية الحالة
# المحلية نفسها. ⛔ ولا تُفترض بادئة: الخطأ فيها **صمتٌ لا خطأ** — يقرأ
# الراصد لا شيء ويظنّ أن لا حكم.
# ⚠️ **بادئتان تُقرآن معاً لا واحدة**: قال github-7e إنّ وظيفته تكتب في
# `qa-state/`، وقال المشرف إنّ وظائف 3a/7e تكتب في `state/`. والخطأ في
# البادئة **صمتٌ لا خطأ** — يقرأ الراصد لا شيء فيظنّ أن لا حكم — فقراءةُ
# الاثنتين تُلغي السؤال وتكلّف نداءً واحداً زائداً في الدورة.
STATE_PREFIXES = tuple(
    x for x in os.environ.get("R2_STATE_PREFIXES", "qa-state/,state/").split(",") if x)
FLOOD = HERE.parents[1] / "docs" / "qa" / "FLOOD_STATUS.md"


def gate_version():
    """بصمةُ منطق البوابة — كي لا يبقى في الطابور حكمٌ أصدره حارسٌ تغيّر.

    ⛔ الطابور يخزّن الحكم بالبصمة، فلو تغيّرت **البوابة** بقي الحكم القديم
    معروضاً في اللوحة وهو باطل. وقع فعلاً: بعد إخراج الغياب المعلَّل من عتبة
    الفقد بقي `akri_qalun.afaacc25` معروضاً «مرفوضاً» والبوابة تقبله. فالحكم
    المخزَّن يُنسب إلى **نسختين**: نسخة الملفّ ونسخة الحاكم.
    """
    # **البصمة تشمل الراصد نفسه لا البوابة وحدها:** الفرزُ والتصنيف هنا، فلو
    # تغيّر الراصد وحده بقي الطابور على تصنيفٍ قديم (وقع: صنف «لقطة جزئية»
    # أُضيف فبقيت اللقطات معروضةً مرفوضةً بحكمٍ سابق).
    return hashlib.sha256(
        Path(promote.__file__).read_bytes()
        + Path(__file__).read_bytes()).hexdigest()[:12]


def prescreen(cl, bucket, state):
    """حكمٌ **بنيويّ** آليّ لكل مفتاحٍ جديد في الاختبار — قبل أن يصل الصوت.

    **لماذا الآن لا عند الترقية؟** لأنّ مئةً وسبعة فهارس ستصل في ساعات، وأنبوب
    التدقيق الصوتي أغلى من أن يُنفق على فهرسٍ يردّه البنيويّ في ثانية. فما سقط
    بنيوياً **لا يحجز مكاناً في الطابور** (درس github-7e: قيمة الحارس البنيوي
    أن يرفض مبكراً فيُفرغ الأنبوب لما يستحقّه).

    ⛔ **ولا يخترع الراصد فحصاً:** يستدعي `promote.index_gate` وفحصَ البتر
    نفسيهما — فما يمرّ هنا هو ما يمرّ هناك حرفاً. والحالة بالبصمة لا بالاسم:
    نسخةٌ جديدة على المفتاح نفسه **حكمٌ جديد** لا تُقرأ بحكم سالفتها.
    """
    queue = state.setdefault("queue", {})
    frozen, _ftext, _fetag = promote.load_frozen(cl, bucket)
    version = gate_version()
    if state.get("gateVersion") != version:
        if state.get("gateVersion"):
            print("  ↻ تغيّرت البوابة — يُعاد الفحص البنيويّ لكل الطابور",
                  flush=True)
        queue.clear()
        state["gateVersion"] = version
    fresh = 0
    for page in cl.get_paginator("list_objects_v2").paginate(
            Bucket=bucket, Prefix=STAGING_PREFIX):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if not key.endswith(".jz"):
                continue
            # **منطقةُ التجربة ليست أسطولاً:** `--self-test` يرفع كائناً وهمياً
            # تحت `tmp/`، فظهر في اللوحة «مرفوضاً بنيوياً» بين فهارس القرّاء.
            # ولوحةٌ فيها صفٌّ لا يعني أحداً تُقرأ بعينٍ أكسل.
            if key.startswith(STAGING_PREFIX + "tmp/"):
                continue
            etag = (obj.get("ETag") or "").strip(chr(34))
            row = queue.get(key)
            if row and row.get("etag") == etag:
                continue
            fresh += 1
            got = cl.get_object(Bucket=bucket, Key=key)
            body = got["Body"].read()
            # **المنتِج يُقرأ ولا يُصدَّق على علّاته.** ميتاداتا الكائن تقول
            # `source`، وقد نبّه المشرف أنها تقول «github-actions» أحياناً لما
            # أنتجه Cloud Run — فتُعرض **كما قالها الرافع** ومعها `job` حين
            # يوجد (‏وهو أثرٌ لا يُكتب بالخطأ)، ولا يُبنى عليها قبولٌ ولا ردّ.
            meta = got.get("Metadata") or {}
            if PARTIAL.search(key):
                idx0 = json.loads(gzip.decompress(body).decode("utf-8"))
                surahs = {e["ayahId"].split(":")[0]
                          for e in idx0.get("entries", [])}
                queue[key] = {"etag": etag, "state": "لقطة جزئية",
                              "entries": len(idx0.get("entries", [])),
                              "surahs": len(surahs), "why": None,
                              "gateVersion": version,
                              "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
                continue
            idx = json.loads(gzip.decompress(body).decode("utf-8"))
            riwaya = idx.get("riwaya") or key.split("/")[1]
            reciter = idx.get("reciterId") or key.split("/")[-1].split(".")[0]
            why = (promote.index_gate(idx)
                   or promote.catalog_gate(idx, promote.catalog(cl, bucket)))
            cut, diag = promote.truncation(cl, bucket, riwaya, reciter,
                                           obj.get("ETag"))
            if cut and not why:
                why = ("سورٌ مبتورةٌ في المصدر: "
                       + "، ".join(str(r.get("surah")) for r in cut[:5]))
            sha = hashlib.sha256(body).hexdigest()
            # **هدفٌ مجمَّدٌ ببصمةٍ أخرى: رفضٌ مبكّر لا انتظارُ عيّنة.** كان
            # `husary_qalun.3e52af3d` معروضاً «ينتظر حكم الصوت» وهدفُه مجمَّدٌ
            # على `8680ed1f` (مرساةُ `wordtimings` بـ39,863 كلمة) — فالعيّنة
            # الصوتية عليه إنفاقٌ على ما لا يُرقّى إلا بقرار إنسان.
            if not why:
                tgt = f"timings/{riwaya}/{reciter}.jz"
                if tgt in frozen and frozen[tgt] != sha:
                    why = (f"الهدف مجمَّد ببصمةٍ أخرى ({frozen[tgt][:8]}) — "
                           "لا ترقية ولا تُنفَق عليه عيّنة حتى يُرفع التجميد "
                           "بقرارٍ صريح")
            publish_verdict(cl, bucket, key, sha, version, riwaya, reciter, why,
                            idx)
            queue[key] = {
                "etag": etag, "sha256": sha,
                "riwaya": riwaya, "reciter": reciter,
                "entries": len(idx.get("entries", [])),
                "refineVersion": idx.get("refineVersion"),
                "missing": (idx.get("missing") or {}).get("count"),
                "lowCount": idx.get("lowCount"), "diagnosis": diag,
                "why": why,
                # **المشتقّ يُعلن نسبَه في اللوحة**: نسخةٌ مصحّحة
                # (‏`basmala_fix` أو `drop_surah`) تحمل بصمةً جديدة، فحكمُ
                # أبيها لا يشهد لها — والبوابة تردّها بمطابقة البصمة على كل
                # حال، لكنّ الصفّ الصامت يوقع القارئ في ظنّ أنها هي هي.
                "source": meta.get("source"), "job": meta.get("job"),
                "transform": (idx.get("transform") or {}).get("op"),
                "parent": ((idx.get("transform") or {}).get("fromSha256")
                           or (idx.get("transform") or {}).get("parent")
                           or idx.get("parent")),
                "state": "مرفوض بنيوياً" if why else "ينتظر حكم الصوت",
                "gateVersion": version,
                "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
    return fresh


def publish_verdict(cl, bucket, key, sha, version, riwaya, reciter, why, idx):
    """يرفع الحكم **البنيويّ** إلى `state/` ببصمتين: بصمة الملفّ وبصمة البوابة.

    ⛔ ويُوسم `kind: structural` صراحةً كي لا يُقرأ حكماً صوتياً: هو لا يحمل
    عيّنة، و**البنية لا تشهد للمحتوى**. والبصمتان معاً لأن الحكم يُنسب إلى
    ما حُكم عليه وإلى ما حَكَم به.
    """
    doc = {
        "key": key, "riwaya": riwaya, "reciterId": reciter, "sha256": sha,
        "kind": "structural", "gateVersion": version, "band": None,
        "sample": None, "fatal": ([why] if why else []),
        "verdict": ("مرفوض (خلل بنيوي)" if why else
                    "بنيوياً سليم — بلا عيّنة صوتية"),
        "info": {"entries": len(idx.get("entries", [])),
                 "missing": (idx.get("missing") or {}).get("count"),
                 "lowCount": idx.get("lowCount"),
                 "refineVersion": idx.get("refineVersion")},
        "ts": time.time(), "by": "rafiq-mushaf/promote_watch",
    }
    name = "state/" + key.replace("/", "_") + ".json"
    try:
        cl.put_object(Bucket=bucket, Key=name,
                      Body=json.dumps(doc, ensure_ascii=False).encode("utf-8"),
                      ContentType="application/json")
    except Exception as ex:                           # noqa: BLE001
        print("  تعذّر رفع الحكم البنيوي: " + str(ex), flush=True)


bucket_reports = promote.bucket_reports   # المنطق في البوابة وحدها


def flood_status(state, promoted):
    """لوحةُ حالٍ نصّية تُكتب كل دورة — وتقول ما لا نعرفه كما تقول ما نعرف."""
    queue = state.get("queue", {})
    waiting = [r for r in queue.values() if r["state"] == "ينتظر حكم الصوت"]
    refused = [r for r in queue.values() if r["state"] == "مرفوض بنيوياً"]
    partial = [r for r in queue.values() if r["state"] == "لقطة جزئية"]
    L = ["# لوحة الفيض — " + time.strftime("%Y-%m-%d %H:%M"), "",
         "> تُكتب من راصد الترقية كل دورة من **الدلو** لا من ذاكرة.",
         "> و«ينتظر حكم الصوت» تعني: اجتاز البنيويّ ولم يصل حكمُه الصوتي —",
         "> **لا** «مقبول»، ولا يُرقّى بلا حكمٍ صوتي مهما طال انتظاره.", "",
         "| وصل الاختبار | ينتظر الصوت | مرفوض بنيوياً | لقطات جزئية | مُرقّى |",
         "|---|---|---|---|---|",
         "| %d | %d | %d | %d | %d |" % (len(queue), len(waiting), len(refused),
                                         len(partial), len(promoted)), "",
         "## ينتظر حكم الصوت", "",
         "| المفتاح | بصمة | مداخل | غياب | LOW | الجيل | التشخيص | المنتِج |",
         "|---|---|---|---|---|---|---|---|"]
    for key, r in sorted(queue.items()):
        if r["state"] == "ينتظر حكم الصوت":
            L.append("| `%s` | `%s` | %s | %s | %s | %s | %s | %s |" % (
                key, r["sha256"][:8], r["entries"], r["missing"],
                r["lowCount"], r["refineVersion"], r["diagnosis"],
                (r.get("job") or r.get("source") or "—")))
    srcs = {}
    for r in waiting:
        srcs[r.get("source") or "—"] = srcs.get(r.get("source") or "—", 0) + 1
    if srcs:
        L += ["", "> **منتِجو المنتظِرين** (‏من ميتاداتا الكائن، وهي قولُ الرافع "
              "لا قياسُنا): " + " · ".join(f"{k} {v}" for k, v in sorted(srcs.items()))]
    snaps = [(k, r) for k, r in sorted(queue.items())
             if r["state"] == "لقطة جزئية"]
    if snaps:
        L += ["", "## لقطات جزئية (استئنافٌ ومعاينة — ليست مرشّحات)", "",
              "| المفتاح | سور | مداخل |", "|---|---|---|"]
        for key, r in snaps:
            L.append("| `%s` | %s | %s |" % (key, r.get("surahs"), r["entries"]))
    der = [(k, r) for k, r in sorted(queue.items()) if r.get("transform")]
    if der:
        L += ["", "## نسخٌ مشتقّة (‏لكلٍّ بصمتُها، فلا يشهد لها حكمُ أصلها)", "",
              "| المفتاح | التحويل | الأصل | الحال |", "|---|---|---|---|"]
        for key, r in der:
            L.append("| `%s` | %s | `%s` | %s |" % (
                key, r["transform"], str(r.get("parent") or "?")[:8], r["state"]))
    L += ["", "## مرفوضٌ بنيوياً (لا يُنفَق عليه تدقيقٌ صوتي)", "",
          "| المفتاح | السبب |", "|---|---|"]
    for key, r in sorted(queue.items()):
        if r["state"] == "مرفوض بنيوياً":
            L.append("| `%s` | %s |" % (key, r["why"]))
    holds = promote.held()
    if holds:
        L += ["", "## محجوزون (‏عطبٌ مقيس — لا يُرقَّون ولا يُجمَّدون)", "",
              "> الحجز **ليس رفضاً للحكم الصوتي**: قد يكون الفهرس نظيف الحدود",
              "> وصوتُه معيباً، فالترقية تختم العيب والمجمَّد لا يستقبل تصحيحاً.",
              "> ⚠️ وهؤلاء **أحياءٌ في `timings/manifest.json`** — الحجز يمنع",
              "> ترقيةً قادمة ولا يسحب ما هو مشحون؛ سحبُه قرارُ إنسان.",
              "", "| المفتاح | سبب الحجز |", "|---|---|"]
        for key, why in sorted(holds.items()):
            L.append("| `%s` | %s |" % (key, why))
    wd = promote.withdrawn()
    if wd:
        L += ["", "## شهاداتٌ مسحوبة (لا ترقية حتى يصل بديلُ الحكم)", "",
              "> السحبُ **زمنيّ**: أيّ حكمٍ بعد لحظته يُقرأ شاهداً ويزول الحاجز",
              "> بلا تدخّل. والقائمة في `tools/index_qa/evidence_withdrawn.txt`.",
              "", "| القارئ | لحظة السحب | السبب |", "|---|---|---|"]
        for rid, (ts, why) in sorted(wd.items()):
            L.append("| `%s` | %s | %s |" % (
                rid, time.strftime("%Y-%m-%d %H:%MZ", time.gmtime(ts)), why))
    L += ["", "## المُرقّى", "", "| المفتاح | بصمة |", "|---|---|"]
    for key, sha in sorted(promoted.items()):
        L.append("| `%s` | `%s` |" % (key, sha[:8]))
    FLOOD.parent.mkdir(parents=True, exist_ok=True)
    FLOOD.write_text(NL.join(L) + NL, encoding="utf-8")


def beat(state, note):
    """نبضةٌ على القرص كل دورة — **موتُ الراصد يجب أن يُرى**.

    مات مرّةً برمز 1 بلا أثرٍ في سجلّه (قُتل ولم ينهَر)، فبقي عشر دقائق لا
    يُدرى أحيٌّ هو أم لا. والنبضة تجعل ذلك مقروءاً بملفٍّ واحد: زمنُها ورقمُ
    العملية ورقمُ الدورة — فمن وجد نبضةً أقدم من دورتين فالراصد ميت.
    """
    (WORK / "heartbeat.json").write_text(json.dumps({
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"), "pid": os.getpid(),
        "cycle": state["cycles"], "note": note,
        "promoted": len(state["promoted"]),
    }, ensure_ascii=False), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--every", type=int, default=600, help="ثوانٍ بين الدورات")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry", action="store_true", help="عرضٌ بلا ترقية")
    a = ap.parse_args()

    WORK.mkdir(parents=True, exist_ok=True)
    state = load_state()
    state["startedAt"] = state.get("startedAt") or time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"راصد الترقية — كل {a.every}ث · pid {os.getpid()} · "
          f"مرقّى سلفاً {len(state['promoted'])}" + (" · عرضٌ فقط" if a.dry else ""),
          flush=True)
    while True:
        state["cycles"] += 1
        stamp = time.strftime("%H:%M:%S")
        try:
            cl0, bucket0 = promote.s3()
            fresh = prescreen(cl0, bucket0, state)
            if fresh:
                print("[%s] فحصٌ بنيويّ لـ%d مفتاحاً جديداً" % (stamp, fresh),
                      flush=True)
            seen, done, text = cycle(state, a.dry)
            flood_status(state, state["promoted"])
            if seen:
                print(f"[{stamp}] دورة {state['cycles']}: مرشّحون {seen} · "
                      f"رُقّي {done}", flush=True)
                print(text, flush=True)
            else:
                print(f"[{stamp}] دورة {state['cycles']}: لا مرشّح", flush=True)
        except SystemExit as ex:
            # **وقفةُ الأداة ليست موتَ الراصد.** يقف `promote` بـ`SystemExit`
            # حين تتعذّر قراءة قائمة التجميد — وهو الصواب: لا ترقية على قراءة
            # ناقصة. لكنّ `except Exception` لا يمسك `SystemExit`، فكان انقطاعُ
            # شبكةٍ عابر (‏قطع R2 الاتصال 17:11) **يقتل الراصد** حتى يوقظه
            # إنسان. فالوقفة تُسجَّل وتُتخطّى الدورة، والحياةُ تستمرّ.
            print(f"[{stamp}] دورة {state['cycles']}: وقفت الأداة — "
                  f"{ex} · لا ترقية في هذه الدورة", flush=True)
        except Exception:                              # noqa: BLE001
            print(f"[{stamp}] دورة {state['cycles']}: خطأ\n"
                  + traceback.format_exc(), flush=True)
        save_state(state)
        beat(state, note="دورة تمّت")
        if a.once:
            return
        time.sleep(a.every)


if __name__ == "__main__":
    main()
