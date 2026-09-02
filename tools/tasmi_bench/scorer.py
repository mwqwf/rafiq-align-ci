# -*- coding: utf-8 -*-
"""منقول حرفياً عن `engine/recitation/.../RecitationScorer.kt` — نسخة القياس.

⚠️ **التماثل شرط صحة كل رقم**: هذا الملف ليس «تقريباً» للحاكم بل صورته. يحرسه
اختبار Kotlin `RecitationScorerParityTest` الذي يعيد تشغيل الحاكم الحقيقي على
`work/parity_fixture.json` (مخرج هذا الملف على العيّنة كاملة) ويطابق النتائج
كلمةً كلمة. فإن انحرف أحدهما سقط الاختبار — لا يمر انحراف صامت.

المتغيّرات القابلة للضبط (تُقاس قبل/بعد على العيّنة كاملة لا على أمثلة):
    match_ratio  — عتبة القبول (الأصل: تحريف ≤ خُمس الطول)
    khanjariya   — معاملة الألف الخنجرية ألفاً (الأصل: نعم)
"""
import re

MISSED, ADDED, CORRECT, SUBSTITUTED = "MISSED", "ADDED", "CORRECT", "SUBSTITUTED"

# نسخة طبق الأصل من نطاقات الحاكم: النطاق المتصل 064B–0670 يبتلع الأرقام
# الهندية 0660–0669، فتُكتب النطاقات بالهروب كما في Kotlin حرفاً بحرف.
_STRIP = re.compile("[ً-ٰٟۖ-ۭـ]")
_NON_ARABIC = re.compile("[^ء-ي ]")
_SUBS = [("ٱ", "ا"), ("أ", "ا"), ("إ", "ا"), ("آ", "ا"),
         ("ؤ", "و"), ("ئ", "ي"), ("ى", "ي"), ("ة", "ه"), ("ء", "")]

INF = (2 ** 31 - 1) // 4


class Config:
    """إعدادات القياس — الافتراضي = سلوك الحاكم المشحون بالضبط."""

    def __init__(self, match_num=1, match_den=5, khanjariya=True, extra_subs=(),
                 strip_yeh_barree=False, dagger_optional=False, naql=False):
        self.match_num, self.match_den = match_num, match_den
        self.khanjariya = khanjariya
        self.extra_subs = list(extra_subs)
        self.strip_yeh_barree = strip_yeh_barree
        self.dagger_optional = dagger_optional
        self.naql = naql

    def label(self):
        bits = [f"عتبة {self.match_num}/{self.match_den}"]
        if not self.khanjariya:
            bits.append("بلا خنجرية")
        if self.strip_yeh_barree:
            bits.append("ے→ي")
        if self.dagger_optional:
            bits.append("خنجرية اختيارية")
        if self.naql:
            bits.append("نقل+صلة الميم")
        if self.extra_subs:
            bits.append("+".join(a + "→" + b for a, b in self.extra_subs))
        return "، ".join(bits)


DEFAULT = Config()


def _apply_subs(w, cfg):
    subs = _SUBS + ([("ے", "ي")] if cfg.strip_yeh_barree else []) + cfg.extra_subs
    for a, b in subs:
        w = w.replace(a, b)
    return w


def norm(word, cfg=DEFAULT):
    w = word.replace("ٰ", "ا") if cfg.khanjariya else word
    return _NON_ARABIC.sub("", _apply_subs(_STRIP.sub("", w), cfg))


def _edit(a, b):
    if a == b:
        return 0
    m, n = len(a), len(b)
    prev = list(range(n + 1))
    for i in range(1, m + 1):
        cur = [i] + [0] * n
        for j in range(1, n + 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1,
                         prev[j - 1] + (0 if a[i - 1] == b[j - 1] else 1))
        prev = cur
    return prev[n]


def variants(word, cfg=DEFAULT):
    """صور الكلمة المرجعية المقبولة. الثانية (عند dagger_optional) تُسقط الألف
    الخنجرية بدل نطقها ألفاً: المصحف يكتب ذَٰلِكَ/هَٰذَا/عَلَىٰ بألف فوقية،
    وwhisper يكتبها إملائياً ذلك/هذا/على — والصورتان رسمٌ واحدٌ لكلمة واحدة،
    فردُّ إحداهما خطأً **إنذارٌ كاذب** لا كشف. ولا يمسّ هذا الألف المرسومة
    (قال/قل، كان/كن) فتبقى أخطاء التلاوة الحقيقية مكشوفة."""
    a = norm(word, cfg)
    if not cfg.dagger_optional or "ٰ" not in word:
        return (a,)
    b = _NON_ARABIC.sub("", _apply_subs(_STRIP.sub("", word.replace("ٰ", "")), cfg))
    return (a,) if b == a else (a, b)


