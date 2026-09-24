#!/usr/bin/env bash
# 📱 جسمُ شوطِ محاكي العدّاء — **ملفٌّ واحدٌ عمداً**.
# ⛔ درسٌ مدفوع (‏2026-09-12): `reactivecircus/android-emulator-runner` ينفّذ **كلَّ سطرٍ في `script:` بصدفةٍ
# منفصلة** (`sh -c` لكلِّ سطر) ⇒ `export` و`cd` لا يعبران السطر، و`"$VAR"` الفارغُ يعطي
# `sh: 1: : Permission denied` وخروجاً 127 **بعد إقلاع المحاكي** فيبدو كأنّ المحاكي هو العطب.
# فالسطرُ في المسار صار واحداً: `bash tools/tasmi_bench/ci_emu_run.sh`، وكلُّ شيءٍ هنا.
#
# البيئة: APK · CAND_TAG (فارغٌ = المشحونُ وحدَه) · SET · LANGS (فارغٌ = افتراضُ التطبيق) · CHUNK
set -euo pipefail
ADB="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-/usr/local/lib/android/sdk}}/platform-tools/adb"
export RAFIQ_ADB="$ADB"
SET="${SET:?يلزم SET}"; CHUNK="${CHUNK:-12}"; CAND_TAG="${CAND_TAG:-}"; LANGS="${LANGS:-}"
# 🎚️ مفاتيحُ المسبار المنطقيّة (‏`decodeGuard` · `criticalPairs`) ولاحقةُ الوسم كي لا تُكتب ذراعٌ فوق أخرى.
EZ="${EZ:-}"; EI="${EI:-}"; SUF="${TAG_SUFFIX:-}"
# 🔬 **سلسلةُ الواجهة الأمامية وسيطاً** (‏2026-09-12 · D-335): 60.6٪ على الطويل المضجَّج وقعت
# **مع** بوّابة الضجيج وسقفِ المجموعة 10ث عاملَين ⇒ يلزم تشريحُهما لا تثبيتُهما:
#   cap = سقفٌ 10 + بوّابة (المقيس) · caponly = سقفٌ 10 بلا بوّابة · gateonly = بوّابةٌ بسقف 25
CHAIN="${CHAIN:-cap}"
EZARGS=""; for f in $EZ; do EZARGS="$EZARGS --ez $f=true"; done
for f in $EI; do EZARGS="$EZARGS --ei $f"; done
[ -n "$EZ$EI" ] && echo "🎚️ مفاتيح: $EZ $EI · لاحقةُ الوسم: '${SUF}'"

# 🎛️⭐ **ذراعُ مفتاحٍ — النموذجُ نفسُه والمفتاحُ وحدَه يختلف** (‏أُضيفت 2026-09-13).
# ⛔ **العطبُ الذي وُجدت له:** `EZ`/`EI` تُطبَّق على **الذراعَين معاً** ⇒ كلُّ سؤالٍ عن مفتاحِ
# فكٍّ (‏«أيكبح حارسُ التكرار سماعَ الكلمة الدخيلة؟» — وهي أضعفُ أصناف الكشف) كان يحتاج
# **شوطَين**، فتُقارَن ذراعٌ بذراعٍ من محاكٍ آخرَ وصوتٍ أُعيد بناؤه — وذاك عينُ ما تمنعه قاعدةُ
# «الذراعان من الشوط نفسِه». ⇒ فصارت ذراعٌ ثالثةٌ **على `q8_shipped.bin` عينِه** بمفاتيحَ أخرى.
ARM2_TAG="${ARM2_TAG:-}"; ARM2_ES="${ARM2_ES:-}"; ARM2_EZ="${ARM2_EZ:-}"; ARM2_EI="${ARM2_EI:-}"
if [ -n "$ARM2_TAG" ]; then
  # ⛔ **ذراعان متطابقتان تُعطيان «لا أثرَ للمفتاح» كذباً** (درسُ D-303 حرفاً) ⇒ تُرفض ابتداءً.
  if [ -z "$ARM2_ES$ARM2_EZ$ARM2_EI" ]; then
    echo "⛔ ARM2_TAG=$ARM2_TAG بلا مفتاحٍ واحد — ذراعٌ مطابقةٌ للمشحون تُعطي «لا أثر» كذباً"; exit 2
  fi
  # ⛔ **ولا تُكتب ذراعٌ فوق أخرى:** وسمٌ يساوي `shipped` أو وسمَ المرشَّح يمحو فرضيّاتِه.
  case "$ARM2_TAG" in
    shipped|"$CAND_TAG"|"$CAND_TAG-ar") echo "⛔ ARM2_TAG=$ARM2_TAG يمحو ذراعاً قائمة"; exit 2 ;;
  esac
fi

