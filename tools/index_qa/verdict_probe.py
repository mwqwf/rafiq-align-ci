#!/usr/bin/env python3
"""أين ذهب الحكمُ الصوتيّ؟ — مسبارٌ يقابل بصمةَ المنشور بأحكام `state/`.

⛔⛔ **سببُه مقيسٌ 2026-09-20:** `asim` و`a_binaoun` لهما تغطيةٌ كاملةٌ وليسا
مصدَّقَين. أطلقتُ لكلٍّ منهما **أربعةَ ملوحٍ**، ونجحت التشغيلاتُ الثماني
(`conclusion=success`)، **وبقي التصديقُ 225/227 كما كان**.
⭐ **ونجاحُ التشغيلة ليس وصولَ الحكم** — تماماً كما أنّ «أُطلق» ليست «تمّ».
فبين الاثنين خطوةٌ لم أَقِسها: أكُتب الحكمُ أصلاً؟ وتحت أيّ بصمة؟

و`certify()` يشترط ثلاثةً مجتمعة، وأيُّها انخرم منع الشهادة:
  ① كائنُ حكمٍ في `state/` اسمُه يحمل **أوّلَ ثمانيةٍ** من بصمة المنشور،
  ② وداخلَه `sha256` **يطابق البصمةَ كاملةً** (فالثمانيةُ دالٌّ لا برهان)،
  ③ وليس فيه فاتلٌ غيرُ معلَن.
⇒ فهذا المسبارُ يطبع الثلاثةَ صراحةً بدل الظنّ: بصمةُ المنشور، وكلُّ كائنِ
حكمٍ يحملها، وما في جوفه. ⚖️ وهو **قارئٌ محض** لا يكتب بايتاً.

الاستعمال:  verdict_probe.py <riwaya>/<id> [...]
"""
import gzip
import hashlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run import s3  # noqa: E402


def main():
    if len(sys.argv) < 2:
        raise SystemExit("الاستعمال: verdict_probe.py <riwaya>/<id> [...]")
    cl, bucket = s3()

    # جردُ أحكامِ `state/` مرّةً واحدةً — فالمقابلةُ بالاسم لا بالتخمين.
    state = []
    tok = None
    while True:
        kw = {"Bucket": bucket, "Prefix": "state/"}
        if tok:
            kw["ContinuationToken"] = tok
        r = cl.list_objects_v2(**kw)
        state += [o["Key"] for o in (r.get("Contents") or [])]
        tok = r.get("NextContinuationToken")
        if not tok:
            break
    audio = [k for k in state if ".audio-" in k and k.endswith(".json")]
    print(f"أحكامٌ صوتيّةٌ في الدلو: {len(audio)} من {len(state)} كائناً\n")

    bad = 0
    for spec in sys.argv[1:]:
        key = f"timings/{spec}.jz"
        # ⛔⛔ **قِسْ بالمقياس الذي يحكم به الحارسُ لا بأيّ مقياس** (وقعت
        #    2026-09-20): قِستُ أوّلاً بـ`etag`، فقال المسبارُ «الحكمُ لم يصل»
        #    وهو لم يبحث عن البصمة أصلاً. و`certify()` يأخذ البصمةَ
        #    **sha256 لجسم الكائن الخام كما هو**، لا من ترويسةٍ ولا من etag.
        #    ⭐ ومسبارٌ يقيس غيرَ ما يقيسه الحارسُ يُنتج تشخيصاً كاذباً واثقاً.
        try:
            raw = cl.get_object(Bucket=bucket, Key=key)["Body"].read()
        except Exception as e:                            # noqa: BLE001
            print(f"⛔ {spec}: لا كائنَ منشورٌ بهذا المفتاح — {e}")
            bad += 1
            continue
        sha = hashlib.sha256(raw).hexdigest()
        print(f"■ {spec}\n   المفتاح {key} · {len(raw):,} بايتاً"
              f"\n   البصمةُ المحكومُ بها {sha}")
        # ⛔⛔ **الشهادةُ تُمنع بأربعةِ شروطٍ لا بواحد** — و`certify()` يقرأ
        #    ثلاثةً منها من **جوف الفهرس نفسِه** لا من الأحكام:
        #    التغطية · و`qa.fatal` · و`transform.op` (‏الذي يميّز الإسقاطَ
        #    المعلَنَ عن العطب). ⭐ فمن نظر إلى الأحكام وحدَها ظنّ المانعَ
        #    فيها وهو في الفهرس، **فعالج غيرَ المريض**.
        try:
            d = json.load(gzip.open(io.BytesIO(raw), "rt", encoding="utf-8"))
            qa = d.get("qa") or {}
            n, tot = len(d.get("entries") or []), d.get("ayahCount") or 6236
            print(f"   تغطية {n}/{tot} = {n / max(1, tot):.4f}"
                  f" · qa.fatal={qa.get('fatal')!r}"
                  f" · transform.op={(d.get('transform') or {}).get('op')!r}")
            if qa.get("fatal"):
                print("   ⛔ **المانعُ هنا**: `qa.fatal` في الفهرس نفسِه "
                      "⇒ لا شهادةَ مهما بلغت الأحكامُ الصوتيّة.")
        except Exception as e:                            # noqa: BLE001
            print(f"   ⚠️ تعذّرت قراءةُ جوف الفهرس: {e}")
        probe = sha[:8]
        hits = [k for k in audio if probe and probe in k]
        if not hits:
            # ⛔ لا حكمَ بهذه البصمة: فإمّا أنّ الملحَ كُتب لبصمةٍ أخرى (فهرسٌ
            #   رُقّي بعد الحكم) أو أنّ التشغيلةَ لم تكتب شيئاً رغم نجاحها.
            print(f"   ⛔ لا كائنَ حكمٍ يحمل {probe} — **الحكمُ لم يصل**")
            near = [k for k in audio if spec.split("/")[-1] in k]
            for k in near[:6]:
                print(f"      · حكمٌ باسمه ببصمةٍ أخرى: {k}")
            bad += 1
            continue
        for k in hits:
            d = json.loads(cl.get_object(Bucket=bucket, Key=k)["Body"]
                           .read().decode("utf-8"))
            full = str(d.get("sha256") or "")
            ok = "✅ يطابق" if full == sha else f"⛔ يصف {full[:12]}… لا هذا"
            fats = d.get("fatal") or []
            print(f"      {k}\n         {ok} · حكم={d.get('verdict')} "
                  f"· فواتل={len(fats)}")
            # ⛔ **نصُّ الفاتل هو الحكم، لا عدده**: `undeclared_fatal()` يقارن
            #    بدايةَ النصّ بقائمة آثار الإسقاط المعلَن. فعددٌ بلا نصٍّ لا
            #    يقول أمعذورٌ هو أم عطبٌ حقيقيّ.
            for f in fats[:3]:
                print(f"            ⛔ {str(f)[:120]}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