def _riwaya_forms(forms, cfg):
    """صور نطقية خاصة بورش/قالون (تُفعَّل بعلم الرواية لا دائماً):
    **النقل** — نقل حركة الهمزة إلى الساكن قبلها فتسقط ألف الوصل نطقاً
    (اَ۬لَايْكَةِ تُقرأ «لَيْكة»، اَ۬لَارْضِ «لَرْض»)؛
    **صلة ميم الجمع** — هُمُۥ/كُمُۥ تُشبع واواً (فأخذَهُمُو).
    لا تُفعَّل في حفص: إسقاط «ال» فيه خطأ تلاوة حقيقي يجب أن يُكشف."""
    if not cfg.naql:
        return forms
    out = list(forms)
    for f in forms:
        if f.startswith("ال") and len(f) > 3:
            out.append(f[1:])
        if f.endswith(("هم", "كم")):
            out += [f + "و", f + "وا"]
    return tuple(dict.fromkeys(out))


def _matches(ref, hyp, cfg):
    refs = ref if isinstance(ref, tuple) else (ref,)
    for r in refs:
        if _edit(r, hyp) * cfg.match_den <= cfg.match_num * max(len(r), len(hyp)):
            return True
    return False


def score(ref_words, hyp_text, cfg=DEFAULT):
    """يعيد dict: words (verdict لكل كلمة مرجعية) + additions."""
    ref = [_riwaya_forms(variants(w, cfg), cfg) for w in ref_words]
    hyp = [w for w in (norm(x, cfg) for x in re.split(r"\s+", hyp_text)) if w]
    R, H = len(ref), len(hyp)
    dp = [[INF] * (H + 1) for _ in range(R + 1)]
    back = [[None] * (H + 1) for _ in range(R + 1)]
    dp[0][0] = 0
    for i in range(R + 1):
        for j in range(H + 1):
            d = dp[i][j]
            if d == INF:
                continue

            def relax(ni, nj, cost, op, i=i, j=j, d=d):
                if ni <= R and nj <= H and cost < INF and d + cost < dp[ni][nj]:
                    dp[ni][nj] = d + cost
                    back[ni][nj] = (i, j, op)

            if i < R and j < H:
                relax(i + 1, j + 1, 0 if _matches(ref[i], hyp[j], cfg) else 2, 0)
            if i < R:
                relax(i + 1, j, 3, 1)
            if j < H:
                relax(i, j + 1, 3, 2)
            if i < R and j + 1 < H:
                relax(i + 1, j + 2, 1 if _matches(ref[i], hyp[j] + hyp[j + 1], cfg) else INF, 3)
            if i + 1 < R and j < H:
                joined = tuple(a + b for a in ref[i] for b in ref[i + 1])
                relax(i + 2, j + 1, 1 if _matches(joined, hyp[j], cfg) else INF, 4)

    words = [None] * R
    additions = []
    i, j = R, H
    while i > 0 or j > 0:
        b = back[i][j]
        if b is None:
            break
        pi, pj, op = b
        if op == 0:
            words[pi] = (pi, CORRECT if _matches(ref[pi], hyp[pj], cfg) else SUBSTITUTED, hyp[pj])
        elif op == 1:
            words[pi] = (pi, MISSED, None)
        elif op == 2:
            additions.insert(0, hyp[pj])
        elif op == 3:
            words[pi] = (pi, CORRECT, hyp[pj] + " " + hyp[pj + 1])
        elif op == 4:
            words[pi] = (pi, CORRECT, hyp[pj])
            words[pi + 1] = (pi + 1, CORRECT, hyp[pj])
        i, j = pi, pj
    for k in range(R):
        if words[k] is None:
            words[k] = (k, MISSED, None)
    return {"words": words, "additions": additions,
            "correct": sum(1 for w in words if w[1] == CORRECT), "total": R}