echo "🔌 $("$ADB" devices | tail -n +2 | tr '\n' ' ')"
"$ADB" wait-for-device
"$ADB" install -r -g "${APK:?يلزم APK}" | tail -2
"$ADB" push models/shipped.bin /data/local/tmp/q8_shipped.bin | tail -1
if [ -n "$CAND_TAG" ] && [ -f models/cand.bin ]; then
  "$ADB" push models/cand.bin "/data/local/tmp/q8_$CAND_TAG.bin" | tail -1
fi

cd tools/tasmi_bench
ARMS="shipped"; [ -n "$CAND_TAG" ] && ARMS="$ARMS $CAND_TAG"
for A in $ARMS; do
  if [ -z "$LANGS" ]; then
    # ⛔ **D-308:** ما دُرِّب بـ`<|ar|>` يُقاس بـ`<|ar|>`. خدمةُ مضبوطٍ بـ`en` رفعت اتّهامَه الكاذب **2.22 نقطة**
    # فحُكم على ثلاثة نماذجَ بالرسوب ظلماً. والمشحونُ يبقى على افتراض التطبيق (`en`) لأنّ `ar` تكلّفه 3.1 نقاطٍ من الكشف
    # ⇒ الزوجُ الافتراضيُّ هنا هو **زوجُ الشحن**: المشحونُ كما يُشحن، والمرشَّحُ كما سيُشحن.
    if [ "$A" = "shipped" ]; then
      # ⛔ **صريحاً لا افتراضاً (‏2026-09-12 · صُحِّح في D-313):** كلُّ ذراعٍ هنا تُثبِّت لغتَها بالنيّة، ولا
      # تتّكل على اشتقاقٍ يملكه غيرُنا. والسببُ الحقيقيُّ بعد D-312 **ليس** أنّ `q8_shipped.bin` يُشتقّ له
      # `ar` — بل أنّه **ليس اسمَ نموذجٍ في جدول `WhisperDecode.SERVING`** (الأسماءُ هناك أسماءُ الشحن
      # `whisper-tiny-ar-quran…bin` لا أسماءُ `/data/local/tmp/q8_*.bin`) ⇒ **كلُّ** ذراعٍ بلا نيّةٍ تسقط
      # إلى `DEFAULT=en`، فتتطابق ذراعا `en`/`ar` في حلقة `LANGS` ويُحكم كذباً أنّ «اللغةَ لا أثرَ لها».
      # وبالتثبيت الصريح يبقى القياسُ صحيحاً أيضاً **بعد** أن يكسب الجدولُ سطراً جديداً (بوّابةُ v2).
      # 🛡️ ويسندُه حارسُ `emu_sweep.py`: سطرُ `RafiqFrontEnd … lang=` يجب أن يُقرّ بالنيّة وإلا وقف المسح.
      # 🗣️ و`SHIPPED_LANG` حين يكون خطُّ الأساس نموذجاً آخرَ (‏`base` q8 مدرَّبٌ بـ<|ar|> ⇒ يُقاس بـ`ar` · D-308).
      BL="${SHIPPED_LANG:-en}"
      echo "▶ $SET · $A · lang=$BL (صريحاً — كما يُشحن)"
      python emu_sweep.py --set "$SET" --chain "$CHAIN" --chunk "$CHUNK" --tag "$A$SUF" --model-path "/data/local/tmp/q8_$A.bin" --es "lang=$BL" $EZARGS | tail -3
    else
      # ⛔ والوسمُ يحمل اللغةَ صراحةً (`v2-ar` لا `v2`): ملفُّ الذراع القديمةِ المخدومةِ بـ`en` يحمل الاسمَ المجرَّد،
      # فلو تساويا لكُتب أحدُهما فوق الآخر و**قورنت ذراعٌ بذراعٍ أخرى بلا أن يظهر في الرقم شيء**.
      echo "▶ $SET · $A · lang=ar (‏D-308: المضبوطُ يُقاس بما دُرِّب عليه)"
      python emu_sweep.py --set "$SET" --chain "$CHAIN" --chunk "$CHUNK" --tag "$A-ar$SUF" --model-path "/data/local/tmp/q8_$A.bin" --es "lang=ar" $EZARGS | tail -3
    fi
  else
    for L in $LANGS; do
      echo "▶ $SET · $A · lang=$L"
      python emu_sweep.py --set "$SET" --chain "$CHAIN" --chunk "$CHUNK" --tag "$A-$L" \
        --model-path "/data/local/tmp/q8_$A.bin" --es "lang=$L" | tail -3
    done
  fi
