# -*- coding: utf-8 -*-
"""فحص المطالع (‏kind=openers) على فهرسٍ في `timings-staging/` — كشفٌ بشاهد.

**ما يفعله:** لكل سورةٍ غير الفاتحة والتوبة، يفرّغ من `startMs` بسُلَّمٍ من ست
درجات (‏1000…6000م.ث) ويحكم على المطلع بأحد ثلاثة:

| الحكم | معناه |
|---|---|
| `clean` | المسموع يبدأ بأول كلمةٍ من الآية ⇒ الحدّ في موضعه |
| `swallowed` | بسملةٌ تامّة قبل الآية ⇒ الحدّ **أبكر مما يجب** |
| `tail` | يبدأ بذيل بسملة ⇒ الحدّ **داخل** البسملة (أسوأ حالةٍ للمستخدم) |

⛔ **ولا حكمَ ترقيةٍ في هذا الملف**: يكتب شاهداً في `state/` ويحكم غيرُه.

⛔ **ولا يُعتدّ بكشفٍ بلا تحقّق**: قِيس (‏deban_qalun س37، 2026-09-02) أن
النموذج **يهلوس بسملةً** في نافذةٍ ضيّقة على ملفٍ أوّله «والصافات صفا» بلا
بسملةٍ أصلاً — والبسملة أكثر عبارةٍ في بيانات تدريبه فهي هلوسته المفضّلة. فكل
`swallowed` هنا يحمل حقل `verified`: تفريغُ ما بعد نهاية البسملة المقدَّرة
يبدأ بأول كلمةٍ من الآية. **وما لم يتحقّق يُبلَّغ `suspect` لا `swallowed`.**

⛔ **والخيوط جزءٌ من النتيجة لا من الإعداد**: قِيس أن س86 وس105 عند `hawashi`
تُكشفان بأربعة خيوطٍ وتفوتان باثنين — **في الاتجاهين**. فتُكتب في الشاهد،
وتشغيلةٌ بخيوطٍ أخرى ليست إعادةً لهذه.

    python tools/tasmi_bench/openers_scan.py --key timings-staging/hafs/alijon.27638af1.jz
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))
sys.path.insert(0, HERE)
from basmala_local import (BAS, _edit, _eq, _eq_first, basmala_tail, cut,  # noqa: E402
                           fuzzy_seq, text_of)
from common import load_index, load_text, norm, read_jz  # noqa: E402

# ⛔ إيداعُ `QuranRafiq` الذي نُسخ منه هذا الملف — يُحدَّث مع كل مزامنة.
SOURCE_COMMIT = "df25676"

SKIP = {1, 9}
LADDER = (1000, 1500, 2000, 3000, 4000, 6000)
VERIFY_MS = 4000
WORK = os.path.join(HERE, "work", "openers")
STATE = os.path.join(ROOT, "tools", "index_qa", "state")
RECITERS = os.path.join(ROOT, "tools", "cloud", "reciters.tsv")


def url_template(rid):
    for line in open(RECITERS, encoding="utf-8"):
        if line.startswith("#"):
            continue
        p = line.rstrip("\n").split("\t")
        if len(p) > 2 and p[0] == rid:
            return p[2]
    return None


def s3():
    import boto3
    c = json.load(open(os.path.join(ROOT, "secure", "r2_credentials.json")))
    return boto3.client("s3", endpoint_url=c["endpoint"],
                        aws_access_key_id=c["accessKeyId"],
                        aws_secret_access_key=c["secretAccessKey"],
                        region_name="auto"), c["bucket"]


def fetch_head(url, dst, need_ms=6000, nbytes=None):
    """⛔ الحمولة تُقاس بحاجة النافذة لا برقمٍ ثابت: ‏256ك.ب تكفي ~16ث، وكثيرٌ
    من الفهارس يبدأ فيها مطلع السورة بعد الاستعاذة (‏alijon س2 عند 8.5ث) فيقع
    آخر النافذة خارج المُنزَّل ⇒ **wav فارغ وتفريغٌ فارغ يبدو حكماً `unknown`**.
    (وقع فعلاً: ست سور كلّها `unknown` في 15 ثانية — والسرعة نفسها كانت
    الدليل.) فتُطلب البايتات على قدر (البدء + النافذة) بهامشٍ للترويسة.

    وثلاث محاولات لأن قطعَ الخادم يتنكّر في زيّ نتيجة."""
    if nbytes is None:
        nbytes = 131072 + int((need_ms / 1000.0) * 20000)
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"Range": f"bytes=0-{nbytes-1}"})
            with urllib.request.urlopen(req, timeout=90) as r, open(dst, "wb") as f:
                f.write(r.read())
            if os.path.getsize(dst) > 32768:
                return dst
            last = "حمولة أقصر من 32ك.ب"
        except Exception as ex:
            last = ex
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"تعذّر التنزيل: {last}")


def self_test():
    """⛔ **حارسٌ بلا اختبارٍ ليس حارساً** — والحالةُ الأولى مقيسةٌ من الدلو
    لا مفترَضة: صفُّ 28 في `hawashi.96b65571` كان
    `{"verdict": "clean", "heard": "بسم الله"}` **والصوتُ أكّد الابتلاع فيه**."""
    def ok(x, y):
        if min(len(x), len(y)) <= 3:
            return x == y
        return _eq(x, y) or _edit(x, y) <= 1

    def starts_ayah(w, ref):
        if not w:
            return False
        if _eq_first(w[0]) and w[0] != ref[0]:
            return False
        return ok(w[0], ref[0]) or (len(w) > 1 and ok(w[0] + w[1], ref[0]))

    cases = [
        ("28 الحالةُ المقيسة", ["بسم", "الله"], ["طسم"], False),
        ("26 نظيرتُها", ["بسم", "الله"], ["طسم"], False),
        ("28 سليمةٌ حقاً", ["طسم"], ["طسم"], True),
        ("27 طس", ["طس"], ["طس"], True),
        ("2 الم", ["الم"], ["الم"], True),
        ("36 يس", ["يس"], ["يس"], True),
        ("خطأُ تعرّفٍ في كلمةٍ طويلة", ["الحمدو", "لله"], ["الحمد", "لله"], True),
        ("بسملةٌ قبل آيةٍ طويلة", ["بسم", "الله"], ["الحمد", "لله"], False),
    ]
    bad = 0
    for name, w, ref, want in cases:
        got = starts_ayah(w, ref)
        bad += got != want
        print(f"  {'✅' if got == want else '❌'} {name}: {got} (المتوقَّع {want})")
    print(f"— فُحصت **{len(cases)}** حالة" + (" ⛔ فيها خلل" if bad else " · كلُّها كما يجب"))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", help="مفتاح تحت timings-staging/")
    ap.add_argument("--self-test", action="store_true",
                    help="اختبارُ مقارن المطالع بحالاتٍ مقيسة — بلا صوتٍ ولا شبكة")
    ap.add_argument("--model", default=os.path.join(HERE, "work", "ggml-q8.bin"))
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(self_test())
    if not a.key:
        ap.error("--key مطلوب (أو --self-test)")
    if not a.key.startswith("timings-staging/"):
        sys.exit("⛔ هذا الفحص لمفاتيح `timings-staging/` وحدها")
    os.makedirs(WORK, exist_ok=True)
    os.makedirs(STATE, exist_ok=True)
    out_path = os.path.join(STATE, a.key.replace("/", "_") + ".openers.json")

    cli, bucket = s3()
    jz = os.path.join(WORK, os.path.basename(a.key))
    if not os.path.exists(jz):
        cli.download_file(bucket, a.key, jz)
    sha = hashlib.sha256(open(jz, "rb").read()).hexdigest()
    ti = read_jz(jz)
    rid = ti.get("reciterId") or a.key.split("/")[-1].split(".")[0]
    riwaya = ti.get("riwaya") or a.key.split("/")[1]
    tmpl = url_template(rid)
    if not tmpl:
        sys.exit(f"⛔ لا قالب صوتٍ لـ{rid} في reciters.tsv — لا فحص بلا مصدر")

    text = load_text(riwaya)
    start_of = {s["n"]: s["start"] for s in load_index()["surahs"]}
    first = {int(e["ayahId"].split(":")[0]): e for e in ti["entries"]
             if e["ayahId"].endswith(":1")}

    from pywhispercpp.model import Model
    model = Model(a.model, n_threads=a.threads, language="ar",
                  print_progress=False, print_realtime=False)

    def ok(x, y):
        # ⛔ **الكلمةُ القصيرةُ تُطابَق حرفاً** (‏عطبٌ مقيسٌ لا متوقَّع،
        #    2026-09-03): «بسم» و«طسم» يفترقان بحرفٍ واحد، فسماحةُ الحرف
        #    تبتلع الفرق ⇒ مطلعُ السورة 28 سُمع فيه «بسم الله» **فحُكم
        #    `clean`** لأنّ «بسم» طابقت «طسم» مرجعَ الآية. والشاهدُ محفوظ:
        #    ‏`hawashi.96b65571` صفُّ 28 = `{"verdict":"clean","heard":"بسم الله"}`
        #    والصوتُ أكّد ابتلاعَ البسملة فيه. ⇒ **دون أربعةِ أحرفٍ لا سماحة**،
        #    فالسماحةُ إنما وُضعت لخطأ تعرّفٍ في كلمةٍ طويلةٍ لا لتمحوَ فرقاً
        #    دلالياً في كلمةٍ من ثلاثة.
        if min(len(x), len(y)) <= 3:
            return x == y
        return _eq(x, y) or _edit(x, y) <= 1

    def starts_ayah(w, ref):
        if not w:
            return False
        # ⛔ **وما بدا أوّلَ بسملةٍ لا يُقرأ أوّلَ آيةٍ إلا بمطابقةٍ حرفية**:
        #    `_eq_first` نفسُها تقبل «طسم» (‏تنتهي بـ«سم» وطولها ثلاثة)، فلا
        #    تُميّز البسملةَ من فواتح السور المقطّعة. **والحكمُ للمطابقة لا
        #    للشبه.**
        if _eq_first(w[0]) and w[0] != ref[0]:
            return False
        return ok(w[0], ref[0]) or (len(w) > 1 and ok(w[0] + w[1], ref[0]))

    rows, t0 = [], time.time()
    todo = [(s, e) for s, e in sorted(first.items())
            if s not in SKIP and e.get("startMs") is not None]
    if a.limit:
        todo = todo[:a.limit]
    for s, e in todo:
        ref = norm(text[start_of[s]]).split()
        mp3 = os.path.join(WORK, f"o_{rid}_{s:03d}.mp3")
        clip = os.path.join(WORK, f"o_{rid}.wav")
        row = {"surah": s, "startMs": e["startMs"]}
        w = []
        try:
            fetch_head(tmpl.format(surah=s), mp3,
                       need_ms=e["startMs"] + LADDER[-1] + VERIFY_MS)
            end = None
            for d in LADDER:
                w = text_of(model, cut(mp3, e["startMs"], d, clip)).split()
                if not w:
                    continue
                j = fuzzy_seq(w)
                if j is not None and len(w) >= j + len(BAS):
                    end, row["rung"], row["heard"] = d, d, " ".join(w[:8])
                    break
                # الأغلب سليم: مطلعٌ يبدأ بأول كلمةٍ من الآية يُحسم من أول
                # درجة، فلا تُدفع كلفةُ ستّ درجاتٍ على السليم.
                if starts_ayah(w, ref):
                    row.update(verdict="clean", heard=" ".join(w[:6]), rung=d)
                    break
                if d == LADDER[0]:
                    t = basmala_tail(w)
                    if t:
                        row.update(verdict="tail", heard=" ".join(w[:6]),
                                   tailWords=t[1])
                        break
            if "verdict" not in row:
                if end is None:
                    row.update(verdict="unknown", heard=" ".join(w[:6]))
                else:
                    after = text_of(model, cut(mp3, e["startMs"] + end,
                                               VERIFY_MS, clip)).split()
                    good = starts_ayah(after, ref)
                    row.update(verdict="swallowed" if good else "suspect",
                               verified=good, afterHeard=" ".join(after[:6]),
                               basmalaEndMs=e["startMs"] + end)
        except Exception as ex:
            row.update(verdict="error", error=str(ex)[:100])
        finally:
            if os.path.exists(mp3):
                os.remove(mp3)
        rows.append(row)
        print(f"  س{s:3d}: {row['verdict']} · {row.get('heard','')[:36]}", flush=True)

    by = {}
    for r in rows:
        by[r["verdict"]] = by.get(r["verdict"], 0) + 1
    doc = {"kind": "openers", "key": a.key, "sha256": sha, "reciterId": rid,
           "riwaya": riwaya, "scope": "partial" if a.limit else "full",
           "checked": len(rows), "counts": by,
           "swallowed": sorted(r["surah"] for r in rows if r["verdict"] == "swallowed"),
           "tail": sorted(r["surah"] for r in rows if r["verdict"] == "tail"),
           "suspect": sorted(r["surah"] for r in rows if r["verdict"] == "suspect"),
           "errors": sorted(r["surah"] for r in rows if r["verdict"] == "error"),
           # ⛔ «العطب» يُعرَّف هنا صراحةً كي لا يُعرِّفه القارئ: `unknown` ليس
           # عطباً في المطلع بل **تعذّر حكم** — أكثره فواتح مقطّعة يخطئ فيها
           # التعرّف («المص» تُسمع «الر») والحدُّ سليم. وعدّه عطباً يردّ فهارس
           # صحيحة بجملتها. و`suspect` عطبٌ مشكوك: كشفٌ بلا تحقّق.
           "defects": sum(1 for r in rows if r["verdict"] in ("swallowed", "tail", "suspect")),
           "unknown": sorted(r["surah"] for r in rows if r["verdict"] == "unknown"),
           "tool": "openers_scan.py",
           # ⛔ **البصمةُ تشهد بمصدرِ المنطق لا بمكان التشغيل** (‏D-175/D-177):
           #    هذا الملفُّ **منسوخٌ** من `QuranRafiq` وهناك تُودع إصلاحاتُه،
           #    وبوابةُ الترقية تقرأ `commit` وتسأل شجرةَ `QuranRafiq` عنه.
           #    فختمُ بصمةِ هذا المستودع كان يجعل كلَّ مسحٍ **مجهولَ الأداة**
           #    فيُردّ حكمُه ولو كان بأحدث منطق — **جمودٌ تامّ وقع فعلاً**.
           #    ⇒ `commit` = إيداعُ المصدر المنسوخ منه · و`ciCommit` = هذا
           #    المستودع، فلا يضيع أيُّ نسبٍ ولا يكذب أيُّ حقل.
           "commit": SOURCE_COMMIT,
           "ciCommit": subprocess.check_output(["git", "-C", ROOT, "rev-parse",
                                                "--short", "HEAD"]).decode().strip(),
           "threads": a.threads, "model": os.path.basename(a.model),
           "elapsedSec": round(time.time() - t0), "at": int(time.time()),
           "note": ("‏`swallowed` متحقَّقٌ صوتياً بعد الحدّ المقدَّر؛ و`suspect` "
                    "كشفٌ بلا تحقّق ⇒ يُحتمل أن يكون هلوسة نموذج، فلا يُبنى "
                    "عليه حكم. ولا حكم ترقيةٍ في هذا الملف."),
           "rows": rows}
    # ⛔ حكمٌ على **المطالع** لا على الترقية (طلب bd، وحدُّ f4 محفوظ): الملفّ
    # يقول ما رآه صريحاً بدل أن يستنتجه قارئُه من خلوّ حقل — والاستنتاج الصحيح
    # اليوم يصير خاطئاً حين تتغيّر الصيغة. ⛔ ولا يقول «يُرقّى»: الترقية حكمُ
    # البوابة، وهذا شاهدُها لا قرارُها.
    if doc["scope"] != "full":
        doc["openersVerdict"] = "inconclusive"
        doc["verdictText"] = (f"فحصٌ جزئي (فُحص {len(rows)}) — لا يشهد بسلامة "
                              "المطالع ولا بعطبها")
    elif doc["counts"].get("swallowed"):
        doc["openersVerdict"] = "defective"
        doc["verdictText"] = ("بسملةٌ مبتلعة **متحقَّقةٌ صوتياً** في "
                              f"{doc['counts']['swallowed']} سورة: {doc['swallowed']}")
    else:
        doc["openersVerdict"] = "clean"
        doc["verdictText"] = (
            "لا بسملة مبتلعة متحقَّقة في أي مطلع"
            + (f" · مشكوكٌ بلا تحقّق: {doc['suspect']}" if doc["suspect"] else "")
            + (f" · ذيول: {doc['tail']}" if doc["tail"] else "")
            + (f" · تعذّر الحكم (أكثره فواتح مقطّعة): {len(doc['unknown'])}"
               if doc["unknown"] else ""))
    doc["verdictScope"] = "openers-only — ليس حكم ترقية"
    json.dump(doc, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n{rid}: {by} · {round(time.time()-t0)}ث → {out_path}")


if __name__ == "__main__":
    main()
