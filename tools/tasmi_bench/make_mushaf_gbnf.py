# -*- coding: utf-8 -*-
"""📖 **مولّدُ نحو GBNF من معجم المصحف** — الخطوة 2-أ من خطة المستشار 2026-10-05 (فكٌّ موجَّهٌ بالمعجم).

الفكرة: whisper-cli يقبل `--grammar f.gbnf --grammar-rule root --grammar-penalty P` فيُنقِص P من لوجيت كلّ رمزٍ
**لا يُكمل** كلمةً من المعجم (‏مكافأةٌ ليّنةٌ لا منعٌ ما دام P محدوداً). هذا يبني ذلك النحوَ.

## المصدر (⛔ لا نصَّ قرآنيّاً يُكتب يدوياً)
نفسُ مصدر `make_critical_pairs_index.py`: `tools/alignment/common.load_text(r)` أي أصولُ `text_<r>.jz` الموثّقة للروايات الستّ،
ثمّ **التطبيعُ نفسُه الذي يقارن به الحاكم** (`scorer.norm`) — وفوقه الصورُ التي يقبلها الحاكمُ صحيحةً لكلمةٍ مرجعيّة
(`scorer.variants` ثمّ `scorer._riwaya_forms` بإعداد الرواية `detect_score.cfg_for`) كي لا يحظر النحوُ ما يقبله الحاكم.

## ما يقبله النحو
`root ::= " "? كلمة (" " كلمة)*` — و«الكلمة» **شجرةُ بادئاتٍ مدموجةُ اللواحق** (‏DAWG: عقدةٌ لكلّ حالةٍ فريدة) بالأحرف:
* كلُّ حرفٍ مطبَّعٍ يقابله **صفُّ الصور الخام** التي تُطبَّع إليه عند الحاكم (‏`ا` ⇐ ا أ إ آ ٱ …؛ `ه` ⇐ ه ة …)،
  مشتقٌّ بتطبيق `scorer.norm` على كلّ حرفٍ عربيّ — لا جدولٌ يدويّ — فمخرجُ النموذج الخام (‏«السماء») يُقبل.
* الهمزةُ `ء` (‏تُطبَّع إلى لا شيء) تُقبل بعد أيّ حرفٍ (‏حلقةٌ ذاتيّة) — فلا تُحظر «السماء» لأنّ المعجمَ يحمل «السما».
* الشجرةُ تقلّل التفرّع: العقدةُ الواحدةُ ≤ ~28 بديلاً لا 15 ألفاً عند الجذر.

    python tools/tasmi_bench/make_mushaf_gbnf.py --out mushaf.gbnf [--words words.txt] [--stats stats.json]
    python tools/tasmi_bench/make_mushaf_gbnf.py --selftest
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))

import scorer  # noqa: E402
import detect_score as D  # noqa: E402

RIWAYAT = ("hafs", "warsh", "qalun", "shuba", "douri", "sousi")
HAMZA = "ء"


def lexicon(riwayat=RIWAYAT, texts=None):
    """مجموعةُ الصور المطبَّعة التي يقبلها الحاكمُ صحيحةً لكلمات المصحف في الروايات المعطاة.

    `texts`: {رواية: قائمةُ آيات} للاختبار؛ وإلا يُحمَّل من أصول المستودع.
    """
    if texts is None:
        from common import load_text
        texts = {r: load_text(r) for r in riwayat}
    out = set()
    for r in riwayat:
        cfg = D.cfg_for(r)
        for ayah in texts[r]:
            for x in ayah.split():
                for f in scorer._riwaya_forms(scorer.variants(x, cfg), cfg):
                    if f:
                        out.add(f)
    return out


def strict_lexicon(riwayat=RIWAYAT, texts=None):
    """المعجمُ الصارم: `scorer.norm` وحدَه (‏بلا صور الحاكم الإضافيّة) — لقياس «oov صارم»."""
    if texts is None:
        from common import load_text
        texts = {r: load_text(r) for r in riwayat}
    out = set()
    for r in riwayat:
        cfg = D.cfg_for(r)
        for ayah in texts[r]:
            for x in ayah.split():
                n = scorer.norm(x, cfg)
                if n:
                    out.add(n)
    return out


def letter_classes(letters):
    """لكلّ حرفٍ مطبَّعٍ: الحروفُ الخام (‏U+0621..U+0671) التي `scorer.norm` يردّها إليه — مشتقٌّ لا مكتوب."""
    cls = {c: [] for c in letters}
    cfg = scorer.Config(strip_yeh_barree=True, dagger_optional=True)
    for cp in range(0x0621, 0x0672):
        ch = chr(cp)
        n = scorer.norm(ch, cfg)
        if n in cls and ch not in cls[n]:
            cls[n].append(ch)
    for c in letters:                       # الحرفُ نفسُه دائماً
        if c not in cls[c]:
            cls[c].insert(0, c)
    return cls


class Node:
    __slots__ = ("term", "kids")

    def __init__(self):
        self.term = False
        self.kids = {}


def build_trie(words):
    root = Node()
    for w in words:
        n = root
        for ch in w:
            n = n.kids.setdefault(ch, Node())
        n.term = True
    return root


def minimize(root):
    """يدمج العقدَ المتطابقةَ بنيةً (‏DAWG) بتجزئةٍ من الأسفل. يعيد (معرّفُ الجذر، {معرّف: (term, ((حرف، معرّف)…))})."""
    table, ids = {}, {}

    def go(n):
        sig = (n.term, tuple((ch, go(k)) for ch, k in sorted(n.kids.items())))
        if sig not in ids:
            ids[sig] = len(ids)
            table[ids[sig]] = sig
        return ids[sig]

    sys.setrecursionlimit(10000)
    r = go(root)
    return r, table


def class_text(chars):
    return "[" + "".join("\\u%04X" % ord(c) for c in chars) + "]"


def render(words):
    """يعيد (نصُّ GBNF، إحصاءات)."""
    letters = sorted({c for w in words for c in w})
    cls = letter_classes(letters)
    trie = build_trie(words)
    rid, table = minimize(trie)
    name = lambda i: "n%d" % i
    lines = ['root ::= " "? %s (" " %s)*' % (name(rid), name(rid))]
    hamza = class_text([HAMZA])
    for i in sorted(table):
        term, kids = table[i]
        alts = ["%s %s" % (class_text(cls[ch]), name(k)) for ch, k in kids]
        if i != rid:
            alts.append("%s %s" % (hamza, name(i)))      # الهمزةُ تُهمَل بعد أيّ حرف
        if term:
            alts.append('""')
        lines.append("%s ::= %s" % (name(i), " | ".join(alts)))
    text = "\n".join(lines) + "\n"
    st = {"words": len(words), "letters": len(letters), "trie_nodes": _count(trie), "dawg_nodes": len(table),
          "bytes": len(text.encode("utf-8"))}
    return text, st


def _count(n):
    return 1 + sum(_count(k) for k in n.kids.values())


def simulate(text_rules, w):
    """يتحقّق من النحو المولَّد بمحاكٍ صغيرٍ لصيغتنا نحن (‏بلا مكتبة): هل يقبل الكلمةَ الخام `w` كاملةً؟"""
    rules = {}
    for ln in text_rules.strip().split("\n"):
        k, v = ln.split(" ::= ", 1)
        rules[k] = [a.strip() for a in v.split(" | ")]

    def cls_set(tok):
        body = tok[1:-1]
        return {chr(int(body[i + 2:i + 6], 16)) for i in range(0, len(body), 6)}

    def walk(rule, s, i):
        for alt in rules[rule]:
            if alt == '""':
                if i == len(s):
                    return True
                continue
            parts = alt.split(" ")
            if i < len(s) and s[i] in cls_set(parts[0]):
                if len(parts) == 1:
                    if i + 1 == len(s):
                        return True
                elif walk(parts[1], s, i + 1):
                    return True
        return False

    import re
    return walk(re.search(r"n\d+", rules["root"][0]).group(0), w, 0)


def selftest():
    # ① اشتقاقُ صفوف الحروف من `scorer.norm` لا من جدولٍ مكتوب
    cl = letter_classes(list("اهويب"))
    assert set("أإآٱ") <= set(cl["ا"]) and "ة" in cl["ه"] and "ؤ" in cl["و"] and "ئ" in cl["ي"] and "ى" in cl["ي"], cl
    assert cl["ب"] == ["ب"], cl
    # ② بناءُ DAWG: صورتان بلاحقةٍ مشتركةٍ تُدمجان، والقبولُ صحيحٌ ومحصورٌ
    words = {"كتب", "قلب", "كلب", "ما"}
    text, st = render(words)
    assert st["dawg_nodes"] < st["trie_nodes"], st
    for w in words:
        assert simulate(text, w), w
    assert simulate(text, "قتب") is False and simulate(text, "كت") is False and simulate(text, "") is False
    # ③ الخامُ يُقبل: ألفٌ مهموزةٌ وتاءٌ مربوطةٌ وهمزةٌ مستقلّةٌ
    t2, _ = render({"سما", "رحمه"})
    assert simulate(t2, "سماء") and simulate(t2, "رحمة") and simulate(t2, "سمأ") and not simulate(t2, "سمي"), "raw"
    # ④ المعجمُ من نصٍّ مصغَّر بتطبيع الحاكم (‏التشكيلُ يُزال، الخنجريّةُ تُنتج صورتين)
    lx = lexicon(("hafs",), {"hafs": ["ذَٰلِكَ الْكِتَابُ"]})
    assert "الكتاب" in lx and "ذلك" in lx, lx
    # ⑤ صيغةُ الرأس والأسماء (‏GBNF: أسماءٌ بـ[a-z0-9-] فقط)
    assert text.startswith('root ::= " "? n') and all(ln.split(" ::= ")[0].replace("-", "").isalnum() for ln in text.strip().split("\n"))
    print("✅ make_mushaf_gbnf selftest: 5 فحوص نجحت")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--out", default="")
    ap.add_argument("--words", default="", help="يكتب قائمة المعجم (كلمةٌ في السطر) — لحساب oov")
    ap.add_argument("--strict-words", default="", help="يكتب المعجم الصارم (scorer.norm وحدَه)")
    ap.add_argument("--stats", default="")
    ap.add_argument("--riwayat", default=",".join(RIWAYAT))
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    words = sorted(lexicon(tuple(a.riwayat.split(","))))
    text, st = render(words)
    print(json.dumps(st, ensure_ascii=False))
    if a.out:
        open(a.out, "w", encoding="utf-8").write(text)
    if a.words:
        open(a.words, "w", encoding="utf-8").write("\n".join(words) + "\n")
    if a.strict_words:
        open(a.strict_words, "w", encoding="utf-8").write("\n".join(sorted(strict_lexicon(tuple(a.riwayat.split(","))))) + "\n")
    if a.stats:
        json.dump(st, open(a.stats, "w"), ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