done
# 🎛️ وذراعُ المفتاح **آخراً** — على النموذج المشحون نفسِه، فالفرقُ مفتاحٌ لا نموذجٌ ولا صوت.
if [ -n "$ARM2_TAG" ]; then
  A2=""
  for kv in $ARM2_ES; do A2="$A2 --es $kv"; done
  # المنطقيُّ يقبل `مفتاح=false` صريحاً (‏وهذا مقصودُه: إطفاءُ ما هو مشتغلٌ افتراضاً).
  for kv in $ARM2_EZ; do
    case "$kv" in *=*) A2="$A2 --ez $kv" ;; *) A2="$A2 --ez $kv=true" ;; esac
  done
  for kv in $ARM2_EI; do A2="$A2 --ei $kv"; done
  # ⛔ **واللغةُ تُثبَّت صريحاً كذراع الشحن** (‏D-313): `q8_shipped.bin` ليس في جدول `SERVING`
  # فالسكوتُ يسقط إلى `DEFAULT` — ويُقارَن حينها مفتاحٌ بمفتاحٍ **ولغةٍ** لو اختلفت الذراعُ الأخرى.
  HAS_LANG=0; for kv in $ARM2_ES; do case "$kv" in lang=*) HAS_LANG=1 ;; esac; done
  [ "$HAS_LANG" = 0 ] && A2="$A2 --es lang=en"
  echo "▶ $SET · $ARM2_TAG · ذراعُ مفتاحٍ على q8_shipped.bin ⇐$A2"
  python emu_sweep.py --set "$SET" --chain "$CHAIN" --chunk "$CHUNK" --tag "$ARM2_TAG$SUF" \
    --model-path "/data/local/tmp/q8_shipped.bin" $A2 | tail -3
  # ⛔⛔ **حارسُ «ذراعان متطابقتان» — بسببٍ مقيسٍ 2026-09-13 (الشوط 34752581140 · D-377):**
  # طُلبت ذراعُ مفتاحٍ بـ`guardScope=ALL`+`decodeGuard=false` فخرج التشريحُ **بفرقٍ صفريٍّ
  # في كلِّ صفٍّ ومجالٍ [+0.0 .. +0.0]** — لأنّ مسارَ المسبار (`whisperBatch`) **لا يستدعي
  # `withFinalGuard`** فكان المفتاحُ لا يغيّر شيئاً، فصارت الذراعان نسختَين. ⭐ والحارسُ
  # السابقُ (‏«مفتاحٌ واحدٌ على الأقلّ») لم يكفِ: **المفتاحُ وُجد ولم يعمل.**
  # ⇒ يُقارَن النصُّ المفكوكُ بنداً بنداً: تطابقٌ تامٌّ ⇒ **سقوطٌ صريحٌ** (‏والفرضيّاتُ مرفوعةٌ
  # في خطوةٍ تالية `if: always()` فلا يضيع المسح، والحمرةُ تمنع أن يُقرأ الصفرُ جواباً).
  python3 - "$SET" "$CHAIN" "shipped$SUF" "$ARM2_TAG$SUF" <<'PYCMP'
import json, os, sys
st, chain, a, b = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
tag = st.replace(":", "-")
def load(arm):
    p = os.path.join("work", f"hyps_emu_{tag}_{chain}_{arm}.json")
    if not os.path.exists(p):
        print(f"ℹ️ لا ملفَّ {p} — لا مقارنة")
        return None
    d = json.load(open(p, encoding="utf-8"))
    # ⛔ **بالمفتاح `hyps` لا بالتخمين:** `emu_sweep` يكتب `{"meta":…, "hyps":{id:{"text":…}}}`
    # ⇒ قراءةُ الجذر كما هو تُعطي مفتاحَين (`meta`/`hyps`) بلا نصوصٍ فيتساوى كلُّ شيءٍ
    # **فيصرخ الحارسُ كذباً**. ⭐ وحارسٌ يكذب أسوأُ من لا حارس (‏وقد وقع في هذا المستودع مرّتين).
    h = d.get("hyps") if isinstance(d, dict) and isinstance(d.get("hyps"), (dict, list)) else None
    if h is None:
        h = d.get("items") if isinstance(d, dict) and isinstance(d.get("items"), list) else d
    if isinstance(h, list):
        out = {x.get("id"): x.get("text") for x in h if isinstance(x, dict)}
    else:
        out = {k: (v.get("text") if isinstance(v, dict) else v) for k, v in h.items()}
    return {k: v for k, v in out.items() if isinstance(v, str)}
ha, hb = load(a), load(b)
if ha is None or hb is None:
    sys.exit(0)
common = set(ha) & set(hb)
if not common:
    sys.exit(f"⛔ لا بندَ مشتركاً بين {a} و{b} — لا يُقرأ ذلك «لا فرق»")
same = sum(1 for k in common if (ha[k] or "") == (hb[k] or ""))
print(f"🔍 {same}/{len(common)} بنداً نصُّهما واحد")
if same == len(common):
    sys.exit(f"⛔⛔ **ذراعان متطابقتان تماماً** ({a} · {b}): المفتاحُ لم يغيّر حرفاً في "
             f"{len(common)} بنداً ⇒ إمّا لا يصل المحركَ في مسار المسبار، وإمّا لا أثرَ له "
             f"البتّة. **ولا يُقرأ هذا «لا فرقَ يُعتدّ به»** — يُصلَح الربطُ ويُعاد الطلب.")
PYCMP
fi
ls -l work/hyps_emu_*.json | tail -6
